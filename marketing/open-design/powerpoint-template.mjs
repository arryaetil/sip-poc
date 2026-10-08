// Reuse the official Office package, including all its masters, layouts and themes.
// Only the example slides are replaced; the private source master is never written.
import fs from 'node:fs/promises';
import path from 'node:path';
import JSZip from 'jszip';

const BRANDS = {
  'ibc-group': {name:'ibc group', cover:1, content:9},
  etil: {name:'Etil', cover:4, content:12},
};
const fail = message => Object.assign(new Error(message), {status:422});
const escape = value => String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&apos;'}[c]));
const emptyTree='<p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>';

function fillPlaceholder(shape, paragraphs, id, fontSize) {
  const original=/<p:txBody>([\s\S]*?)<\/p:txBody>/.exec(shape)?.[1] || '';
  const bodyPr=/<a:bodyPr\b[^>]*(?:\/>|>[\s\S]*?<\/a:bodyPr>)/.exec(original)?.[0] || '<a:bodyPr/>';
  let listStyle=/<a:lstStyle\b[^>]*(?:\/>|>[\s\S]*?<\/a:lstStyle>)/.exec(original)?.[0] || '<a:lstStyle/>';
  if(fontSize)listStyle=listStyle.replace(/\bsz="\d+"/g,'sz="'+fontSize*100+'"');
  const text=paragraphs.map(p=>'<a:p><a:pPr lvl="0" marL="0" indent="0"><a:buNone/></a:pPr><a:r><a:rPr lang="nl-NL"'+(fontSize?' sz="'+fontSize*100+'"':'')+'/><a:t>'+escape(p)+'</a:t></a:r><a:endParaRPr lang="nl-NL"/></a:p>').join('');
  return shape.replace(/<p:cNvPr\b[^>]*\bid="\d+"/, m=>m.replace(/id="\d+"/,'id="'+id+'"'))
    .replace(/<p:txBody>[\s\S]*?<\/p:txBody>/,'<p:txBody>'+bodyPr+listStyle+text+'</p:txBody>')
    .replace(/<[^:>]+:extLst\b[^>]*>[\s\S]*?<\/[^:>]+:extLst>/g,'');
}

