// Compatibility for the upstream desktop PDF command in a hosted Studio.
export const STUDIO_EXPORT_SCRIPT = `<script id="sip-studio-export">(function(){
// Use normal browser downloads, including embedded browsers without a native save dialog.
try{window.showSaveFilePicker=undefined;}catch{}
const original=window.fetch.bind(window);
window.fetch=async function(input,options){
  const url=new URL(typeof input==='string'?input:input.url,location.href);
  const method=options?.method||(typeof input==='object'?input.method:'GET');
  if(url.origin!==location.origin||method!=='POST'||!/^\\/api\\/projects\\/[^/]+\\/export\\/pdf$/.test(url.pathname))return original(input,options);
  url.pathname=url.pathname.replace(/\\/pdf$/,'/pdf-image');
  const requestOptions={...options};
  if(typeof input==='object'){requestOptions.headers=options?.headers||input.headers;requestOptions.body=options?.body||await input.clone().text();}
  const result=await original(url.toString(),{...requestOptions,method:'POST'});
  if(!result.ok)return result;
  const blob=await result.blob();const downloadUrl=URL.createObjectURL(blob);const a=document.createElement('a');
  a.href=downloadUrl;a.download=/filename="([^"]+)"/.exec(result.headers.get('content-disposition')||'')?.[1]||'ontwerp.pdf';
  document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(downloadUrl),60000);
  return new Response(JSON.stringify({ok:true}),{status:200,headers:{'content-type':'application/json'}});
};})();</script>`;
