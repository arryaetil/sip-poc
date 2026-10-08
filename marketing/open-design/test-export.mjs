import assert from 'node:assert/strict';
import {renderExport, validateExport, exportRoute} from './export-renderer.mjs';
import {PDFDocument} from 'pdf-lib';
import {STUDIO_PREVIEW_SCRIPT,ARTWORK_PREVIEW_SCRIPT} from './studio-preview-script.mjs';
import {STUDIO_EXPORT_SCRIPT} from './studio-export-script.mjs';
import {Script} from 'node:vm';
import JSZip from 'jszip';
import {readFile} from 'node:fs/promises';
for(const script of [STUDIO_PREVIEW_SCRIPT,ARTWORK_PREVIEW_SCRIPT,STUDIO_EXPORT_SCRIPT])new Script(script.replace(/^<script[^>]*>|<\/script>$/g,''));
const executable = process.env.STUDIO_CHROMIUM_PATH;
assert.ok(executable, 'Set STUDIO_CHROMIUM_PATH for the real browser test');
for (const body of [null, [], {fileName:'../secret.html'}, {fileName:'/private.html'}, {fileName:'post.html',width:99999}, {fileName:'post.html',editable:true}]) {
  assert.throws(()=>validateExport(body));
}
assert.equal(exportRoute('/api/projects/../export/image'), null);
const fixture='<html><body><script>fetch("https://blocked.invalid/private");fetch("http://sip-render.invalid/api/projects/other/raw/secret.txt");</script><section data-slide style="width:400px;height:500px;background:red">Page 1</section><section data-slide style="width:400px;height:500px;background:blue">Page 2</section></body></html>';
let reads=[];
const upstream=async(path)=>{reads.push(path);return new Response(fixture,{status:200});};
for(const format of ['image','pdf-image','pptx']){
  reads=[];
  const result=await renderExport('fixture',format,{fileName:'post.html'},upstream,executable);
  assert.equal(result.pages,format==='image'?1:2);
  assert.ok(result.buffer.length>100);
  assert.deepEqual(reads,['/api/projects/fixture/export/html'], 'Scripts must not fetch another project or external service');
  if(format==='image')assert.equal(result.buffer.subarray(1,4).toString(),'PNG');
  if(format==='pdf-image')assert.equal((await PDFDocument.load(result.buffer)).getPageCount(),2);
  if(format==='pptx')assert.equal(result.buffer.subarray(0,2).toString(),'PK');
}
reads=[];
for(const imageFormat of ['jpeg','webp']){
 const result=await renderExport('fixture','image',{fileName:'post.html',imageFormat},upstream,executable);
 assert.equal(result.type,`image/${imageFormat}`);
 if(imageFormat==='webp')assert.equal(result.buffer.subarray(8,12).toString(),'WEBP');
 if(imageFormat==='jpeg')assert.equal(result.buffer[0],255);
}
 reads=[];
 await renderExport('fixture','image',{fileName:'nested/post.html',versionId:'version-1'},upstream,executable);
