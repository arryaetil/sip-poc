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

## Home page — "Jouw digitale team" (feature/digitaal-team)

- Home is the default view after sign-in, reachable via "Home" in the sidebar and
  the ibc group logo (the only way back on phones, where the sidebar is hidden).
- Three specialists: Marketing (opens the existing studio view with its signed
  link), Kennisassistent (two actions: Ask ibc group, and Create context), and
  KYC-onderzoeker, a plain link opening the separate KYCX adverse media app
  (https://kycx-adverse-media-production.up.railway.app/) in a new tab. KYCX
  has its own sign-in; SIP passes no session or data to it.
  Actions carry `data-roles` mirroring `_role_allows`; Sales sees the studio and
  create-context actions as unavailable.
- Images: `backend/app/avatars/{marketing,kennis,kyc}.{webp,png}`, 720 px.
- Living robots (`bringRobotToLife` in `app.js`): `<name>-base.webp` is the robot
  with its eyes painted out; the eyes are cut from `<name>.webp` as two layers
  (coordinates in `data-eyes`, on the 1254 px source grid). They follow the
  pointer, blink, wander when idle, glance at neighbours, perk up on hover and
  squint when the robot is tapped. Until both images have loaded, and always with
  "reduce motion", the original still image is shown. New robot images need new
  eye coordinates and a new base image.
- Optional animations: drop `marketing.mp4`, `kennis.mp4`, `kyc.mp4` (square,
  muted, H.264) in the same folder and deploy. `index()` only advertises videos
  that exist; playback stops off-screen, on other views and with reduced motion.
- Ubuntu is now loaded from `backend/app/fonts` (woff2, Ubuntu Font Licence),
  which changes the font across all of SIP, not just Home.

## Product Owner assistant (feature/product-owner, 01-10-2026)

Started by Claude Code, which stopped at its usage limit with an uncommitted
backend skeleton (chat route, a DevOps write without approval checks, models,
prompt, Dify YAML and the avatars) and a Dify app that was never published.
Finished in a second session on the same branch.

What it does: a Product Owner card on Home (roles admin and product_owner) and
a "Product Owner" item in the sidebar open a chat built like Ask ibc group. The
assistant asks one question at a time, shows an editable story proposal
(title, As/I want/so that, entry criteria, acceptance criteria, Fibonacci
points with reason, backlog or sprint, split suggestion for big work) and SIP
creates the User Story in Azure DevOps only after the owner confirmed that
exact version. New stories only; refining or managing existing stories,
Software Developer and OpenCode are not built.

- Code: `backend/app/devops.py` (adapter), routes under `/api/product-owner/*`
  in `main.py`, table `story_drafts` in `store.py`, models in `models.py`,
  prompt `product_owner_prompt.txt`, UI in `index.html`/`app.js`/`i18n.js`.
- Conversations have `kind = product_owner`; they never reach the strategist,
  the portfolio or the knowledge chat. Admins can read them (like all
  conversations) but only the owner can continue, edit or confirm.
- Every model answer or user edit is a new version; confirming sends the
  version on screen plus a confirmation id. One atomic SQLite update claims
  the write, so a double click or retry never writes twice. Statuses: draft,
  ready (shown when complete), creating, created, failed, uncertain.
- A timeout or 5xx after sending is "uncertain": no retry until the check
  button ran a WIQL query (title, created by the token owner, since the
  approval). One match → created; none → failed (confirm again); several →
  stays uncertain. A write stuck in "creating" for 2 minutes becomes uncertain.
- Only the backlog (project root) and current/future sprints of
  `Etil Solutions Team`, read live, are accepted; the model gets that list and
  any other sprint is dropped. No tags, state, assignee or comments are set.
- Azure DevOps (verified 01-10 with the real API): org `EtilSolutions`,
  project `Etil Solutions`, team `Etil Solutions Team`, type User Story,
  fields as in the skill incl. `Custom.EntryCriteria`, default state New, team
  area = project root, current sprint Sprint 28 (22-09 to 12-10).
- Identity: Arrya's PAT (`AZURE_DEVOPS_PAT`, Work Items read & write), so every
  story is created under her name. `SIP_PRODUCT_OWNER_WRITERS` (comma-separated
  SIP emails, empty = nobody) limits who may create; set to Arrya's own SIP
  account only. Drafting works without DevOps or writer rights. Production
  should use an Entra ID identity instead of a PAT.
- Dify: app `SIP — Product Owner (Dify)` `08102bff-059c-463c-aad5-b827fbc6bb0d`,
  `gpt-5.6-terra`, inputs language/history/targets/draft, strict
  `ProductOwnerTurn` schema, no tools or token. Key `DIFY_PRODUCT_OWNER_API_KEY`
  is optional: without it only this chat reports it is unavailable.
  Published by Arrya 01-10 and verified with `difyctl export` (identical to the
  generated YAML).
- Tests: `tests/test_product_owner.py` (23 tests, fake Dify and DevOps):
  roles, ownership, versions, stale confirmation, double click, timeout →
  check, refusal, expired token, closed sprint, invalid model output, missing
  key, separation from other features. Full suite 52 passed.
- Verified for real: DevOps reads (sprints, fields, WIQL), Dify conversation
  (one question at a time, complete draft with the live sprint, split proposal
  for ~21 points), browser check of Home (4 cards, desktop/phone), chat,
  proposal, edit → save required → create disabled, no console errors.
- Test story created with Arrya's approval through SIP's routes:
  **#1800** "[SIP-test] Product Owner-assistent maakt story aan" on the backlog
  (New, 1 point, no tags, unassigned), read back. Not closed or removed.
- The Product Owner robot is alive like the others: `product-owner-base.webp`
  plus `data-eyes="551,298,64;730,353,64"` (measured from the difference with
  `product-owner.webp`). Home always shows three specialists per row; the
  Product Owner starts the second row. Fixed 01-10: the chat-open layout rules
  now include `#product-owner-view`/`#po-chat`, so the conversation scrolls.
- Live: merged to main (ab3fde6), pushed, deployed with `railway up --service sip-poc`,
  deployment fa010e45 SUCCESS on 01-10; /health 200, new app.js served, PO API
  answers 401 without sign-in. Railway variables added: DIFY_PRODUCT_OWNER_API_KEY,
  SIP_PRODUCT_OWNER_WRITERS (= SIP_AUTH_EMAIL). Open Design was not deployed.
- Not verified on production: a signed-in browser run (Arrya's login).
- Since 01-10 (later the same day), the chat covers skill routes A, C and E too:
  - Overviews: the model returns a `query` (sprint, assigned to a person or
    "me", one story); SIP runs it (WIQL, max 200 items) and shows the real
    items grouped by status with links. Results are stored
    (`work_item_results`) and shown to the model in later turns as
    "[Azure DevOps via SIP]" notes.
  - Changes to existing user stories: the model returns a `change` (only the
    fields that change: description as As/I want/so that, criteria, points,
    status, sprint, assignee). SIP reads the story, shows current → new
    (`work_item_changes`, versioned like story_drafts) and writes after
    confirmation with a `/rev` test op. If the story changed meanwhile SIP plans
    again on the new revision and asks for a new confirmation; a timeout is
    uncertain and settled by reading the story. Closed/Removed cannot be
    expressed; Resolved only on explicit request; a warning shows that Active
    assigns the story to the token's account.
  - New stories can be assigned (`assigned_to`); people are resolved against
    the live team member list (display names to the model, accounts stay in
    SIP). Reads and changes are limited to `SIP_PRODUCT_OWNER_WRITERS`.
  - Verified for real (reads only): current sprint, Arrya's work in Sprint 28,
    story #1800, and a change proposal "New → Refinement" for #1800 (not applied).
  - All work item types (01-10, later): user stories, bugs, tasks, features and
    epics can be created and changed. `devops.TYPE_RULES` holds what each type
    has in this project (bug description = repro steps, tasks have remaining
    work instead of points, features/epics use Effort, epics need a priority);
    states are read live per type. Also: priority, parent link ("belongs
    under", an existing parent is replaced), comments (System.History in the
    same /rev-checked write; an uncertain write is checked via the comments
    API), search (title text, type, state, person, sprint or backlog only) and
    the children of an item. Existing tags only. Arrya chose: never Closed or
    Removed via SIP (refused by the server, whatever the model says). Deleting
    is not possible with a Read & write token.
  - SIP strips "As/Als", "I want/wil ik" and "so that/zodat" from the story
    parts (no more "zodat zodat") and says so visibly when it drops a person,
    tag or sprint the model proposed.
  - Not built: route D (implementing a story).
- Not tested: Safari; the uncertain/timeout path against the real DevOps
  (only with fakes); several people at once on Railway.
