# Handover — SIP POC (Dify provider, knowledge base, Marketing studio)

Written 24-09-2026 for continuing in another agent (Codex). Repository:
`C:\Users\ArryaWillems\source\repos\sip-poc` (GitHub `arryaetil/sip-poc`, branch
`main`). Owner: Arrya (intern); explain technical terms in Dutch, work step by
step, short answers. Login/authentication and entering API keys in web forms are
Arrya's. Arrya has allowed the agent to publish the SIP apps in Dify.

## Two tracks, do not mix

1. **POC** (this repo): Python/FastAPI on Railway. Disposable, may be simple.
2. **Production** (later, with the senior): C#/ASP.NET Core on Azure App Service,
   Azure DevOps, Azure SQL, Foundry IQ. Decisions in `README.md` → "Agreed
   direction"; rules in the `sip-development` skill (branches `feature/<name>`
   from main, never commit on main, max two deploys a day in Azure, managed
   identity, no keys except Dify via Key Vault).

## What is live

| Piece | Where |
|---|---|
| SIP app | Railway project `sip-poc`, service `sip-poc`, https://sip-poc-production.up.railway.app |
| Open Design (Marketing studio) | service `open-design`, https://open-design-production-3762.up.railway.app (gateway; 401 without SIP link) |
| Assistant provider | `SIP_ASSISTANT_PROVIDER=dify` in Railway |
| Dify | Dify Cloud workspace `beheer@etil.nl`, Sandbox plan |

Railway does **not** auto-deploy from GitHub. Deploy with `railway up`:
- SIP: `railway up --service sip-poc` from the repo root.
- Open Design: `railway up marketing/open-design --path-as-root --service open-design`.
  Without `--path-as-root` Railway uploads the whole repo and runs SIP there.
- Git Bash rewrites paths like `/app/.od`; prefix with `MSYS_NO_PATHCONV=1`.
- No `gh` CLI on the laptop: merge feature branches locally with `--no-ff`, push.

## Architecture (POC)

- `backend/app/assistants.py` — one `Assistant` interface, `FoundryAssistant` and
  `DifyAssistant`, chosen at startup; fails closed without keys. SIP owns all
  conversation history and sends it as `history` input (Dify memory off,
  truncated at 95,000 characters).
- `dify/build_apps.py` — generates the three Dify apps from SIP's prompt files and
  Pydantic models (strict JSON schemas). Import with
  `difyctl import studio-app -f dify/<app>.yml --app-id <id>`, then **publish in
  the Dify editor** (refresh the editor tab first).
  - Strategist `516e0f3c-866c-42d3-92fb-db0a2b04d0e4` — gpt-5.6-terra
  - Finalizer `f7d3e6a6-aa5c-4159-93b9-2893b6a8a414` — gpt-5.6-terra
  - Knowledge `e1950fd4-7d7e-4840-be5d-e27b71cf6922` — query rewrite on gpt-5-mini
    (node id `query_rewrite`), answers on gpt-5.6-luna, hybrid retrieval 0.7/0.3,
    top 12, threshold 0.4, owner metadata filter.
- Knowledge base `SIP — ETIL corpus (3-large)` `cc833d3d-e595-41c7-a7ca-1bc1c5b7decd`,
  text-embedding-3-large via Arrya's OpenAI key in Dify.
  - Corpus: `dify/sync_corpus.py` (one chunk per `##` section; Dify ignores
    process_rule on update).
  - Permissions: metadata field `owner` (`4db261db-d0f7-4c92-a5fe-15cb3e02ee70`),
    `public` or sha256(user id)[:24]. Contexts and uploads are synced on
    save/approve/delete. Backfill: `railway ssh --service sip-poc -- sh -c "cd /workspace/backend && python -m app.reindex"`.
  - Leak test passed (private doc invisible to another user).
- Knowledge chat UI: source viewer panel for uploads/contexts; web sources link out.
- Eval: `SIP_ASSISTANT_PROVIDER=dify python dify/eval_knowledge.py` (22 questions,
  last run 22/22 retrieval, median 6 s). Same set is meant for Foundry IQ later.

### Marketing studio (Open Design) — just built, needs end-to-end verification

- `marketing/open-design/`: Dockerfile pinned by digest, Etil and ibc group design
  systems (from the brand guidelines in `C:\Users\ArryaWillems\source\ibc-huisstijl`),
  `metadata.json` status `published` (drafts cannot be used by projects),
  Ubuntu fonts, LinkedIn examples.
- `gateway.mjs`: daemon on 127.0.0.1:7456; gateway on Railway's port admits the
  daemon token (SIP backend over `open-design.railway.internal:8080`) or a cookie
  from `/__sip/enter?t=<signed>` (HMAC with `STUDIO_HANDOFF_SECRET`, 120 s). Sets
  `frame-ancestors` to SIP. Cookie `SameSite=None; Secure; Partitioned`.
- SIP: `backend/app/studio.py`, endpoints `GET /api/studio/link` and
  `POST /api/studio/projects`; the knowledge app returns `marketing_request`
  (format linkedin_post | one_pager | presentation, brief, title, brand); the chat
  shows "Verder in de Marketing studio?" and opens the Marketing studio view
  (iframe) with the prepared project (`context.md` + pending prompt).
- Verified: gateway denies without link (401), accepts signed link (302 + cookie),
  project creation with `user:etil` and `context.md` works via the API.