export async function createTemplatePowerPoint(brand, pages, {title='Marketing Studio', templatePath}={}) {
  const config=BRANDS[brand];
  if(!config) throw fail('Kies de huisstijl van ibc group of Etil.');
  if(!Array.isArray(pages)||pages.length<1||pages.length>40)throw fail('Kies een ontwerp met één tot veertig pagina’s.');
  for(const page of pages){
    if(!page.title?.trim()||!Array.isArray(page.paragraphs))throw fail('Een pagina heeft geen herkenbare tekst. Gebruik de export met afbeeldingen of voeg een duidelijke titel toe.');
    if(page.title.length>240||page.paragraphs.join('\n').length>4000||page.paragraphs.length>24)throw fail('Een pagina bevat te veel tekst voor de template. Verdeel de tekst over meer pagina’s.');
    if(page.bodyLines>12||page.titleFontSize===0)throw fail('De tekst past niet leesbaar in de officiële dia-indeling. Verdeel de tekst over meer pagina’s of kies de export met afbeeldingen.');
  }
  const sourcePath=templatePath || path.join(process.env.OD_DATA_DIR||'/app/.od','design-systems',brand,'assets/private-library/Powerpoint Master',config.name+' - Powerpoint Master v1.0.pptx');
  let source;try{source=await fs.readFile(sourcePath);}catch{throw fail('De officiële PowerPoint-template is niet beschikbaar. Gebruik voorlopig de export met afbeeldingen.');}
  const zip=await JSZip.loadAsync(source);
  const read=async name=>{const file=zip.file(name);if(!file)throw fail('De PowerPoint-template is onvolledig.');return file.async('string');};
  const presentation=await read('ppt/presentation.xml');
  if(!/<p:sldSz\b[^>]*cx="12192000"[^>]*cy="6858000"/.test(presentation))throw fail('De officiële template heeft een onverwacht paginaformaat.');
  for(const file of Object.keys(zip.files))if(/^ppt\/(?:slides|notesSlides|comments)\//.test(file))zip.remove(file);
  let contentTypes=await read('[Content_Types].xml');
  contentTypes=contentTypes.replace(/<Override\b[^>]*PartName="\/ppt\/(?:slides|notesSlides|comments)\/[^>]*\/>/g,'');
  let relationships=await read('ppt/_rels/presentation.xml.rels');
  relationships=relationships.replace(/<Relationship\b[^>]*Type="[^"]*\/(?:slide|commentAuthors)"[^>]*\/>/g,'');
  const slideIds=[];
  for(let i=0;i<pages.length;i++){
    const page=pages[i];
    // The cover's 70pt title is only used when the source text fits its shorter box.
    const cover=i===0 && page.coverFits!==false && page.title.length<=42 && page.paragraphs.join(' ').length<=90;
    const layoutNumber=cover?config.cover:config.content;
    const layout=await read('ppt/slideLayouts/slideLayout'+layoutNumber+'.xml');
    const placeholders=[...layout.matchAll(/<p:sp>[\s\S]*?<\/p:sp>/g)].map(m=>m[0]).filter(s=>s.includes('<p:ph')&&!/type="(?:dt|ftr|sldNum)"/.test(s));
    const heading=placeholders.find(s=>/type="(?:title|ctrTitle)"/.test(s));
    const body=placeholders.find(s=>s!==heading);
    if(!heading||!body)throw fail('De tekstindeling in de officiële template kon niet worden gelezen.');
    const titleFont=cover?70:Math.min(page.titleFontSize||36,36);
    const shapes=fillPlaceholder(heading,[page.title],2,titleFont)+fillPlaceholder(body,page.paragraphs.length?page.paragraphs:[''],3);
    const slide='<?xml version="1.0" encoding="UTF-8" standalone="yes"?><p:sld xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"><p:cSld name="'+escape(page.title)+'"><p:spTree>'+emptyTree+shapes+'</p:spTree></p:cSld><p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sld>';
    zip.file('ppt/slides/slide'+(i+1)+'.xml',slide);
    zip.file('ppt/slides/_rels/slide'+(i+1)+'.xml.rels','<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rIdLayout" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="../slideLayouts/slideLayout'+layoutNumber+'.xml"/></Relationships>');
    contentTypes=contentTypes.replace('</Types>','<Override PartName="/ppt/slides/slide'+(i+1)+'.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/></Types>');
    const rid='rIdSIPSlide'+(i+1);
    slideIds.push('<p:sldId id="'+(256+i)+'" r:id="'+rid+'"/>');
    relationships=relationships.replace('</Relationships>','<Relationship Id="'+rid+'" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" Target="slides/slide'+(i+1)+'.xml"/></Relationships>');
  }
  zip.file('ppt/presentation.xml',presentation.replace(/<p:sldIdLst>[\s\S]*?<\/p:sldIdLst>/,'<p:sldIdLst>'+slideIds.join('')+'</p:sldIdLst>').replace(/<p:custShowLst>[\s\S]*?<\/p:custShowLst>/g,'').replace(/<p14:sectionLst\b[^>]*>[\s\S]*?<\/p14:sectionLst>/g,''));
  zip.file('ppt/_rels/presentation.xml.rels',relationships);
  zip.file('[Content_Types].xml',contentTypes);
  if(zip.file('docProps/core.xml'))zip.file('docProps/core.xml',(await read('docProps/core.xml')).replace(/<dc:title>[\s\S]*?<\/dc:title>/,'<dc:title>'+escape(title)+'</dc:title>'));
  if(zip.file('docProps/app.xml'))zip.file('docProps/app.xml',(await read('docProps/app.xml')).replace(/<Slides>\d+<\/Slides>/,'<Slides>'+pages.length+'</Slides>'));
  return {buffer:await zip.generateAsync({type:'nodebuffer',compression:'DEFLATE'}),type:'application/vnd.openxmlformats-officedocument.presentationml.presentation',ext:'pptx',pages:pages.length};
}
