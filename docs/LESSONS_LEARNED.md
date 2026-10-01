# Lessons learned in the POC — read before building SIP on Azure in C#

Every problem below cost real time in the Railway POC. Each entry says what went
wrong, why, what the POC does now, and what it means for the Azure/C# build. Use it
as a checklist when you configure the production version: most of these are not
Python- or Railway-specific, they come back in any stack.

Keep it updated. Add a lesson the day you learn it; write the symptom as you saw it,
because that is what the next person will search for.

Related: [MIGRATION.md](../MIGRATION.md) (POC shortcuts and what replaces them),
[AZURE_TARGET_ARCHITECTURE.md](AZURE_TARGET_ARCHITECTURE.md),
[AZURE_PROVISIONING.md](AZURE_PROVISIONING.md), [HANDOVER.md](../HANDOVER.md).

Last updated: 1 October 2026.

---

## 1. Configuration and secrets

**Fail closed at startup.** A half-configured provider used to surface as random
500s per request. SIP now refuses to start when the selected assistant provider has
no keys (`main.py`, `assistants.py`); the studio and developer gateways refuse to
start without their token, signing secret and allowed origin (`entrypoint.sh`).
→ **Azure/C#:** validate options at startup (`ValidateOnStart()` on options
classes) so a missing Key Vault reference stops the deployment slot instead of
reaching users.

**Changing a variable does not ship code.** On Railway, setting a variable redeploys
the *last built image*. Code changes only arrive with a new build.
→ **Azure/C#:** App Service app settings behave the same way (restart, same
build). Keep configuration changes and code releases as separate, visible steps in
the pipeline.

**Keys tied to a person.** The Azure DevOps PAT and the Foundry keys on Railway are
Arrya's personal credentials; every work item SIP creates shows her as the author.
→ **Azure/C#:** user-assigned managed identity (`id-sip-dev-weu`) for Azure
services; an Entra ID identity for Azure DevOps. Decide up front whether writes
should appear as "SIP" or as the signed-in user (on-behalf-of).

**Never read or print secrets.** Secrets live in `backend/.env` (git-ignored) and
platform variables. Production smoke tests ran *inside* the containers, using the
container's own environment variables, so tokens never appeared in a terminal or a
log. → **Azure/C#:** Key Vault references only; never log option values; run
smoke tests from inside the environment (pipeline job with the managed identity).

---

## 2. Repository, branches and deploys

**Two sessions in one checkout.** On 01-10 another agent created and checked out a
branch in the same folder while work was in progress; a commit landed on the wrong
branch and a merge silently did nothing. → Check the current branch right before
every commit and merge. Give every parallel stream its own git worktree.

