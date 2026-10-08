// Fit fixed-size marketing previews; project files and exports stay unchanged.
export const STUDIO_PREVIEW_SCRIPT = `<script id="sip-studio-preview">(function(){
function update(){const frames=Array.from(document.querySelectorAll('iframe'));
const reference=frames.find(f=>(f.getAttribute('src')||'').includes('/raw/'));
for(const frame of frames){try{const src=frame.getAttribute('src')||'';if(!src.includes('/raw/')&&src!=='about:blank')continue;
const doc=frame.contentDocument;if(!doc?.body)continue;
if(src==='about:blank'&&reference&&!doc.querySelector('base')){const base=doc.createElement('base');base.href=new URL(reference.getAttribute('src'),location.href).href;doc.head.prepend(base);}
if(doc.querySelectorAll('[data-slide],.slide,.deck-slide').length>1)continue;
const root=doc.querySelector('[data-export-root],.poster,.post,.artboard');if(!root)continue;
frame.style.width='100%';frame.style.height='100%';
const w=root.offsetWidth,h=root.offsetHeight,aw=frame.clientWidth,ah=frame.clientHeight;if(!w||!h||!aw||!ah)continue;
const scale=Math.min(1,aw/w,ah/h);let button=doc.getElementById('sip-preview-fit');if(scale>=1&&!button)continue;
if(!button){button=doc.createElement('button');button.id='sip-preview-fit';button.type='button';button.dataset.fit='true';button.textContent='Op ware grootte';button.style.cssText='position:fixed;right:8px;bottom:8px;z-index:2147483647;padding:7px 12px;border:1px solid #bbb;border-radius:16px;background:white;color:#111;font:12px sans-serif;cursor:pointer';button.onclick=()=>{button.dataset.fit=button.dataset.fit==='true'?'false':'true';button.textContent=button.dataset.fit==='true'?'Op ware grootte':'Hele ontwerp';update();};doc.body.appendChild(button);}
const fit=button.dataset.fit==='true';doc.body.style.margin='0';doc.body.style.overflow=fit?'hidden':'auto';doc.documentElement.style.overflow=fit?'hidden':'auto';
root.style.transformOrigin='top left';root.style.position='absolute';root.style.top=fit?Math.max(0,(ah-h*scale)/2)+'px':'0';root.style.left=fit?Math.max(0,(aw-w*scale)/2)+'px':'0';root.style.transform=fit?'scale('+scale+')':'none';
}catch{}}}
document.addEventListener('load',update,true);window.addEventListener('resize',update);setInterval(update,1000);
})();</script>`;
