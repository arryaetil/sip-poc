// SIP-owned headless export adapter; the upstream image remains unchanged.
let busy = false;
const error = (status, message) => Object.assign(new Error(message), { status });
export function exportRoute(pathname) {
  return /^\/api\/projects\/([a-zA-Z0-9_-]{1,128})\/export\/(image|pdf-image|pptx)$/.exec(pathname);
}
export function validateExport(body) {
  if (!body || typeof body !== 'object' || Array.isArray(body)) throw error(400, 'Ongeldige exportaanvraag.');
  if (typeof body.fileName !== 'string' || !/\.html?$/i.test(body.fileName) || body.fileName.length > 1024 || body.fileName.split(/[\\/]/).some(p => p === '..') || /^[\\/]/.test(body.fileName)) throw error(400, 'Kies een HTML-ontwerp om te exporteren.');
  if (body.editable === true) throw error(422, 'Deze Studio exporteert PowerPoint als afbeeldingen per pagina. Bewerkbare PowerPoint wordt hier nog niet ondersteund.');
  if (body.imageFormat && !['png', 'jpeg', 'jpg', 'webp'].includes(body.imageFormat)) throw error(400, 'Kies PNG, JPG of WebP.');
  for (const key of ['width', 'height']) if (body[key] != null && (!Number.isInteger(body[key]) || body[key] < 100 || body[key] > 4096)) throw error(400, 'Afmetingen moeten tussen 100 en 4096 pixels liggen.');
}
export async function renderExport(projectId, format, body, upstream, executablePath = process.env.STUDIO_CHROMIUM_PATH || '/usr/bin/chromium-browser') {
  validateExport(body);
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
    if (await page.locator('img').evaluateAll(images=>images.some(image=>image.src && image.naturalWidth===0))) throw error(422,'Een afbeelding in dit ontwerp ontbreekt. Herstel de afbeelding en exporteer opnieuw.');
    await page.addStyleTag({content:'*,*::before,*::after{animation:none!important;transition:none!important;caret-color:transparent!important}'});
    const selectors=['[data-slide]','.slide','.deck-slide','section.slide'];
    let slides;
    for (const selector of selectors) {
      const candidate=page.locator(selector);
      if (await candidate.count()>1) {slides=candidate;break;}
    }
    if (format==='pptx' && !slides) throw error(422,'Dit ontwerp bevat geen herkenbare presentatiepagina’s. Exporteer als PDF of afbeelding.');
    const count=slides?await slides.count():1;
    if(count>40)throw error(413,'Exporteer maximaal 40 pagina’s tegelijk.');
    const captures=[];
    for(let i=0;i<(format==='image'?1:count);i++) {
      let target=slides?slides.nth(i):page.locator('[data-export-root], .poster, .post, .artboard, main').first();
      if(await target.count()===0)target=page.locator('body');
      if(slides) {
        // Carousel pages normally sit outside an overflow-hidden viewport.
        // Show one page at a time without editing the project's source file.
        await slides.evaluateAll((nodes,index)=>nodes.forEach((n,j)=>{n.style.setProperty('display',j===index?'block':'none','important');n.style.setProperty('transform','none','important');n.style.setProperty('opacity','1','important');n.style.setProperty('visibility','visible','important');}),i);
        await target.evaluate(node=>{for(let p=node.parentElement;p&&p!==document.body;p=p.parentElement){p.style.setProperty('transform','none','important');p.style.setProperty('overflow','visible','important');}});
      }
      const box=await target.boundingBox();
      if(!box || box.width<1 || box.height<1 || box.width>8000 || box.height>16000 || box.width*box.height>16000000)throw error(422,'Deze pagina heeft geen bruikbare exportafmetingen.');
      const jpeg=format==='image'&&['jpg','jpeg'].includes(body.imageFormat);
      const buffer=await target.screenshot({type:jpeg?'jpeg':'png',...(jpeg?{quality:95}:{}),timeout:20000});
      captures.push({buffer,width:box.width,height:box.height,jpeg});
    }
    if(format==='image'){
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
  } catch(e){console.error('studio export failed:',e.status||500,e.status?e.message:'renderer failure');res.writeHead(e.status||502,{'content-type':'application/json','cache-control':'no-store'});res.end(JSON.stringify({error:{code:'SIP_EXPORT_FAILED',message:e.status?e.message:'Exporteren is niet gelukt. Probeer opnieuw.'}}));}
}
