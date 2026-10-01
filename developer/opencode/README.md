# Software developer via OpenCode

Deze eerste omgeving is voor **één** SIP-account. De kaart op de SIP-homepage opent OpenCode in een nieuw tabblad. OpenCode beheert zelf gesprekken, terminal en bestanden; SIP bouwt geen programmeerchat en stuurt geen SIP-, Marketing- of Azure DevOps-gegevens door.

## Versie en keuze

`opencode-ai@1.18.34` staat vast in de Dockerfile. De officiële [v1-webdocumentatie](https://dev.opencode.ai/docs/web/) beschrijft `opencode web` met HTTP Basic Auth en de [serverdocumentatie](https://dev.opencode.ai/docs/server/) dezelfde wachtwoordinstelling. [V2](https://opencode.ai/v2/docs/cli/web) is beschikbaar, maar gebruikt een ander koppelproces met eigen eenmalige links en sessies. Die twee aanmeldmethoden zijn niet vermengd. Een overstap naar v2 vraagt een afzonderlijke controle van de poort en browserstromen.

De browser krijgt van SIP een HMAC-ondertekende link (120 seconden). De poort registreert het unieke linknummer op de blijvende schijf en accepteert het één keer. Daarna zet zij een eigen `Secure`, `HttpOnly`, `SameSite=Strict` cookie voor twaalf uur. Ze antwoordt met een korte pagina die zelf doorgaat naar OpenCode, niet met een doorverwijzing: de klik begint op SIP (een andere site) en een browser stuurt een `SameSite=Strict`-cookie bij geen enkel verzoek van die navigatie mee, ook niet na een doorverwijzing. Met een doorverwijzing zag je daardoor de weigering "Open Developer vanuit SIP." Die cookie draagt het kenmerk `typ: session`: een link wordt nooit als cookie geaccepteerd en een cookie nooit als link, zodat een link uit de adresbalk of geschiedenis de eenmalige controle niet kan omzeilen. De poort weigert verzoeken zonder sessie, controleert de herkomst van schrijvende verzoeken en voert HTTP, streaming antwoorden en WebSockets door. OpenCode luistert uitsluitend op `127.0.0.1:4096`; de poort luistert op Railway's `PORT`. De poort geeft OpenCode's lokale serverwachtwoord alleen in de interne verbinding mee.

OpenCode draait als gebruiker `developer` (UID 10001). De container heeft geen SIP-code, SIP-data, Marketing-bestanden, DevOps-token, Docker-socket of hostkoppeling. Bewaar geen vertrouwelijke ETIL-data in deze POC.

## Geheime en gewone instellingen

| Service | Railway-instellingen |
|---|---|
| `sip-poc` | `SIP_DEVELOPER_EMAIL`, `OPENCODE_DEVELOPER_PUBLIC_URL`, `DEVELOPER_HANDOFF_SECRET` |
| `opencode-developer` | `DEVELOPER_HANDOFF_SECRET`, `DEVELOPER_PUBLIC_URL`, `OPENCODE_SERVER_PASSWORD`, `OPENAI_API_KEY` |

`SIP_DEVELOPER_EMAIL` is de exacte SIP-accountnaam die toegang krijgt. Beide services gebruiken hetzelfde `DEVELOPER_HANDOFF_SECRET`. `OPENAI_API_KEY` is een **aparte** sleutel voor Developer; vul die zelf in bij Railway. Bewaar alle waarden als Railway-variabelen. Zet ze niet in Git, chat of terminaluitvoer. `.env` en `.env.*` worden door Git genegeerd.

## Opslag

Koppel een eigen Railway-volume aan `opencode-developer` op `/data`. Projectbestanden staan in `/data/projects`. OpenCode bewaart via `HOME` en `XDG_*` gesprekken, instellingen en providergegevens onder `/data/home`. De poort bewaart gebruikte linknummers onder `/data/used-links`. Zonder volume gaan gesprekken en projecten bij een nieuwe uitrol verloren. De volume-inhoud moet bij een back-up worden meegenomen.

## Installatie en uitrol

1. Controleer de bestaande services in het Railway-project `sip-poc`. Maak alleen als hij ontbreekt een service `opencode-developer` en een eigen volume op `/data`.
2. Stel de bovengenoemde variabelen in. Gebruik een nieuw willekeurig ondertekeningsgeheim en een ander, willekeurig intern OpenCode-wachtwoord. De Developer-URL moet HTTPS gebruiken.
3. Draai vanuit de repo-root ` $env:PYTHONPATH='backend'; python -m pytest -q tests `.
4. Rol **alleen de Developer-map** uit: `railway up developer/opencode --path-as-root --service opencode-developer`. Controleer vooraf dat `--path-as-root` de bouwcontext tot die map beperkt; zonder die optie kan SIP op de verkeerde service terechtkomen.
5. Controleer de Developer-poort zonder sessie (401) en de gezondheid op `/__sip/health`. Rol SIP vanuit de repo-root uit: `railway up --service sip-poc`.
6. Meld je bij SIP aan met de ingestelde accountnaam. Klik **Software developer** → **Open OpenCode**. Stel de aparte `OPENAI_API_KEY` in voordat je een modelopdracht probeert. Maak een klein testproject, laat OpenCode een bestand schrijven, herstart de Developer-service en controleer bestand én gesprek. Test ook een tweede SIP-account, een verlopen en een gewijzigde link, rechtstreeks openen, voortgang en terminal.

Railway deployt niet automatisch vanaf GitHub. Wijzig of deploy `open-design` niet.

## Gegevens en grenzen

De OpenCode-webinterface wordt door de eigen server aangeboden. De modelaanvraag verstuurt prompt, relevante projectbestanden en tooluitvoer naar OpenAI via de aparte sleutel. OpenCode kan ook modelmetadata ophalen; controleer in de live browser of er aanvullende externe webverzoeken zijn. Deelopties of extra providers zijn hier niet geconfigureerd. Een gedeelde OpenCode-server biedt geen gebruikersscheiding; geef dus geen tweede account toegang tot deze service. Automatisch publiceren en een geïntegreerde live app-preview zijn geen onderdeel van deze versie.

## Controle

De Python-tests controleren SIP-aanmelding, het exacte account, ontbrekende configuratie, de linkvorm en de homepage: 77 tests geslaagd voor de gecombineerde main-code. `node developer/opencode/test-gateway.mjs` test de werkelijke poort met een nagebootste OpenCode-server op directe toegang, verlopen/aangepaste/hergebruikte links, een link als cookie, cookies en herkomst. Online zijn beide services gezond; rechtstreekse Developer-toegang en een SIP-link zonder aanmelding leveren 401. In de Developer-container gaf een ondertekende link 303, daarna de OpenCode-webpagina 200, en hergebruik 401. Een leeg bestand in `/data/projects` bleef na een nieuwe Developer-uitrol bestaan. Een werkende modelopdracht, browserterminal en bewaard OpenCode-gesprek kunnen pas na het instellen van de aparte `OPENAI_API_KEY` worden bevestigd.
