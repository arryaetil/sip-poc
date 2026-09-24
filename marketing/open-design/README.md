# Open Design — marketing studio spike

## Current SIP integration (24 September 2026)

Open this service through SIP's signed studio link. No separate OpenDesign Cloud
login and no browser API key are required. The gateway supplies the server's
OpenAI key for both `/api/runs` and `/api/chat`. At startup,
`configure-studio.mjs` selects the installed OpenCode runner in the browser;
the upstream Cloud default otherwise asks for the uninstalled Vela program.
The actual run is mapped to `byok-opencode` by the gateway.

Deploy from the repository root with:
`railway up marketing/open-design --path-as-root --service open-design`.
The `--path-as-root` flag is essential to avoid deploying SIP to this service.

The original spike notes below describe the upstream setup; their browser
password/API-key instructions are superseded by the SIP integration above.

A spike, not the marketing studio: it lets marketing colleagues try an
AI design tool in the Etil and ibc group house style, so the decision between
adopting [Open Design](https://github.com/nexu-io/open-design) (Apache-2.0) and
building a smaller studio into SIP rests on their experience.

| | |
|---|---|
| Live | Railway service `open-design` in project `sip-poc` |
| Image | `ghcr.io/nexu-io/od`, pinned by digest (v0.24.0, 22-09-2026) |
| Data | Railway volume `open-design-volume` at `/app/.od` |
| Sign-in | browser prompt: user `open-design`, password = `OD_API_TOKEN` |

## What is added on top of the upstream image

- `design-systems/etil/` and `design-systems/ibc-group/` — house style packages
  written from the official brand guidelines (Etil 2026-07, ibc group 2026-04):
  colours, Ubuntu typography, logo rules, tone of voice and the logos.
- `entrypoint.sh` — refuses to start without `OD_API_TOKEN`, copies the brand
  packages into the data volume on every start, then runs the daemon as the
  image's unprivileged user.

## Security, read before sharing the link

- **One shared password.** Upstream calls the token "single-tenant
  authentication, not user-level access control". Everyone with the password
  has full access, including spending on the configured model key. Share it
  only with the people testing.
- **Model key (BYOK).** Open Design has no model of its own; a user enters an
  API key under Settings. That key pays for every generation. Enter it
  yourself in the UI; never commit it.
- **Generated code runs in a sandboxed preview.** Use test data only until a
  senior has reviewed this.
- Not production. A production marketing studio needs Entra ID sign-in in
  front of it, the key in Key Vault, and an agreed exception to "App Service,
  no containers" (upstream ships `deploy/azure/app-service.bicep`).

## Railway variables

| Variable | Value |
|---|---|
| `OD_API_TOKEN` | random 64 hex characters; the shared password |
| `OD_ALLOWED_ORIGINS` | the service's public URL |
| `OD_DATA_DIR` | `/app/.od` (the volume) |
| `NODE_OPTIONS` | `--max-old-space-size=384` |

Deploy from this folder: `railway up --service open-design`. Always pass
`--service`: the repository root is linked to the `sip-poc` service.
