# Marketing Studio — eigen Open Design-adapter

Open Studio via de platformknop. Een ondertekende eenmalige link geeft een
beperkte sessie; geen aparte Cloud-login of browser-API-key is nodig. De gateway
gebruikt de bestaande serversleutel voor het model. De daemon luistert uitsluitend
op localhost; alleen de gateway is publiek bereikbaar.

Open Design staat vast op v0.24.0 met een image-digest. Er zijn geen automatische
upstream-updates. [UPDATE-RUNBOOK.md](UPDATE-RUNBOOK.md) beschrijft de versiecontrole,
backup, hersteltest en verplichte echte gebruikerscontrole vóór een wijziging.
De eigen adapter mag veranderen; upstream-code wordt niet gepatcht.

## Deployment

Deploy uitsluitend de geïntegreerde, geteste main vanuit de repositoryroot:

```text
railway up marketing/open-design --path-as-root --service open-design
```

Selecteer expliciet het juiste Railway-project en de productieomgeving. De vlag
`--path-as-root` voorkomt dat de platformapp naar de Studio-service gaat.
`check-release.mjs` draait tijdens de build en controleert vaste versies en lockfile.
Het volume `open-design-volume` staat op `/app/.od` en bevat de projecten en historie.

## Onze toevoegingen

- Officiële Etil- en ibc group-huisstijl, logo's, voorbeelden en Ubuntu-fonts.
- Signed-entry gateway, modelconfiguratie en automatische gedeelde kennis.
- Taaladapter voor NL/EN/DE, grotere previews en betrouwbare bestandsexports.
- PowerPoint als complete ontwerpafbeeldingen óf bewerkbare tekst in een officiële
  brede template. Grafieken en beelden uit het ontwerp worden niet meegenomen in
  de tekstvariant; het exportvenster legt dat uit.
- `entrypoint.sh` bewaart de private bibliotheek bij het vervangen van de publieke
  huisstijlpakketten. Bij een stagingconflict stopt het opstarten.

## Private bibliotheek en toegang

Originele merkrichtlijnen, beelden, LinkedIn-templates en Office-masters staan
alleen op het private Railway-volume onder de huisstijlpakketten in
`assets/private-library/`. Ze horen niet in Git of in het openbare buildcontext.
Nieuwe projecten krijgen alleen de geselecteerde huisstijlbestanden en beelden.

Studio is momenteel een gedeelde werkruimte voor toegelaten platformgebruikers;
het heeft geen bewezen afzonderlijke projectrechten per medewerker. De gateway
vervangt de oude gedeelde browser-passwordroute. Deel geen daemon-token of
modelsleutel met gebruikers. Gegenereerde code draait in een sandboxed preview.
Een vastgepinde image neemt de noodzaak van toegangs- en exportcontroles niet weg.

## Configuratie

Gebruik de bestaande private servicevariabelen, nooit credentials in deze repo:
`OD_API_TOKEN`, `STUDIO_HANDOFF_SECRET`, `SIP_ORIGIN`, `STUDIO_OPENAI_API_KEY`,
`OD_ALLOWED_ORIGINS`, `OD_DATA_DIR` en eventueel `SIP_INTERNAL_URL`.
`OD_API_TOKEN` is een servercredential, geen browserwachtwoord.
De service weigert te starten zonder de vereiste toegangsinformatie.

### Automatic SIP knowledge (8 October 2026)

SIP's own gateway fetches `/api/studio/library` before creating a supported studio project and before every `/api/runs` or `/api/chat` request. The endpoint accepts a timestamped HMAC using the existing `STUDIO_HANDOFF_SECRET`. It exports only approved shared Business Contexts (without the people field or ownership metadata) and the existing reviewed website corpus. Drafts, conversations and uploaded evidence are excluded.

The gateway updates three fixed Markdown files via Open Design's existing JSON files API: `sip/README.md`, `sip/business-contexts.md`, `sip/website-knowledge.md`. The latest snapshot replaces the previous one, including removed/withdrawn contexts. Existing projects refresh at their next generation. The gateway adds a short instruction to read these sources before designing. If fetching or uploading fails, generation does not start against stale knowledge. Nothing in Open Design's own source is patched; the image remains pinned. `sip-library.mjs` belongs to the SIP integration and must ship with `gateway.mjs`.

`SIP_INTERNAL_URL` may optionally point at SIP's private service URL. Without it the adapter uses the existing `SIP_ORIGIN`; no new key is needed. Deploy SIP first, then this service. Verify a direct studio project, an existing project after a context change, and a withdrawn context. Compatibility was checked against the pinned `open-design-v0.24.0` project-file route: JSON `{name, content, encoding}` writes the requested relative file path. Re-run `node marketing/open-design/test-gateway.mjs` before changing the pinned upstream image, then smoke-test the real file API.

