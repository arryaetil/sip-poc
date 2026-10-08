// Translate Studio chrome only. Artwork, captions, prompts and generated answers
// keep the language the user requested for their content.
export const STUDIO_LANGUAGE_SCRIPT=`<script id="sip-studio-language">(function(){
const initial='SIP_STUDIO_LANGUAGE';const parentOrigin='SIP_LANGUAGE_PARENT_ORIGIN';
const allowed=['nl','en','de'];let language=allowed.includes(initial)?initial:'nl';
const copy={
nl:{title:'Wat wil je maken?',subtitle:'Beschrijf je post, carousel of presentatie. Kies de huisstijl; kennis uit het platform wordt automatisch meegenomen.',big:'Groot bekijken'},
en:{title:'What would you like to create?',subtitle:'Describe your post, carousel or presentation. Choose the house style; knowledge from the platform is included automatically.',big:'Large preview'},
de:{title:'Was möchtest du erstellen?',subtitle:'Beschreibe deinen Post, dein Karussell oder deine Präsentation. Wähle die Hausgestaltung; Wissen aus der Plattform wird automatisch einbezogen.',big:'Große Vorschau'}
};
const labels=[
['Home','Start','Start'],['All projects','Alle projecten','Alle Projekte'],['Recent projects','Recente projecten','Letzte Projekte'],
['Search','Zoeken','Suchen'],['Run','Maken','Erstellen'],['Send','Versturen','Senden'],['Stop','Stoppen','Stoppen'],
['Export','Exporteren','Exportieren'],['Share','Delen','Teilen'],['Preview','Voorbeeld','Vorschau'],['Code','Code','Code'],
['Export as PDF','Download als PDF','Als PDF herunterladen'],['Export as image','Download als afbeelding','Als Bild herunterladen'],
['Download as .zip','Download als ZIP','Als ZIP herunterladen'],['Export as standalone HTML','Download als HTML','Als HTML herunterladen'],
['Format','Bestandstype','Dateiformat'],['Cancel','Annuleren','Abbrechen'],['Save','Opslaan','Speichern'],
['Choose a format, then download the current preview as an image.','Kies een bestandstype. Alle pagina’s worden als afbeeldingen in een ZIP-bestand gedownload.','Wähle ein Dateiformat. Alle Seiten werden als Bilder in einer ZIP-Datei heruntergeladen.'],
['Describe what you want to generate…','Beschrijf wat je wilt maken…','Beschreibe, was du erstellen möchtest…'],
['Attach a file, link your design system, or describe what you want to make','Voeg een bestand toe, kies een huisstijl of beschrijf wat je wilt maken','Füge eine Datei hinzu, wähle eine Hausgestaltung oder beschreibe, was du erstellen möchtest'],
['Mock up a signup flow','Beschrijf wat je wilt maken','Beschreibe, was du erstellen möchtest'],
['Reload Preview','Voorbeeld vernieuwen','Vorschau neu laden'],['Collapse sidebar','Projectlijst inklappen','Projektliste einklappen'],['Expand sidebar','Projectlijst uitklappen','Projektliste ausklappen'],
['Present','Groot bekijken','Große Vorschau'],['In this tab','In dit tabblad','In diesem Tab'],['Exit presentation','Grote weergave sluiten','Präsentation schließen'],
['Design Files','Ontwerpbestanden','Designdateien'],['New tab','Nieuw tabblad','Neuer Tab'],['More','Meer','Mehr'],
['Download PowerPoint','Download PowerPoint','PowerPoint herunterladen'],['PowerPoint downloaden','PowerPoint downloaden','PowerPoint herunterladen'],
['Version history','Versiegeschiedenis','Versionsverlauf'],['Versions','Versies','Versionen'],['Conversation history','Gespreksgeschiedenis','Gesprächsverlauf'],
['Execution mode','Uitvoering','Ausführung'],['Add context','Context toevoegen','Kontext hinzufügen'],['Design system','Huisstijl','Hausgestaltung'],
['House style','Huisstijl','Hausgestaltung'],['Export version','Uitvoering','Exportversion'],
['Official template, editable text','Officiële template, bewerkbare tekst','Offizielle Vorlage, bearbeitbarer Text'],
['Studio design, images per slide','Studio-ontwerp, afbeeldingen per dia','Studio-Design, Bilder pro Folie'],
['Choose a house style','Kies een huisstijl','Wähle eine Hausgestaltung'],
['Your text uses the standard widescreen slide layouts (16:9). The official masters and house style remain available in PowerPoint. Images, charts and diagrams from your design are not included.','Je tekst komt in de vaste brede dia-indelingen (16:9). De officiële masters en huisstijl blijven beschikbaar in PowerPoint. Afbeeldingen, grafieken en diagrammen uit je ontwerp worden niet overgenomen.','Dein Text nutzt die breiten Folienlayouts (16:9). Die offiziellen Master und die Hausgestaltung bleiben in PowerPoint verfügbar. Bilder, Grafiken und Diagramme aus deinem Design werden nicht übernommen.'],
['Each slide contains an image of your complete design. Text cannot be edited separately in this version.','Iedere dia bevat een afbeelding van je volledige ontwerp. De tekst is hierbij niet apart bewerkbaar.','Jede Folie enthält ein Bild deines vollständigen Designs. Text kann dabei nicht separat bearbeitet werden.'],
['Choose a house style first.','Kies eerst een huisstijl.','Wähle zuerst eine Hausgestaltung.'],
['Preparing PowerPoint…','PowerPoint wordt gemaakt…','PowerPoint wird erstellt…'],['Preparing your file…','Je bestand wordt klaargemaakt…','Deine Datei wird vorbereitet…'],['Exporting…','Exporteren…','Exportieren…'],
['PowerPoint with editable text is ready. Your browser is starting the download.','PowerPoint is gemaakt met bewerkbare tekst. Je browser start de download.','PowerPoint mit bearbeitbarem Text ist erstellt. Dein Browser startet den Download.'],
['PowerPoint with images per slide is ready. Your browser is starting the download.','PowerPoint is gemaakt met afbeeldingen per dia. Je browser start de download.','PowerPoint mit Bildern pro Folie ist erstellt. Dein Browser startet den Download.']
];
const lookup=new Map();for(const row of labels)for(const text of row)lookup.set(text,row);
const originals=new WeakMap();let pending=false;
const t=text=>{const row=lookup.get(text);return row?row[language==='en'?0:language==='nl'?1:2]:text;};window.sipStudioT=t;
function translateNode(node){const old=originals.get(node);const source=old&&node.textContent===old.last?old.source:node.textContent;const next=t(source);if(next!==node.textContent)node.textContent=next;originals.set(node,{source,last:next});}
function apply(){
const row=copy[language];document.documentElement.dataset.sipLanguage=language;document.documentElement.lang=language;
document.querySelector('.home-hero__title')?.setAttribute('aria-label',row.title);document.querySelector('.home-hero__subtitle')?.setAttribute('aria-label',row.subtitle);
for(const [key,value] of Object.entries({title:row.title,subtitle:row.subtitle,big:row.big}))document.documentElement.style.setProperty('--sip-'+key,JSON.stringify(value));
const scopes=document.querySelectorAll('.entry-nav-rail,.home-hero,#app-chrome-file-actions,.image-export-modal,[data-sip-pptx-dialog]');
for(const scope of scopes){const walker=document.createTreeWalker(scope,NodeFilter.SHOW_TEXT);let node;const nodes=[];while(node=walker.nextNode())if(!node.parentElement.closest('[contenteditable],[role="combobox"],textarea,.entry-nav-rail__recent-item')&&(lookup.has(node.textContent)||originals.has(node)))nodes.push(node);for(const node of nodes)translateNode(node);}
for(const node of document.querySelectorAll('button,input,textarea,[role="combobox"],[role="tab"],[role="menuitem"],dialog'))for(const attribute of ['aria-label','placeholder','title','data-tooltip']){const value=node.getAttribute(attribute);if(value&&lookup.has(value)){const next=t(value);if(next!==value)node.setAttribute(attribute,next);}}
}
function setLanguage(value){if(!allowed.includes(value))return;language=value;try{localStorage.setItem('sip:studio-language',value);localStorage.setItem('open-design:locale',value==='de'?'de':'en');localStorage.setItem('open-design:locale-source','manual');}catch{}apply();}
window.addEventListener('message',event=>{if(event.source===window.parent&&event.origin===parentOrigin&&event.data?.type==='sip-studio-language')setLanguage(event.data.language);});
setLanguage(language);
document.addEventListener('DOMContentLoaded',()=>{apply();new MutationObserver(()=>{if(!pending){pending=true;queueMicrotask(()=>{pending=false;apply();});}}).observe(document.body,{childList:true,subtree:true,characterData:true});if(window.parent!==window)window.parent.postMessage({type:'sip-studio-ready'},parentOrigin);});
})();</script>`;
