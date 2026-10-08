// Compatibility for the upstream desktop PDF command in a hosted Studio.
export const STUDIO_EXPORT_SCRIPT = `<script id="sip-studio-export">(function(){
// Use normal browser downloads, including embedded browsers without a native save dialog.
try{window.showSaveFilePicker=undefined;}catch{}
const original=window.fetch.bind(window);
async function download(result,fallback){const blob=new Blob([await result.arrayBuffer()],{type:'application/octet-stream'});const fileName=/filename="([^"]+)"/.exec(result.headers.get('content-disposition')||'')?.[1]||fallback;if(window.parent!==window){window.parent.postMessage({type:'sip-studio-download',blob,fileName},'SIP_DOWNLOAD_PARENT_ORIGIN');return;}const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download=fileName;document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),60000);}
function addPowerPoint(){
const actions=document.querySelector('#app-chrome-file-actions');const match=location.pathname.match(/^\\/projects\\/([a-zA-Z0-9_-]+)\\/.*\\/files\\/(.+\\.html?)$/);if(!actions)return;const existing=actions.querySelector('[data-sip-pptx]');if(!match){existing?.remove();actions.querySelector('[data-sip-pptx-status]')?.remove();return;}if(existing)return;
const button=document.createElement('button');button.dataset.sipPptx='';button.textContent='PowerPoint';button.title='Download met de officiële template of behoud het Studio-ontwerp';button.style.cssText='padding:6px 10px;border:1px solid #ccc;border-radius:6px;background:white;color:#111;cursor:pointer;font:12px Ubuntu,sans-serif';
button.onclick=async()=>{
const current=location.pathname.match(/^\\/projects\\/([a-zA-Z0-9_-]+)\\/.*\\/files\\/(.+\\.html?)$/);if(!current||document.querySelector('[data-sip-pptx-dialog]'))return;
const dialog=document.createElement('dialog');dialog.dataset.sipPptxDialog='';dialog.setAttribute('aria-label','PowerPoint downloaden');dialog.style.cssText='width:min(480px,90vw);padding:28px;border:1px solid #ddd;border-radius:16px;font:16px Ubuntu,sans-serif;color:#111;background:white';
dialog.innerHTML='<h2 style="margin:0 0 16px;font-size:24px">PowerPoint downloaden</h2><label style="display:block">Uitvoering<select data-sip-pptx-mode style="display:block;width:100%;padding:10px;margin:8px 0 16px"><option value="template">Officiële template, bewerkbare tekst</option><option value="images">Studio-ontwerp, afbeeldingen per dia</option></select></label><p data-sip-pptx-description>Je tekst komt in de vaste brede dia-indelingen (16:9). De officiële masters en huisstijl blijven beschikbaar in PowerPoint. Afbeeldingen, grafieken en diagrammen uit je ontwerp worden niet overgenomen.</p><label data-sip-brand-label style="display:block">Huisstijl<select data-sip-pptx-brand style="display:block;width:100%;padding:10px;margin:8px 0 16px"><option value="">Kies een huisstijl</option><option value="ibc-group">ibc group</option><option value="etil">Etil</option></select></label><p role="status" data-sip-pptx-status></p><div style="display:flex;gap:12px;justify-content:flex-end"><button type="button" data-sip-pptx-cancel>Annuleren</button><button type="button" data-sip-pptx-save>Download PowerPoint</button></div>';
document.body.appendChild(dialog);dialog.showModal();
const mode=dialog.querySelector('[data-sip-pptx-mode]'),brand=dialog.querySelector('[data-sip-pptx-brand]'),save=dialog.querySelector('[data-sip-pptx-save]'),status=dialog.querySelector('[data-sip-pptx-status]');
  const controller=new AbortController();
  const close=()=>{controller.abort();dialog.close();dialog.remove();};dialog.addEventListener('cancel',close);dialog.querySelector('[data-sip-pptx-cancel]').onclick=close;
mode.onchange=()=>{dialog.querySelector('[data-sip-brand-label]').hidden=mode.value==='images';dialog.querySelector('[data-sip-pptx-description]').textContent=mode.value==='images'?'Iedere dia bevat een afbeelding van je volledige ontwerp. De tekst is hierbij niet apart bewerkbaar.':'Je tekst komt in de vaste brede dia-indelingen (16:9). De officiële masters en huisstijl blijven beschikbaar in PowerPoint. Afbeeldingen, grafieken en diagrammen uit je ontwerp worden niet overgenomen.';};
try{const response=await original('/api/projects/'+current[1]);if(response.ok){const data=await response.json();const id=data.project?.designSystemId||data.designSystemId||'';if(id==='user:etil'||id==='etil')brand.value='etil';if(id==='user:ibc-group'||id==='ibc-group')brand.value='ibc-group';}}catch{}
save.onclick=async()=>{if(mode.value==='template'&&!brand.value){status.textContent='Kies eerst een huisstijl.';brand.focus();return;}save.disabled=true;mode.disabled=true;brand.disabled=true;status.textContent='PowerPoint wordt gemaakt…';try{const response=await original('/api/projects/'+current[1]+'/export/'+(mode.value==='template'?'pptx-template':'pptx'),{method:'POST',signal:controller.signal,headers:{'content-type':'application/json'},body:JSON.stringify({fileName:decodeURIComponent(current[2]),templateBrand:mode.value==='template'?brand.value:undefined})});if(!response.ok){const data=await response.json().catch(()=>({}));throw new Error(data.error?.message||'Exporteren is niet gelukt.');}if(controller.signal.aborted)return;await download(response,'ontwerp.pptx');status.textContent=mode.value==='template'?'PowerPoint is gemaakt met bewerkbare tekst. Je browser start de download.':'PowerPoint is gemaakt met afbeeldingen per dia. Je browser start de download.';}catch(error){status.textContent=error.message;}finally{save.disabled=false;mode.disabled=false;brand.disabled=false;}};
};actions.appendChild(button);
}
document.addEventListener('DOMContentLoaded',addPowerPoint);setInterval(addPowerPoint,1000);
// Upstream can remove its native PPTX item after capability discovery. Keep the
// adapter's supported template export available in the artwork export menu.
function ensureExportMenu(){
if(!document.querySelector('[data-sip-pptx]'))return;
for(const menu of document.querySelectorAll('[role="menu"]')){
const items=[...menu.querySelectorAll('[role="menuitem"]')];
const zip=items.find(item=>['Download as .zip','Download als ZIP','Als ZIP herunterladen'].includes(item.textContent.trim()));
if(!zip||items.some(item=>['Export as PPTX','PowerPoint downloaden','PowerPoint herunterladen'].includes(item.textContent.trim())))continue;
const entry=document.createElement('button');entry.type='button';entry.setAttribute('role','menuitem');entry.dataset.sipExportPptxMenu='';entry.className=zip.className;entry.textContent=window.sipStudioT?.('Export as PPTX')||'Export as PPTX';menu.appendChild(entry);
}
}
new MutationObserver(ensureExportMenu).observe(document.documentElement,{childList:true,subtree:true});
setInterval(ensureExportMenu,1000);

// The upstream ZIP contains project source files. In the marketing export menu,
// ZIP means the artwork pages. Keep both PowerPoint entry points consistent.
let zipBusy=false;
document.addEventListener('click',async event=>{
const item=event.target.closest?.('[role="menuitem"]');if(!item)return;
const label=item.textContent.trim();
const current=location.pathname.match(/^\\/projects\\/([a-zA-Z0-9_-]+)\\/.*\\/files\\/(.+\\.html?)$/);if(!current)return;
if(['Export as PPTX','PowerPoint downloaden','PowerPoint herunterladen'].includes(label)){
event.preventDefault();event.stopImmediatePropagation();document.querySelector('[data-sip-pptx]')?.click();return;
}
if(!['Download as .zip','Download als ZIP','Als ZIP herunterladen'].includes(label))return;
event.preventDefault();event.stopImmediatePropagation();if(zipBusy)return;zipBusy=true;
let status=document.querySelector('[data-sip-zip-status]');if(!status){status=document.createElement('p');status.dataset.sipZipStatus='';status.setAttribute('role','status');document.querySelector('#app-chrome-file-actions')?.appendChild(status);}
const translate=text=>window.sipStudioT?.(text)||text;status.textContent=translate('Preparing ZIP…');
try{
const response=await original('/api/projects/'+current[1]+'/export/images',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({fileName:decodeURIComponent(current[2]),imageFormat:'png'})});
if(!response.ok){const data=await response.json().catch(()=>({}));throw new Error(data.error?.message||translate('Export failed. Please try again.'));}
await download(response,'ontwerp.zip');status.textContent=translate('ZIP with all artwork pages is ready. Your browser is starting the download.');
}catch(error){status.textContent=error.message;}finally{zipBusy=false;}
},true);
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
