// Compatibility for the upstream desktop PDF command in a hosted Studio.
export const STUDIO_EXPORT_SCRIPT = `<script id="sip-studio-export">(function(){
// Use normal browser downloads, including embedded browsers without a native save dialog.
try{window.showSaveFilePicker=undefined;}catch{}
const original=window.fetch.bind(window);
async function download(result,fallback){const blob=new Blob([await result.arrayBuffer()],{type:'application/octet-stream'});const fileName=/filename="([^"]+)"/.exec(result.headers.get('content-disposition')||'')?.[1]||fallback;if(window.parent!==window){window.parent.postMessage({type:'sip-studio-download',blob,fileName},'SIP_DOWNLOAD_PARENT_ORIGIN');return;}const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download=fileName;document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),60000);}
function addPowerPoint(){
const actions=document.querySelector('#app-chrome-file-actions');const match=location.pathname.match(/^\\/projects\\/([a-zA-Z0-9_-]+)\\/.*\\/files\\/(.+\\.html?)$/);if(!actions)return;const existing=actions.querySelector('[data-sip-pptx]');if(!match){existing?.remove();actions.querySelector('[data-sip-pptx-status]')?.remove();return;}if(existing)return;
const button=document.createElement('button');button.dataset.sipPptx='';button.textContent='PowerPoint';button.title='Download PowerPoint met een afbeelding per pagina';button.style.cssText='padding:6px 10px;border:1px solid #ccc;border-radius:6px;background:white;color:#111;cursor:pointer;font:12px Ubuntu,sans-serif';
button.onclick=async()=>{const current=location.pathname.match(/^\\/projects\\/([a-zA-Z0-9_-]+)\\/.*\\/files\\/(.+\\.html?)$/);if(!current)return;button.disabled=true;let status=actions.querySelector('[data-sip-pptx-status]');if(!status){status=document.createElement('span');status.dataset.sipPptxStatus='';status.setAttribute('role','status');status.style.fontSize='12px';actions.appendChild(status);}status.textContent='PowerPoint wordt gemaakt…';try{const response=await original('/api/projects/'+current[1]+'/export/pptx',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({fileName:decodeURIComponent(current[2])})});if(!response.ok){const data=await response.json().catch(()=>({}));throw new Error(data.error?.message||'Exporteren is niet gelukt.');}await download(response,'ontwerp.pptx');status.textContent='Gedownload: afbeeldingen per pagina.';}catch(error){status.textContent=error.message;}finally{button.disabled=false;}};actions.appendChild(button);
}
document.addEventListener('DOMContentLoaded',addPowerPoint);setInterval(addPowerPoint,1000);
// The desktop image dialog captures the iframe itself. In a hosted Studio,
// use the authenticated renderer so the downloaded artwork is complete.
document.addEventListener('click',async event=>{
const button=event.target.closest?.('button');const modal=button?.closest('.image-export-modal');
if(!modal||modal.closest('.file-version-export-backdrop')||!['Save','Speichern','Opslaan'].includes(button.textContent.trim()))return;
const project=location.pathname.match(/^\\/projects\\/([a-zA-Z0-9_-]{1,128})/);
const file=location.pathname.match(/\\/files\\/(.+)$/);if(!project||!file)return;
event.preventDefault();event.stopImmediatePropagation();button.disabled=true;const label=button.textContent;button.textContent='Exporteren…';
let status=modal.querySelector('[data-sip-export-status]');if(!status){status=document.createElement('p');status.dataset.sipExportStatus='';status.setAttribute('role','status');modal.appendChild(status);}status.textContent='Je bestand wordt klaargemaakt…';
try{const format=modal.querySelector('input[type=radio]:checked')?.value||'png';
const response=await original('/api/projects/'+project[1]+'/export/images',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({fileName:decodeURIComponent(file[1]),imageFormat:format})});
if(!response.ok){let data=await response.json().catch(()=>({}));throw new Error(data.error?.message||'Exporteren is niet gelukt. Probeer opnieuw.');}
const pages=Number(response.headers.get('x-sip-export-pages')||1);await download(response,'ontwerp.zip');status.textContent=pages>1?'Download klaar: alle '+pages+' pagina’s staan als losse afbeeldingen in het ZIP-bestand.':'Download klaar: de afbeelding staat in het ZIP-bestand bij je downloads.';
}catch(error){status.textContent=error.message;}finally{button.disabled=false;button.textContent=label;}
},true);
window.fetch=async function(input,options){
  const url=new URL(typeof input==='string'?input:input.url,location.href);
  const method=options?.method||(typeof input==='object'?input.method:'GET');
  if(url.origin!==location.origin||method!=='POST'||!/^\\/api\\/projects\\/[^/]+\\/export\\/pdf$/.test(url.pathname))return original(input,options);
  url.pathname=url.pathname.replace(/\\/pdf$/,'/pdf-image');
  const requestOptions={...options};
  if(typeof input==='object'){requestOptions.headers=options?.headers||input.headers;requestOptions.body=options?.body||await input.clone().text();}
  const result=await original(url.toString(),{...requestOptions,method:'POST'});
  if(!result.ok)return result;
  await download(result,'ontwerp.pdf');
  return new Response(JSON.stringify({ok:true}),{status:200,headers:{'content-type':'application/json'}});
};})();</script>`;
