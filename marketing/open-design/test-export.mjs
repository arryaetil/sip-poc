import assert from 'node:assert/strict';
import {renderExport, validateExport, exportRoute} from './export-renderer.mjs';
import {PDFDocument} from 'pdf-lib';
import {STUDIO_PREVIEW_SCRIPT} from './studio-preview-script.mjs';
import {STUDIO_EXPORT_SCRIPT} from './studio-export-script.mjs';
import {Script} from 'node:vm';
for(const script of [STUDIO_PREVIEW_SCRIPT,STUDIO_EXPORT_SCRIPT])new Script(script.replace(/^<script[^>]*>|<\/script>$/g,''));
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
// A previous failed render must release the browser/semaphore.
assert.equal((await renderExport('fixture','image',{fileName:'post.html'},upstream,executable)).pages,1);
console.log('Real Chromium exports: PNG, two-page PDF/PPTX, historical version, failed asset, isolation and recovery passed');
const {chromium}=await import('playwright-core');
const browser=await chromium.launch({executablePath:executable,headless:true});
try{
 const page=await browser.newPage({viewport:{width:1200,height:800}});
 await page.route('http://preview.invalid/**',route=>route.fulfill({contentType:'text/html',body:'<html><body style="margin:0"><main class="post" style="width:1080px;height:1350px;background:red">The whole design<footer>Logo</footer></main></body></html>'}));
 await page.setContent('<iframe style="width:600px;height:600px" src="http://preview.invalid/api/projects/fixture/raw/post.html"></iframe>'+STUDIO_PREVIEW_SCRIPT);
 // Both documents must share an origin for the preview compatibility script.
 await page.goto('http://preview.invalid/app');
 await page.setContent('<iframe style="width:600px;height:600px" src="/api/projects/fixture/raw/post.html"></iframe>'+STUDIO_PREVIEW_SCRIPT);
 const frame=page.frameLocator('iframe');
 await frame.locator('#sip-preview-fit').waitFor();
 const box=await frame.locator('main').boundingBox();
 const frameBox=await page.locator('iframe').boundingBox();
 assert.ok(box.height<=frameBox.height && box.width<=frameBox.width,'The entire portrait must fit the preview');
 await frame.getByRole('button',{name:'Op ware grootte'}).click();
 assert.ok((await frame.locator('main').boundingBox()).width>1000);
 console.log('Preview fit and full-size toggle passed');
}finally{await browser.close();}