- Verified since (24-09, ~12:00): the published knowledge app returns
  `marketing_request` (presentation / linkedin_post recognised, none for plain
  questions); the studio embeds in SIP in Chrome (Arrya saw it); an end-to-end run
  (`marketing/open-design/e2e_test.py`) produced a LinkedIn post HTML + post text
  from `context.md`, matching the Etil template pattern.
- **Model key is server-side**: Open Design normally keeps the BYOK key in each
  browser. The gateway rewrites every `POST /api/runs` to `agentId: byok-opencode`
  with `byokProvider = {protocol: openai, apiKey: STUDIO_OPENAI_API_KEY, model:
  STUDIO_MODEL (gpt-5.6-terra)}`. Marketers enter nothing. The entrypoint also
  exports the key as `OD_OPENAI_API_KEY` for image generation.
- The image bundles the OpenCode CLI (`opencode-ai@1.18.32`); the BYOK runtime
  needs it. `HOME` for the daemon is `/app/.od/home`.
- `studio.create_project` copies the design system's `assets/` and `fonts/` into
  the project's `brand/` folder (the model otherwise has no logo or font files).
- Status 24-09 12:20 (after Codex's `configure-studio.mjs` fix, which seeds the
  browser runner to OpenCode and maps `/api/chat` too):
  - ✅ Ubuntu loads (fonts copied to `brand/fonts/`), approved image used, AI
    label bottom right, logo no longer cropped, text grounded in `context.md`.
  - `brand/logo.svg` (493 bytes) is created by Open Design itself
    (`design-systems/index.ts`), not by the model, and is unused. Harmless.
    It lands in the design system's `assets/` on the volume, so
    `studio._copy_brand_assets` copies it along; skip `assets/logo.svg` there.
  - Verified 12:21: after deploy `b5f866ec` the stale claim-only SVG is gone and
    `assets/etil-logo-lockup-white.png` is present.
  - ❌ → fix deployed, **not yet verified**: `etil-logo-slogan-white.svg` held only
    the claim without the "Etil" wordmark. Added `etil-logo-lockup-white.png`
    (official "Etil logo white with claim"), renamed the old file to
    `etil-claim-only-white.svg`, and `entrypoint.sh` now deletes old package
    files on start (they lingered on the volume). Deploy `b5f866ec` was building.
  - **Next**: rerun `cd backend && python ../marketing/open-design/e2e_test.py`,
    check the post HTML uses `brand/etil-logo-lockup-white.png`, and view it via
    `studio.signed_link('e2e-test', '/api/projects/<id>/raw/<file>.html')` (set
    `OPEN_DESIGN_INTERNAL_URL` to the public URL when running locally).
- Unused brand material worth adding next: PowerPoint masters
  (`C:\Users\ArryaWillems\source\ibc-huisstijl\extra3\Powerpoint Master\`),
  claim posts ("connecting insights to impact" / "connecting performance"
  folders under `extra1\LinkedIn Templates\Posting Templates\`), 2–3 more LinkedIn
  examples per domain, LinkedIn profile banners. Creative Commons images need
  attribution: leave them out.
- Not tested: Safari (use "Open in new tab"), one-pager and presentation formats,
  PPTX export.

## Railway variables (names only)

- `sip-poc`: SIP_AUTH_*, SIP_SESSION_SECRET, SIP_ASSISTANT_PROVIDER,
  DIFY_{STRATEGIST,FINALIZER,KNOWLEDGE,DATASET}_API_KEY, OPEN_DESIGN_TOKEN,
  OPEN_DESIGN_INTERNAL_URL, OPEN_DESIGN_PUBLIC_URL, STUDIO_HANDOFF_SECRET,
  AZURE_* (Arrya's personal Foundry keys; she wants them removed eventually).
- `open-design`: OD_API_TOKEN, STUDIO_HANDOFF_SECRET, SIP_ORIGIN,
  OD_ALLOWED_ORIGINS, OD_DATA_DIR=/app/.od, NODE_OPTIONS, STUDIO_OPENAI_API_KEY,
  STUDIO_MODEL. Volume at `/app/.od`. Setting a variable redeploys the *last
  built image*; code changes need `railway up … --path-as-root`.
- Local copies of the secrets: `backend/.env` (gitignored). Never print them.

## Known pitfalls

- Opening the Dify editor can overwrite a `difyctl` import with a stale copy;
  gpt-5.6 rejects `reasoning_effort: minimal` (valid: none|low|medium|high|xhigh|max).
  Always `difyctl export` after publishing to check.
- Sandbox limits: ~10 knowledge-base requests/minute (every chat question counts),
  50 documents per workspace (corpus uses 32).
- Windows: files may get CRLF; `.sh`/`.mjs` in `marketing/open-design` are forced LF.

## Next steps

1. Publish the knowledge app, then ask in Ask ibc group "Maak een PowerPoint over de
   WoonAtlas voor gemeenten" → expect the studio card → Yes → studio opens the project.
2. Test in Chrome/Edge (embedded) and Safari (use "Open in new tab").
3. Remove Open Design's direct access beyond the gateway is already done; consider
   hiding the public domain entirely once only the iframe is used.
4. Run the marketing test with colleagues: `marketing/open-design/GESPREK-MARKETING.md`.
5. Open items: evidence stays public after its context is deleted (SIP rule says it
   should become private); Finalizer writes fields in English; occasional wrong
   answer language; extra source chips.
