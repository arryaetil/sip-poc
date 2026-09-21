# SIP — Solution Intelligence Platform

SIP is a multilingual proof of concept for ibc group / ETIL. Sales and product users build a structured Business Context through a guided conversation, work with private documents, browse approved portfolio items, and ask a grounded knowledge assistant questions.

| | |
|---|---|
| Live | https://sip-poc-production.up.railway.app — deployment `82552912`, running |
| Stack | Python 3.13, FastAPI, vanilla JavaScript, SQLite, Azure AI Foundry |
| Languages | English, Nederlands, Deutsch |
| Hosting | Railway project and service `sip-poc`, persistent volume mounted at `/data` |

> [!IMPORTANT]
> **Target knowledge architecture: Microsoft Foundry IQ.** The local lexical/vector
> index in this repository is a temporary POC implementation, not the intended
> production architecture. SIP will migrate to a Foundry IQ knowledge base for
> managed, reusable and permission-aware retrieval. Foundry IQ is backed by Azure
> AI Search, so indexing still exists, but SIP will no longer build, store or query
> its own vector index. Do not extend the custom index beyond what is needed to keep
> the POC working. See [MIGRATION.md](MIGRATION.md) and the
> [Azure target architecture](docs/AZURE_TARGET_ARCHITECTURE.md). For the technical
> review, use the concise [minimum Azure resources checklist](docs/AZURE_MINIMUM_RESOURCES.md).

## Current experience

Both Create context and Ask ibc group open on a central prompt composer with their own conversation history directly underneath. Create context asks which Business Context the user wants to create; Ask ibc group asks what the user wants to work on. Starting or opening either type switches immediately to a full-workspace chat while the response loads. The context chat omits the redundant page header, subtitle and disabled save action; Save to portfolio only appears with the readiness state once the context can actually be prepared. New assistant answers reveal progressively with a short typing cursor; restored history renders immediately and reduced-motion disables the effect. Context intake handles greetings and corrections naturally, does not expose missing-field pressure until the context is ready, and never treats the bundled website corpus as user-uploaded evidence. Translucent “Liquid Glass” materials are used selectively on the launcher and chat controls, with high-contrast and reduced-motion fallbacks.

There are two persistent conversation types:

- `context`: guided Business Context intake, conversational document analysis, review and approval.
- `knowledge`: organisation knowledge chat with saved message history and source visibility.

Conversations and draft contexts belong to one user. Other users receive `404` for private object IDs. Approved contexts and explicitly published evidence are organisation-wide; administrators can inspect all records. Legacy rows are assigned to the configured bootstrap account during the idempotent startup migration and are never implicitly public.

## Documents and retrieval

PDF and DOCX uploads are supported. Files are limited to 10 MB and PDFs to 200 pages. Workspace documents remain private to their owner. Context evidence also remains private until the related Business Context is approved and the reviewer leaves that document selected for publication.

For context evidence, the model reads the uploaded document as untrusted business evidence and brings the relevant knowledge back into the conversation in its own words. It highlights three to five useful insights, connects them to the emerging Business Context, calls out uncertainty and asks at most one useful follow-up question. There are no proposal cards or Accept/Ignore actions. The resulting discussion is saved in the conversation and informs the final review.

The current POC knowledge assistant uses hybrid lexical/vector retrieval when a local embedding index is available and falls back to lexical retrieval otherwise. Visibility is filtered before ranking. Reciprocal-rank-fusion results below `SIP_RELEVANCE_THRESHOLD` do not ground an answer; the UI shows the closest matches without offering a separate general-answer mode. Knowledge follow-ups are reconstructed from stored messages instead of relying on provider-side response IDs. Enter sends from every chat composer and start screen; Shift+Enter inserts a new line.

The bundled `knowledge/markdown` corpus is a reviewed snapshot of public ETIL and ibc group pages. Uploads are indexed incrementally and removed from the index when deleted.

## Architecture

```mermaid
flowchart LR
    B[Browser SPA] --> A[FastAPI]
    A --> D[(SQLite /data/sip.db)]
    A --> U[Uploads /data/uploads]
    A --> V[Local lexical/vector index]
    A --> F[Azure AI Foundry]
    D & U & V --> R[Railway persistent volume]
```

The frontend is plain JavaScript and CSS with no build step. FastAPI serves the UI, API and public `/health` endpoint. SQLite, uploads and the vector index live on the same persistent volume, so production must remain a single replica until storage is moved to shared services.

### Target Azure knowledge architecture

```mermaid
flowchart LR
    B[Browser] --> A[SIP application]
    A --> G[Foundry agent or application orchestration]
    G --> IQ[Foundry IQ knowledge base]
    IQ --> KS[Managed knowledge sources]
    KS --> BL[Azure Blob Storage]
    KS --> WK[Approved organisational knowledge]
    IQ --> AS[Azure AI Search agentic retrieval]
```