assert.deepEqual(reads,['/api/projects/fixture/export/nested/post.html?inline=1&versionId=version-1']);
await assert.rejects(renderExport('fixture','image',{fileName:'post.html'},async()=>new Response('<img src="https://blocked.invalid/missing.png">'),executable),e=>e.status===422);
await assert.rejects(renderExport('fixture','image',{fileName:'post.html'},async()=>new Response('',{status:404}),executable),e=>e.status===404);
const first=await renderExport('fixture','image',{fileName:'post.html',index:0},upstream,executable);
const second=await renderExport('fixture','image',{fileName:'post.html',index:1},upstream,executable);
assert.notDeepEqual(first.buffer,second.buffer,'Selecting another carousel page must change the exported image');
const carousel=await renderExport('fixture','images',{fileName:'post.html'},upstream,executable);
const zip=await JSZip.loadAsync(carousel.buffer);
assert.equal(carousel.pages,2);
assert.deepEqual(Object.keys(zip.files),['pagina-01.png','pagina-02.png']);
assert.notDeepEqual(await zip.file('pagina-01.png').async('nodebuffer'),await zip.file('pagina-02.png').async('nodebuffer'));
// Real generated carousel structure: centered absolute deck with a resize script.
const centered='<html><head><style>body{margin:0}.preview{display:grid;place-items:center;padding:20px}.viewport{width:100%;height:900px;position:relative;overflow:hidden}.deck{position:absolute;left:50%;top:50%;width:400px;height:500px;transform:translate(-50%,-50%) scale(.5)}.slide{position:absolute;inset:0}</style></head><body><div class="preview"><div class="viewport"><div class="deck"><section data-slide class="slide" style="background:red">Page 1</section><section data-slide class="slide" style="background:blue">Page 2</section></div></div></div><nav>Never export navigation</nav></body></html>';
const centeredResult=await renderExport('fixture','images',{fileName:'post.html'},async()=>new Response(centered),executable);
const centeredZip=await JSZip.loadAsync(centeredResult.buffer);
assert.deepEqual(await centeredZip.file('pagina-01.png').async('nodebuffer'),first.buffer,'Centered wrappers must produce the complete same page as an unwrapped slide');
const tall= centered.replaceAll('400px','1080px').replaceAll('500px','1350px').replace('</body>','<script>function fit(){document.querySelector(".deck").style.transform="translate(-50%,-50%) scale(.5)"}window.addEventListener("resize",fit);fit();</script></body>');
const plainTall=fixture.replaceAll('400px','1080px').replaceAll('500px','1350px');
const expectedTall=await renderExport('fixture','image',{fileName:'post.html'},async()=>new Response(plainTall),executable);
const resized=await renderExport('fixture','images',{fileName:'post.html'},async()=>new Response(tall),executable);
const resizedZip=await JSZip.loadAsync(resized.buffer);
assert.deepEqual(await resizedZip.file('pagina-01.png').async('nodebuffer'),expectedTall.buffer,'A real resize handler must not recenter or rescale tall exported pages');
// A previous failed render must release the browser/semaphore.
assert.equal((await renderExport('fixture','image',{fileName:'post.html'},upstream,executable)).pages,1);
console.log('Real Chromium exports: PNG, two-page PDF/PPTX, historical version, failed asset, isolation and recovery passed');
const {chromium}=await import('playwright-core');
const browser=await chromium.launch({executablePath:executable,headless:true});
try{
 const page=await browser.newPage({viewport:{width:1200,height:800}});
 await page.route('http://preview.invalid/**',route=>route.fulfill({contentType:'text/html',body:'<html><head>'+ARTWORK_PREVIEW_SCRIPT+'</head><body style="margin:0"><main class="post" style="width:1080px;height:1350px;background:red">The whole design<footer>Logo</footer></main></body></html>'}));
 await page.setContent('<iframe style="width:600px;height:600px" src="http://preview.invalid/api/projects/fixture/raw/post.html"></iframe>'+STUDIO_PREVIEW_SCRIPT);
 // Both documents must share an origin for the preview compatibility script.
 await page.goto('http://preview.invalid/app');
 await page.setContent('<iframe sandbox="allow-scripts" style="width:600px;height:600px" src="/api/projects/fixture/raw/post.html"></iframe>'+STUDIO_PREVIEW_SCRIPT);
 const frame=page.frameLocator('iframe');
 await frame.locator('#sip-preview-fit').waitFor();
 const box=await frame.locator('main').boundingBox();
 const frameBox=await page.locator('iframe').boundingBox();
 assert.ok(box.height<=frameBox.height && box.width<=frameBox.width,'The entire portrait must fit the preview');
 await frame.getByRole('button',{name:'Op ware grootte'}).click();
 assert.ok((await frame.locator('main').boundingBox()).width>1000);
 console.log('Preview fit and full-size toggle passed');
 let requests=0;
 await page.route('http://download.invalid/**',route=>{
   if(route.request().method()==='POST'){
     requests++;assert.deepEqual(route.request().postDataJSON(),{fileName:'post.html',imageFormat:'png'});
     return requests===1?route.fulfill({status:200,contentType:'application/zip',headers:{'content-disposition':'attachment; filename="carousel.zip"','x-sip-export-pages':'2'},body:carousel.buffer}):route.fulfill({status:422,contentType:'application/json',body:JSON.stringify({error:{message:'Een afbeelding ontbreekt.'}})});
   }
   return route.fulfill({contentType:'text/html',body:'<html><head>'+STUDIO_EXPORT_SCRIPT+'</head><body><div class="image-export-modal" role="dialog"><input type="radio" value="png" checked><button>Save</button></div></body></html>'});
 });
 await page.goto('http://download.invalid/projects/fixture/conversations/one/files/post.html');
 const downloading=page.waitForEvent('download');await page.getByRole('button',{name:'Save'}).click();const downloaded=await downloading;
 assert.equal(downloaded.suggestedFilename(),'carousel.zip');
 assert.deepEqual(await readFile(await downloaded.path()),carousel.buffer);
 assert.match(await page.getByRole('status').innerText(),/alle 2 pagina/);
 await page.getByRole('button',{name:'Save'}).click();
 await page.waitForFunction(()=>document.querySelector('[role=status]').textContent==='Een afbeelding ontbreekt.');
 assert.equal(await page.getByRole('button',{name:'Save'}).isEnabled(),true);
 console.log('Normal image-dialog download contains every carousel page; truthful error and retry passed');
 const app=await readFile(new URL('../../backend/app/app.js',import.meta.url),'utf8');
 const handler=app.slice(app.indexOf('window.addEventListener("message", event => {'),app.indexOf('\n\nasync function openPreparedStudio()'));
 assert.ok(handler.includes('sip-studio-download'));
 await page.route('http://embedded.invalid/**',route=>route.fulfill({contentType:'text/html',body:'<iframe id="studio-frame" src="http://download.invalid/projects/fixture/conversations/one/files/post.html"></iframe><script>const studioFrame=document.querySelector("iframe");const studioLastLink="http://download.invalid";let studioProjectId="";'+handler+'</script>'}));
 await page.unroute('http://download.invalid/**');
 await page.route('http://download.invalid/**',route=>route.request().method()==='POST'?route.fulfill({status:200,contentType:'application/zip',headers:{'content-disposition':'attachment; filename="embedded.zip"','x-sip-export-pages':'2'},body:carousel.buffer}):route.fulfill({contentType:'text/html',body:'<html><head>'+STUDIO_EXPORT_SCRIPT.replace("\'SIP_DOWNLOAD_PARENT_ORIGIN\'",JSON.stringify('http://embedded.invalid'))+'</head><body><div class="image-export-modal"><button>Save</button></div></body></html>'}));
 await page.goto('http://embedded.invalid/');
 const embeddedDownload=page.waitForEvent('download');await page.frameLocator('iframe').getByRole('button',{name:'Save'}).click();const embedded=await embeddedDownload;
 assert.equal(embedded.suggestedFilename(),'embedded.zip');assert.deepEqual(await readFile(await embedded.path()),carousel.buffer);
 console.log('Embedded Studio download through the actual SIP message handler passed');
}finally{await browser.close();}
