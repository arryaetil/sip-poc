# Open Design veilig bijwerken

## Wat nu vaststaat

Open Design wordt niet automatisch bijgewerkt. `Dockerfile` verwijst naar één
onveranderlijke image-digest; `release-lock.json` legt dezelfde release vast.
OpenCode heeft een exact versienummer. De eigen npm-dependencies hebben exacte
versies en integriteitshashes in `package-lock.json`.

`node check-release.mjs` controleert dit vóór installatie in elke Docker-build.
Dezelfde controle draait in de GitHub-workflow bij relevante wijzigingen. Een
afwijking stopt de build. Een bewuste update wijzigt Dockerfile én baseline in
een gereviewde featurebranch. Deze controle bewijst geen API-compatibiliteit.

Chromium en de lettertypepakketten komen nog uit de Alpine-pakketbron: een nieuwe
build kan daarvan een andere versie installeren. Bewaar daarom de werkende
Railway-deployment om terug te rollen en herhaal de echte exportcontroles bij
een rebuild. Alleen dezelfde upstream-digest is geen bewijs van identieke exports.

Alle aanpassingen staan in onze adapter, niet in upstream-code. Selectors, API's,
de daemon-database en het private volume kunnen bij een upstream-update veranderen.

## Voor een bewuste upstream-update

1. Noteer de huidige commit, beide werkende Railway-deployments, image-digest,
   OpenCode-versie en de versies uit de buildlogs. Lees de upstream release notes.
2. Maak een consistente, versleutelde backup van het complete `/app/.od`-volume
   met de daemon gestopt of een gedocumenteerde consistente snapshotprocedure.
   Neem database, projecten, versiehistorie, `home`, gebruikte inloglinks en beide
   `assets/private-library`-mappen mee. Dat laatste bevat de officiële Office-masters.
   Bewaar de backup privé, buiten Git en buiten het openbare buildcontext.
3. Bewijs herstel op een aparte private kopie: lees projecten en geschiedenis en
   controleer de hashes van beide masters. Een gemaakte backup zonder hersteltest
   is nog geen bewezen terugweg. Noteer tijdstip en resultaat.
4. Test de kandidaat in een afzonderlijke omgeving met een afzonderlijk volume.
   Laat die nooit op het productievolume starten. Gebruik QA-bronnen en een
   afzonderlijke sleutel/configuratie; laat authenticatie en localhost-isolatie
   intact. Kopieer geen productiecredentials naar een onbeveiligde testomgeving.
5. Werk alleen de eigen Dockerfile/baseline/adapter bij op een featurebranch vanaf
   actuele main. Patch geen upstream-code. Draai onderstaande controles.
6. Integreer vanaf een nieuw gemaakte integration-branch uit main, test, merge naar
   main en deploy uitsluitend main. Verwijder de integration-branch en ververs
   onze open featurebranches. Dit volgt de lokale development-skill.

## Verplichte controle van de kandidaat

Automatisch, vanuit de repositoryroot:

```text
node marketing/open-design/check-release.mjs
node marketing/open-design/test-gateway.mjs
node marketing/open-design/test-export.mjs
node marketing/open-design/test-language.mjs
```

Voor de browsertests moet `STUDIO_CHROMIUM_PATH` naar de geïnstalleerde Chromium
wijzen. Gebruik de bestaande native-exportcontrole met de private officiële
masters en valideer alle PPTX-relaties; publiceer die masters niet in Git.
De gatewaytest gebruikt een fake daemon: voer daarom ook onderstaande echte
gebruikerscontrole uit op de kandidaat, niet alleen op de huidige release.

- Niet ingelogd: Studio weigert toegang. Ingelogd via de platformknop: eenmalige
  entree en sessie werken, ook ingebed. Een gebruikte link kan niet opnieuw inloggen.
- Nieuw project en bestaand project: officiële huisstijl/assets, juiste provider,
  generatie én vervolgchat werken. Test JSON-file-write en multipart asset-upload,
  raw bestanden, streaming van `/api/runs` en `/api/chat` tegen de echte daemon.
- Kennis: goedgekeurde context en websitekennis worden vernieuwd; ingetrokken
  context verdwijnt. Bij onbereikbare kennisbron wordt generatie geblokkeerd.
  Privéconcepten en geüpload bewijs verschijnen niet in de gedeelde Studio-bibliotheek.
- NL/EN/DE wisselen zonder ontwerp, caption, projectnaam of lopende invoer te verliezen.
- Bekijk alle zes carouselpagina's en één enkele post op klein én groot formaat.
  Controleer volledige logo's, contrast, paginateller, vooruit/terug en sluiten.
- Download werkelijk PNG/JPEG/WebP, ZIP, PDF, HTML en beide PowerPoint-keuzes.
  Open de fysieke bestanden: aantal pagina's, afmetingen, beeld en tekst moeten
  kloppen. De template-export moet echt bewerkbare tekst bevatten; de ontwerp-export
  bevat afbeeldingen per dia. Controleer beide merken en historische versies.
- Herstart de kandidaat: projecten, bestanden, historie, private masters en
  providerinstelling blijven aanwezig. Bekijk logs zonder credentials te publiceren.

## Terugrollen

Bij een fout vóór productie: stop de kandidaat; productie blijft op de bewezen
deployment en het eigen volume. Bij een fout ná productie: gebruik de vorige
Railway-deployment. Heeft upstream het gegevensschema gemigreerd, dan is alleen
de oude image terugzetten niet voldoende: herstel de bewezen backup terwijl de
daemon gestopt is. Houd rekening met wijzigingen sinds die backup; vergelijk en
bewaar nieuwe projecten privé voordat je een herstel uitvoert.

## Status op 8 oktober 2026

De huidige upstream-digest is niet gewijzigd. De baselinecontrole is lokaal
uitgevoerd; de build voert hem opnieuw uit. Er is bij deze wijziging geen nieuwe
volume-backup of hersteltest gedaan. Dit document is de verplichte procedure voor
een toekomstige upstream-update, geen verklaring dat die update al is getest.
