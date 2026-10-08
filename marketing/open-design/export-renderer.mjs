// SIP-owned headless export adapter; the upstream image remains unchanged.
let busy = false;
const error = (status, message) => Object.assign(new Error(message), { status });
export function exportRoute(pathname) {
  return /^\/api\/projects\/([a-zA-Z0-9_-]{1,128})\/export\/(image|images|pdf-image|pptx|pptx-template)$/.exec(pathname);
}
export function validateExport(body) {
  if (!body || typeof body !== 'object' || Array.isArray(body)) throw error(400, 'Ongeldige exportaanvraag.');
  if (typeof body.fileName !== 'string' || !/\.html?$/i.test(body.fileName) || body.fileName.length > 1024 || body.fileName.split(/[\\/]/).some(p => p === '..') || /^[\\/]/.test(body.fileName)) throw error(400, 'Kies een HTML-ontwerp om te exporteren.');
  if (body.editable === true) throw error(422, 'Deze Studio exporteert PowerPoint als afbeeldingen per pagina. Bewerkbare PowerPoint wordt hier nog niet ondersteund.');
  if (body.imageFormat && !['png', 'jpeg', 'jpg', 'webp'].includes(body.imageFormat)) throw error(400, 'Kies PNG, JPG of WebP.');
  if (body.templateBrand && !['etil','ibc-group'].includes(body.templateBrand)) throw error(400,'Kies de huisstijl van ibc group of Etil.');
  for (const key of ['width', 'height']) if (body[key] != null && (!Number.isInteger(body[key]) || body[key] < 100 || body[key] > 4096)) throw error(400, 'Afmetingen moeten tussen 100 en 4096 pixels liggen.');
  if (body.index != null && (!Number.isInteger(body.index) || body.index < 0 || body.index > 39)) throw error(400, 'Kies een geldige pagina.');
}
export async function renderExport(projectId, format, body, upstream, executablePath = process.env.STUDIO_CHROMIUM_PATH || '/usr/bin/chromium-browser') {
  validateExport(body);
  if(format==='pptx-template'&&!['etil','ibc-group'].includes(body.templateBrand))throw error(422,'Kies de huisstijl van ibc group of Etil.');
  if (busy) throw error(429, 'Er wordt al een export gemaakt. Probeer het over enkele seconden opnieuw.');
  busy = true;
  let browser;
  try {
    // The existing standalone export resolves project files, versions and inline assets.
    const filePath = body.fileName.split(/[\\/]/).map(encodeURIComponent).join('/');
    const source = body.versionId
      ? await upstream(`/api/projects/${projectId}/export/${filePath}?inline=1&versionId=${encodeURIComponent(body.versionId)}`)
      : await upstream(`/api/projects/${projectId}/export/html`, { method: 'POST', headers: {'content-type':'application/json'}, body: JSON.stringify({fileName:body.fileName, title:body.title}) });
    if (!source.ok) throw error(source.status, 'Het gekozen ontwerp kon niet worden gelezen.');
    const html = await source.text();
    if (Buffer.byteLength(html) > 16_000_000) throw error(413, 'Dit ontwerp is te groot om te exporteren.');
    const {chromium} = await import('playwright-core');
    browser = await chromium.launch({executablePath, headless:true, args:['--no-sandbox','--disable-dev-shm-usage']});
    const context = await browser.newContext({viewport:{width:body.width || 1440,height:body.height || 1080},deviceScaleFactor:2,serviceWorkers:'block'});
    // No API credentials enter the page. Bundled project assets are data URLs;
    // scripts cannot read other projects, local files, or external network services.
    const rawPrefix = `/api/projects/${projectId}/raw/`;
    await context.route('**/*', async route => {
      const url = new URL(route.request().url());
      if (url.origin !== 'http://sip-render.invalid' || !url.pathname.startsWith(rawPrefix) || route.request().method() !== 'GET') return route.abort();
      const asset = await upstream(url.pathname, {redirect:'error'});
      if (!asset.ok) return route.abort();
      await route.fulfill({status:200,contentType:asset.headers.get('content-type')||'application/octet-stream',body:Buffer.from(await asset.arrayBuffer())});
    });
    const page = await context.newPage();
    page.setDefaultTimeout(15000);
    const directory = filePath.includes('/') ? filePath.slice(0,filePath.lastIndexOf('/')+1) : '';
    const prepared = await page.evaluate(({html,base}) => {
      const document = new DOMParser().parseFromString(html,'text/html');
      document.querySelectorAll('base').forEach(node=>node.remove());
      const element=document.createElement('base');element.href=base;document.head.prepend(element);
      return '<!doctype html>'+document.documentElement.outerHTML;
    },{html,base:'http://sip-render.invalid'+rawPrefix+directory});
    await page.setContent(prepared,{waitUntil:'load',timeout:20000});
    await page.evaluate(async()=>{await document.fonts.ready;await Promise.all(Array.from(document.images).map(i=>i.complete?Promise.resolve():new Promise(r=>{i.onload=r;i.onerror=r})));});
    if(format==='pptx-template'){
      const fs=await import('node:fs/promises');const path=await import('node:path');
      const fonts=[];
      for(const [name,weight] of [['Ubuntu-Regular.ttf','400'],['Ubuntu-Bold.ttf','700']]){
        const source=path.join(process.env.OD_DATA_DIR||'/app/.od','design-systems',body.templateBrand,'fonts',name);
        let font;try{font=await fs.readFile(source);}catch{throw error(422,'Het officiële Ubuntu-lettertype voor de template is niet beschikbaar.');}
        fonts.push({data:font.toString('base64'),weight});
      }
      await page.evaluate(async fonts=>{for(const f of fonts){const face=new FontFace('SIP Template Ubuntu','url(data:font/ttf;base64,'+f.data+')',{weight:f.weight});await face.load();document.fonts.add(face);}},fonts);
    }
    if (await page.locator('img').evaluateAll(images=>images.some(image=>image.src && image.naturalWidth===0))) throw error(422,'Een afbeelding in dit ontwerp ontbreekt. Herstel de afbeelding en exporteer opnieuw.');
    await page.addStyleTag({content:'*,*::before,*::after{animation:none!important;transition:none!important;caret-color:transparent!important}'});
    const selectors=['[data-slide]','.slide','.deck-slide','section.slide'];
    let slides;
    for (const selector of selectors) {
      const candidate=page.locator(selector);
      if (await candidate.count()>1) {slides=candidate;break;}
    }
    const count=slides?await slides.count():1;
    if(body.index!=null && body.index>=count)throw error(400,'Deze pagina bestaat niet in het ontwerp.');
    if(count>40)throw error(413,'Exporteer maximaal 40 pagina’s tegelijk.');
    const captures=[], templatePages=[];
    // Screenshotting a tall page resizes Chromium's viewport. Project resize
    // handlers can overwrite even inline !important via style.transform=... .
    // A stylesheet rule keeps the export layout stable through that event.
    await page.addStyleTag({content:'[data-sip-export-wrapper]{transform:none!important;position:relative!important;left:0!important;top:0!important;right:auto!important;bottom:auto!important;margin:0!important}'});
    for(let i=0;i<(format==='image'?1:count);i++) {
      const index=format==='image'?(body.index||0):i;
      let target=slides?slides.nth(index):null;
      if(!target){
        for(const selector of ['[data-export-root]','.poster','.post','.artboard','[data-slide]','.slide','main']){
          const candidate=page.locator(selector).first();if(await candidate.count()){target=candidate;break;}
        }
      }
      if(!target)target=page.locator('body');
      if(await target.count()===0)target=page.locator('body');
      if(slides || format==='pptx-template' || await target.evaluate(node=>node.matches('[data-export-root],.poster,.post,.artboard,[data-slide],.slide'))) {
        // Carousel pages normally sit outside an overflow-hidden viewport.
        // Show one page at a time without editing the project's source file.
        if(slides)await slides.evaluateAll((nodes,index)=>nodes.forEach((n,j)=>{n.style.setProperty('display',j===index?'block':'none','important');n.style.setProperty('transform','none','important');n.style.setProperty('opacity','1','important');n.style.setProperty('visibility','visible','important');}),index);
        await target.evaluate(node=>{
          const width=node.offsetWidth,height=node.offsetHeight;
          // Generated decks often use centered, absolutely positioned wrappers.
          // Removing only their scale leaves the page outside the screenshot.
          for(let p=node;p&&p!==document.body;p=p.parentElement){
            p.setAttribute('data-sip-export-wrapper','');
            for(const [key,value] of Object.entries({transform:'none',position:'relative',left:'0',top:'0',right:'auto',bottom:'auto',margin:'0',padding:p===node?getComputedStyle(p).padding:'0',overflow:p===node?'hidden':'visible'}))p.style.setProperty(key,value,'important');
          }
          node.style.setProperty('width',width+'px','important');node.style.setProperty('height',height+'px','important');
          document.body.style.margin='0';
        });
      }
      const box=await target.boundingBox();
      if(!box || box.width<1 || box.height<1 || box.width>8000 || box.height>16000 || box.width*box.height>16000000)throw error(422,'Deze pagina heeft geen bruikbare exportafmetingen.');
      if(format==='pptx-template'){
        templatePages.push(await target.evaluate(root=>{
          const clean=s=>s.replace(/\s+/g,' ').trim();
          const heading=root.querySelector('[data-pptx-title],h1,h2,.value-quote') || Array.from(root.querySelectorAll('p')).sort((a,b)=>parseFloat(getComputedStyle(b).fontSize)-parseFloat(getComputedStyle(a).fontSize))[0];
          const title=heading?clean(heading.textContent):'';
          const clone=root.cloneNode(true);
          clone.querySelectorAll('script,style,button,nav,footer,.slide-meta,.ai-label,.page-no,.eyebrow,[data-pptx-ignore]').forEach(n=>n.remove());
          const titleNode=clone.querySelector('[data-pptx-title],h1,h2,.value-quote');
          if(titleNode)titleNode.remove();
          const groups=new Map();const walker=document.createTreeWalker(clone,NodeFilter.SHOW_TEXT);let node;
          while(node=walker.nextNode()){
            const text=clean(node.textContent);if(!text)continue;
            const owner=node.parentElement.closest('p,li,h1,h2,h3,h4,.path-step,.source-bar,.insight-card')||node.parentElement;
            if(!groups.has(owner))groups.set(owner,[]);groups.get(owner).push(text);
          }
          const paragraphs=[...groups.values()].map(parts=>clean(parts.join(' '))).filter(t=>t!==title&&!/^(?:\d{1,2}(?:\s*\/\s*\d{1,2})?|[↓↑→←])$/.test(t)).map(t=>t.replace(/^\d{2}\s+(?=\D)/,''));
          const unique=[...new Set(paragraphs)];
          const ctx=document.createElement('canvas').getContext('2d');
          const lines=(text,points,width,bold=true)=>{ctx.font=(bold?'700 ':'400 ')+(points*96/72)+'px "SIP Template Ubuntu"';let count=1,current='';for(const word of text.split(/\s+/)){if(ctx.measureText(word).width>width)return 99;const candidate=current?current+' '+word:word;if(ctx.measureText(candidate).width>width){count++;current=word;}else current=candidate;}return count;};
          // Leave room for font metrics and line spacing used by Office readers.
          let titleFontSize=36;while(titleFontSize>=30&&lines(title,titleFontSize,1000)>2)titleFontSize-=2;
          return {title,paragraphs:unique,titleFontSize:titleFontSize<30?0:titleFontSize,coverFits:lines(title,70,866)<=2,bodyLines:unique.reduce((sum,p)=>sum+lines(p,18,1104,false)+.5,0)};
        }));
        continue;
      }
      const jpeg=['image','images'].includes(format)&&['jpg','jpeg'].includes(body.imageFormat);
      const buffer=await target.screenshot({type:jpeg?'jpeg':'png',...(jpeg?{quality:95}:{}),timeout:20000});
      captures.push({buffer,width:box.width,height:box.height,jpeg});
    }
    if(format==='pptx-template'){
      const {createTemplatePowerPoint}=await import('./powerpoint-template.mjs');
      return await createTemplatePowerPoint(body.templateBrand,templatePages,{title:body.title});
    }
    if(format==='images'){
      const {default:JSZip}=await import('jszip');const zip=new JSZip();
      for(let i=0;i<captures.length;i++){
        let buffer=captures[i].buffer;let ext=captures[i].jpeg?'jpg':'png';
        if(body.imageFormat==='webp'){
          const data=await page.evaluate(async source=>{const image=new Image();image.src=source;await image.decode();const canvas=document.createElement('canvas');canvas.width=image.naturalWidth;canvas.height=image.naturalHeight;canvas.getContext('2d').drawImage(image,0,0);return canvas.toDataURL('image/webp',0.95).split(',')[1];},'data:image/png;base64,'+buffer.toString('base64'));
          buffer=Buffer.from(data,'base64');ext='webp';
        }
        zip.file(`pagina-${String(i+1).padStart(2,'0')}.${ext}`,buffer);
      }
      return {buffer:await zip.generateAsync({type:'nodebuffer'}),type:'application/zip',ext:'zip',pages:captures.length};
    }
    if(format==='image'||format==='images'){
      if(body.imageFormat==='webp'){
        const data=await page.evaluate(async source=>{const image=new Image();image.src=source;await image.decode();const canvas=document.createElement('canvas');canvas.width=image.naturalWidth;canvas.height=image.naturalHeight;canvas.getContext('2d').drawImage(image,0,0);return canvas.toDataURL('image/webp',0.95).split(',')[1];},'data:image/png;base64,'+captures[0].buffer.toString('base64'));
        return {buffer:Buffer.from(data,'base64'),type:'image/webp',ext:'webp',pages:1};
      }
      return {buffer:captures[0].buffer,type:captures[0].jpeg?'image/jpeg':'image/png',ext:captures[0].jpeg?'jpg':'png',pages:1};
    }
    if(format==='pdf-image') {
      const {PDFDocument}=await import('pdf-lib');const pdf=await PDFDocument.create();
      for(const image of captures){const embedded=await pdf.embedPng(image.buffer);const scale=960/Math.max(image.width,image.height);const width=image.width*scale,height=image.height*scale;pdf.addPage([width,height]).drawImage(embedded,{x:0,y:0,width,height});}
      return {buffer:Buffer.from(await pdf.save()),type:'application/pdf',ext:'pdf',pages:captures.length};
    }
    const {default:PptxGenJS}=await import('pptxgenjs');const pptx=new PptxGenJS();const first=captures[0];const width=10,height=10*first.height/first.width;
    pptx.defineLayout({name:'SIP',width,height});pptx.layout='SIP';pptx.title=body.title||'Marketing Studio';pptx.author='ibc group marketing';
    for(const image of captures){const slide=pptx.addSlide();slide.addImage({data:'data:image/png;base64,'+image.buffer.toString('base64'),x:0,y:0,w:width,h:height});}
    return {buffer:Buffer.from(await pptx.write({outputType:'nodebuffer'})),type:'application/vnd.openxmlformats-officedocument.presentationml.presentation',ext:'pptx',pages:captures.length};
  } finally {await browser?.close().catch(()=>{});busy=false;}
}
export async function handleExport(req,res,match,upstream) {
  const chunks=[];let size=0;
  try {
    for await (const chunk of req){size+=chunk.length;if(size>65536)throw error(413,'Exportaanvraag is te groot.');chunks.push(chunk);}
    let body;try{body=JSON.parse(Buffer.concat(chunks).toString('utf8'));}catch{throw error(400,'Ongeldige exportaanvraag.');}
    const rendered=await renderExport(match[1],match[2],body,upstream);
    const title=String(body.title||body.fileName).replace(/\.html?$/i,'').replace(/[^a-zA-Z0-9_-]+/g,'-').slice(0,100)||'ontwerp';
    res.writeHead(200,{'content-type':rendered.type,'content-disposition':`attachment; filename="${title}.${rendered.ext}"`,'content-length':rendered.buffer.length,'cache-control':'no-store','x-sip-export-pages':String(rendered.pages)});res.end(rendered.buffer);
  } catch(e){console.error('studio export failed:',e.status||500,String(e.message||'renderer failure').slice(0,500));res.writeHead(e.status||502,{'content-type':'application/json','cache-control':'no-store'});res.end(JSON.stringify({error:{code:'SIP_EXPORT_FAILED',message:e.status?e.message:'Exporteren is niet gelukt. Probeer opnieuw.'}}));}
}