Foundry IQ becomes the reusable knowledge layer for SIP. It owns knowledge-source
ingestion and retrieval through Azure AI Search. The application continues to own
the Business Context workflow, approvals and presentation. The existing
`retrieve()` boundary should be preserved until the Foundry IQ integration is
validated, so the POC can migrate without rewriting the chat workflows.

## Repository

```text
backend/app/
  main.py       routes, auth, chat orchestration and migrations
  store.py      SQLite persistence and ownership rules
  retrieval.py hybrid retrieval, visibility filtering and diagnostics
  uploads.py    upload validation and PDF/DOCX extraction
  app.js        single-page application
  styles.css    responsive UI and glass materials
knowledge/      bundled source corpus
tests/          ownership/workspace regression tests
Dockerfile      production image
railway.json    Railway build, healthcheck and restart policy
```

## Main API

| Area | Endpoints |
|---|---|
| Authentication | `POST /api/auth/login`, `POST /api/auth/logout`, `GET /api/auth/me` |
| Users | `GET/POST /api/users`, `PUT/DELETE /api/users/{id}` |
| Conversations | `GET/POST /api/conversations`, `GET/DELETE /api/conversations/{id}`, message and portfolio routes |
| Contexts | `GET/POST /api/contexts`, `GET/PUT/DELETE /api/contexts/{id}`, `POST /api/contexts/prepare` |
| Uploads | `GET/POST /api/uploads`, `GET/DELETE /api/uploads/{id}`, `POST /api/uploads/{id}/discuss` |
| Knowledge | `POST /api/knowledge/chat` |
| Portfolio | `/api/portfolio/solutions`, `/api/portfolio/sources` and source detail |
| Operations | public `GET /health` |

FastAPI documentation is available at `/docs` after login.

## Configuration

Copy `.env.example` to `.env`; never commit real secrets.

| Variable | Purpose |
|---|---|
| `AZURE_AI_PROJECT_ENDPOINT`, `AZURE_AI_API_KEY` | Azure AI Foundry connection |
| `MODEL_DEPLOYMENT` | Chat model deployment, default `gpt-5-mini` |
| `EMBEDDING_DEPLOYMENT` | Embedding deployment for hybrid retrieval |
| `SIP_DB_PATH` | SQLite path; production uses `/data/sip.db` |
| `SIP_UPLOAD_ROOT` | Upload directory; defaults beside the database |
| `SIP_VECTOR_PATH` | Persistent vector index path |
| `SIP_RETRIEVAL` | `lexical` or `hybrid` |
| `SIP_RELEVANCE_THRESHOLD` | Minimum fused relevance score, default `0.017` |
| `SIP_AUTH_EMAIL`, `SIP_AUTH_PASSWORD`, `SIP_AUTH_ROLE` | Bootstrap account |
| `SIP_AUTH_EXTRA_USERS` | JSON map of additional demo accounts |
| `SIP_SESSION_SECRET`, `SIP_COOKIE_SECURE` | Signed cookie configuration |
| `PORT` | HTTP port; Railway injects this value |

## Local development

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r backend/requirements.txt
Copy-Item .env.example .env
Set-Location backend
uvicorn app.main:app --reload --port 8000
```

Run the checks from the repository root:

```powershell
$env:PYTHONPATH='backend'
python -m pytest tests -q
node --check backend/app/app.js
```

## Deployment

The production service currently receives explicit CLI deployments from this repository. GitHub is the source of truth, but Railway is not configured for automatic deploy-on-push.

```powershell
railway link --project e0e06291-87e2-4b51-b83d-392ae919f448
railway up --service sip-poc --detach
```

`railway.json` declares the Dockerfile build, `/health` deployment healthcheck and restart-on-failure policy for a future source-connected deployment. The current CLI-uploaded service is healthy, but Railway does not apply the file-level healthcheck to this deployment method. The image starts through a JSON-form command so signals reach the Python process correctly.

## Known limitations

- The current retrieval implementation is transitional and will be replaced by a Foundry IQ knowledge base before production.
- SQLite and the local index require a single application replica.
- Scanned/image-only PDFs are not OCR'd.
- Upload/index mutation is intended for POC traffic; it does not yet use distributed locking.
- Demo environment credentials and user lifecycle need hardening before customer production use.
- The public `/health` endpoint returns OK, but the current CLI-uploaded Railway service has no platform healthcheck configured; set it in Railway or connect the GitHub source so `railway.json` is applied.

Last documentation review: **16 September 2026**.
