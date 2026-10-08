// App glue never reaches into sandboxed preview documents.
export const STUDIO_PREVIEW_SCRIPT = `<script id="sip-studio-preview">(function(){function update(){
const project=location.pathname.match(/^\\/projects\\/([a-zA-Z0-9_-]{1,128})(?:\\/|$)/);
if(project&&window.parent!==window)window.parent.postMessage({type:'sip-studio-project',projectId:project[1]},SIP_PARENT_ORIGIN);
for(const frame of document.querySelectorAll('iframe')){const src=frame.getAttribute('src')||'';if(src.includes('/raw/')||src==='about:blank'){frame.style.width='100%';frame.style.height='100%';}}
}document.addEventListener('load',update,true);window.addEventListener('resize',update);setInterval(update,1000);})();</script>`;

// Runs inside the preview sandbox and changes display only.
export const ARTWORK_PREVIEW_SCRIPT = `<script id="sip-artwork-preview">(function(){function update(){
if(document.querySelectorAll('[data-slide],.slide,.deck-slide').length>1)return;
const root=document.querySelector('[data-export-root],.poster,.post,.artboard');if(!root)return;
const w=root.offsetWidth,h=root.offsetHeight,aw=innerWidth,ah=innerHeight;if(!w||!h||!aw||!ah)return;
const scale=Math.min(1,aw/w,ah/h);let button=document.getElementById('sip-preview-fit');if(scale>=1&&!button)return;
if(!button){button=document.createElement('button');button.id='sip-preview-fit';button.type='button';button.dataset.fit='true';button.textContent='Op ware grootte';button.style.cssText='position:fixed;right:8px;bottom:8px;z-index:2147483647;padding:7px 12px;border:1px solid #bbb;border-radius:16px;background:white;color:#111;font:12px sans-serif;cursor:pointer';button.onclick=()=>{button.dataset.fit=button.dataset.fit==='true'?'false':'true';button.textContent=button.dataset.fit==='true'?'Op ware grootte':'Hele ontwerp';update();};document.body.appendChild(button);}
const fit=button.dataset.fit==='true';document.body.style.margin='0';document.body.style.overflow=fit?'hidden':'auto';document.documentElement.style.overflow=fit?'hidden':'auto';
root.style.transformOrigin='top left';root.style.position='absolute';root.style.top=fit?Math.max(0,(ah-h*scale)/2)+'px':'0';root.style.left=fit?Math.max(0,(aw-w*scale)/2)+'px':'0';root.style.transform=fit?'scale('+scale+')':'none';
}document.addEventListener('DOMContentLoaded',update);window.addEventListener('load',update);window.addEventListener('resize',update);})();</script>`;