**Never commit on `main`.** A direct commit on main happened once by accident.
Feature branch from main, merge with `--no-ff`. The production rule (Azure DevOps,
integration branch, max two deploys a day behind an approval) is in
README.md → [Agreed direction](../README.md#agreed-direction).

**One build context per service.** `railway up` from a subfolder uploaded the whole
repository; the Open Design service then ran SIP. Fix:
`railway up marketing/open-design --path-as-root --service open-design`.
→ **Azure/C#:** one pipeline (or stage) per deployable, each with an explicit
build context and Dockerfile path; check the image that actually runs after the
first deploy.

**No auto-deploy.** Railway does not deploy from GitHub; what runs is whatever was
last uploaded by hand. → **Azure/C#:** deploy only from the pipeline, so "what is
live" always equals a commit on main.

**Windows tooling traps.**
- Git Bash rewrites arguments that look like paths (`/app/.od` became
  `C:/Program Files/Git/app/.od`). Prefix with `MSYS_NO_PATHCONV=1`.
- Files get CRLF line endings; shell scripts with CRLF fail inside Linux
  containers. `.sh`/`.mjs` in `marketing/open-design` and `developer/opencode` are forced to LF
  with `.gitattributes`.
- `railway ssh` loses quotes and parentheses. Workaround: send a script as base64
  (`echo <b64> | base64 -d > /tmp/x.mjs && node /tmp/x.mjs`).
→ **Azure/C#:** run build and deploy steps on Linux pipeline agents, not on a
laptop; add `.gitattributes` from day one.

---

## 3. The AI provider seam

**Keep one interface.** `assistants.py` defines one `Assistant` protocol with a
Foundry and a Dify implementation, chosen at startup with
`SIP_ASSISTANT_PROVIDER`. Nothing outside it knows which provider runs. This is what
made the Dify vs Foundry comparison possible. → **Azure/C#:** an `IAssistant`
interface registered in DI; provider-specific types never leave the adapter.

**SIP owns the conversation.** Provider memory is off; SIP stores the history and
sends it with every call, truncated at 95,000 characters (`HISTORY_LIMIT`). This
keeps conversations portable between providers and auditable in SIP's own
database. → **Azure/C#:** keep history in Azure SQL, not in agent threads.

**Structured output must be strict, also for nested objects.** Pydantic schemas are
converted to strict JSON schemas (`_make_strict` in `dify/build_apps.py`): every
object, including nested ones, needs `additionalProperties: false` and all
properties in `required`. Missing this on a nested object makes the model API
reject the schema. → **Azure/C#:** the same rule applies to schemas generated from
C# records; test the generated schema against the model once per change.

**Model parameters differ per model family.** gpt-5.6 rejects
`reasoning_effort: minimal` (valid: none, low, medium, high, xhigh, max). An editor
kept writing `minimal` back; the node was renamed (`query_rewrite`) and moved to
gpt-5-mini. → Keep model settings in code or config that is reviewed, and test
each deployment name with a real call after a model change.

**Empty beats invented.** Prompts and studio instructions forbid inventing
customers, figures or capabilities; missing facts become visible placeholders.
See MIGRATION.md §6. Carry this policy into every prompt in production.

---

## 4. Knowledge base and retrieval

**Embedding dimension is fixed at creation.** A knowledge base created with one
embedding model cannot take vectors of another size; switching to
`text-embedding-3-large` (3072 dimensions) required a new knowledge base and a full
re-upload. → **Azure/C#:** choose the embedding model before creating the Azure AI
Search index / Foundry IQ knowledge source, and write it down.

**Embedding endpoint is not the project endpoint.** In Foundry, chat answers on the
project endpoint but embeddings on the resource root; the project path gives a bare
404 that looks like a missing deployment. See MIGRATION.md §3.

**The platform may ignore your chunking.** Dify ignores `process_rule` when a
document is updated, so `sync_corpus.py` splits documents itself (one chunk per
`##` section). → Check how Foundry IQ chunks our markdown; keep provenance
(source URL, organisation) on every chunk.

**Permissions on knowledge are metadata filters, and must be tested.** Private
uploads and contexts are tagged with an `owner` metadata value (`public` or a hash
of the user id) and every query filters on it. A leak test (a private document must
be invisible to another user) passed and must be repeated after every change.
→ **Azure/C#:** security trimming in Azure AI Search / Foundry IQ, plus the same
leak test in the pipeline. Open issue: evidence stays public after its context is
deleted.

**Measure retrieval with a fixed question set.** `dify/eval_questions.json`
(22 questions) and `dify/eval_knowledge.py` gave 22/22 with Dify. Run the same set
against Foundry IQ before switching; it is the evidence for the Dify vs Foundry
decision.

**Hosted limits shape the design.** Dify Sandbox: about 10 knowledge-base requests
per minute (every chat question counts) and 50 documents. → Look up the quotas of
each Azure tier (AI Search free vs Basic, model TPM) on the pricing and limits
pages before load testing.

---

## 5. Dify specifics (only if Dify stays)

- Opening the Dify editor can overwrite a `difyctl` import with an older copy.
  After every import: refresh the editor, publish, then `difyctl export` and compare.
- An import is not live until it is **published** in the editor.
- Dify Cloud is behind Cloudflare: Python's default User-Agent gets
  `403 error code: 1010`. Send an explicit User-Agent header.
- Apps are generated from SIP's own prompts and models (`dify/build_apps.py`);
  never edit prompts in the Dify UI only, or the repository and Dify drift apart.

---

## 6. Marketing studio (Open Design)

Most of the studio problems were the same lesson: **the model only uses what is
physically in the project, and it copies what it sees, not what the text says.**

**Brand files must be in the project.** The design system's text reached the model,
its files did not: no logo, no fonts, so the model drew a logo or fetched a stock
photo. The gateway now copies logos, images, examples and fonts into
`brand/<brand>/` of every new project.

**Projects created in the studio itself got nothing.** Only projects started from
the SIP chat were prepared; a colleague's project had no design system and the
model downloaded a photo. The gateway now prepares *every* new project; without a
chosen house style it adds both and the model first asks "Etil or ibc group?".

**Don't depend on undocumented APIs of a pinned image.** Open Design's
`GET /api/design-systems/<id>/files` started answering 404 ("editable design system
not found") from about 25-09: brand copying stopped and a handoff from the SIP chat
could fail. The gateway now
reads the files from disk. → Prefer reading our own files from our own storage
over a third-party listing endpoint; alert when a project is created without brand
files.

**IDs and folder names differ.** Open Design calls the design systems `user:etil`
and `user:ibc-group`; the folders and the image catalogue use `etil` and
`ibc-group`. A prompt pointed at `brand/user:etil/`, which did not exist.

**Give the exact official assets, and nothing that contradicts them.**
- ibc group had only a white logo with a *white* bar; the official posts use the
  white logo with the *colour spectrum* bar. The model used what it had. Added
  `ibc-group-logo-white.png`; the white-bar file is marked "not for posts".
- The AI label was described as a line of text, so the model wrote a line of text.
  DESIGN.md now contains the exact HTML and CSS of the official label (outlined
  pill "AI-GENERATED VISUAL" + "provided by ibc group marketing").
- Nearly every brand image had an old AI notice baked in, which clashed with the
  label. They were replaced by the "Images without AI notice" originals; images
  without a clean original had the notice cropped off.
- Logos must never be drawn in HTML/CSS; only the PNG/SVG as it is.
- The model is told to open the matching example post first and compare before
  finishing.
→ **Azure/C#:** treat the brand package (DESIGN.md, tokens, logos, images,
examples, fonts) as a versioned artifact with an owner in marketing; review it
visually against the official templates whenever it changes.

**Old projects keep old files.** Fixes apply to new projects only; tell users to
start a new project after a brand change.

**Draft design systems cannot be used.** A design system needs `metadata.json` with
status `published`, or projects cannot select it.

**Files linger on volumes.** Renamed or removed brand files stayed on the volume
after a redeploy. The entrypoint now replaces the brand packages on every start,
while moving the private brand library aside and back so it survives.
→ **Azure/C#:** with Azure Files or Blob storage, deploy the package as a whole
(replace, don't merge) and keep user-uploaded content in a separate location.

**Keep the model key on the server.** Open Design normally stores a model key in
every marketer's browser. The gateway rewrites each run to use the server's key and
model, so marketers enter nothing. The bundled OpenCode CLI is required for that
runtime, and it needs a writable `HOME`.

**Licences.** Creative Commons images need attribution and a fresh licence check;
they are kept out of the projects. Never use photos from the internet.

---

## 7. Signed links, sessions and iframes (studio and developer gateways)

**A signed link is not a session.** Both gateways first signed the entry link and the
session cookie the same way, so a link token could be used directly as a cookie and
skip the one-time check. Found twice (developer and studio). Session tokens now
carry `typ: session`; the gateway rejects a link as cookie and a cookie as link.
→ **Azure/C#:** if signed handoff links remain, give every token type its own
purpose claim and validate it; better, use Entra ID sign-in on every app.

**Embedding needs both sides configured.** The studio runs in an iframe inside SIP:
`Content-Security-Policy: frame-ancestors` must name SIP, and the cookie needs
`SameSite=None; Secure; Partitioned` or browsers drop it in the iframe. Safari was
not tested; offer "open in new tab".

**Only SIP decides who gets in.** Open Design and OpenCode have a single shared token
and no user accounts. They listen on localhost only; a gateway is the one way in.
→ **Azure/C#:** keep these tools on a private network (internal ingress / private
endpoint) behind SIP, never exposed directly.

---

## 8. Azure DevOps writes (Product Owner assistant)

These rules prevented duplicate or wrong work items and carry over unchanged:

- **Write only what the user confirmed:** SIP writes the exact version on screen,
  identified by a confirmation id; any edit makes a new version that needs a new
  confirmation.
- **Claim the write atomically,** so a double click or retry writes once.
- **A timeout after sending is "uncertain", not "failed":** no retry until SIP has
  checked (WIQL query on title, author and time). One match = created, none =
  failed, several = stay uncertain.
- **Optimistic concurrency on changes:** a `/rev` test operation; if the item changed
  meanwhile, plan again on the new revision and ask again.
- **Validate model output against live data:** sprints, people, states and tags are
  read from DevOps; anything else the model proposes is dropped, visibly.
- **Rules per work item type** live in code (`devops.TYPE_RULES`): bugs use repro
  steps, tasks remaining work, features/epics effort.
- **Never close or remove** through SIP; the server refuses it, whatever the model
  says.
→ **Azure/C#:** port these as tests first (`tests/test_product_owner*.py` describe
the behaviour), then the implementation.

---

## 9. Frontend

- Fonts are self-hosted (Ubuntu, woff2, Ubuntu Font Licence); no external font CDN.
- The living robots need two images per robot (`<name>.webp` and `<name>-base.webp`
  with the eyes painted out) and eye coordinates on the 1254 px grid. New robot
  artwork means new base images and coordinates. Respect "reduce motion".
- Hover styles only applied to single-action cards (`.is-single-action`), so the
  two-action Kennisassistent card did not highlight. Check interaction states for
  every card variant.

---

## 10. Testing that paid off

- **Fake upstream tests:** `marketing/open-design/test-gateway.mjs` runs the gateway
  against a fake Open Design (including the 404 seen live); pytest uses fake Dify
  and DevOps. They caught the cookie bug and the brand-copy regression.
- **Production smoke tests from inside the container,** with the container's own
  token: create a project, list its files, delete it again.
- **Visual check against the official example:** render the design next to the
  official template before shipping a brand change.
- **Leak test and retrieval eval** after every knowledge change.
→ **Azure/C#:** make all four pipeline steps.
