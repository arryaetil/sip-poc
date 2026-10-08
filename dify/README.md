# Dify apps for SIP

SIP can run its assistants on hosted Dify instead of Azure AI Foundry.
`SIP_ASSISTANT_PROVIDER=dify` switches every model call to the apps below;
the default, `foundry`, keeps the original path. The switch lives in
`backend/app/assistants.py` and nowhere else.

| App | Dify app id | Used by | Returns |
|---|---|---|---|
| SIP — Product Strategist (Dify) | `516e0f3c-866c-42d3-92fb-db0a2b04d0e4` | context chat, discussing an upload | `ProductStrategistTurn` JSON |
| SIP — Business Context Finalizer (Dify) | `f7d3e6a6-aa5c-4159-93b9-2893b6a8a414` | saving a conversation to the portfolio | `BusinessContext` JSON |
| SIP — Knowledge Assistant (Dify) | `e1950fd4-7d7e-4840-be5d-e27b71cf6922` | knowledge chat | answer + retriever resources |
| SIP — Product Owner (Dify) | `08102bff-059c-463c-aad5-b827fbc6bb0d` | Product Owner chat (user story drafts) | `ProductOwnerTurn` JSON |
| SIP — Lead finder (Dify) | `2266c4de-5764-4411-8b04-03f9b4f7cccc` | Lead finder intake and lead search steps | `LeadIntakeTurn`, `LeadQueryPlan`, `LeadCandidates` or `LeadExtraction` JSON |

The knowledge app searches the Dify knowledge base *SIP — ETIL corpus (3-large)*
(`cc833d3d-e595-41c7-a7ca-1bc1c5b7decd`), filled from `knowledge/markdown/etil`
with `text-embedding-3-large`, the same embedding model SIP uses.

## Access for maintenance

Use `difyctl` for Studio maintenance, as in the commands below. Authenticate with
its browser device sign-in (`auth login --host https://cloud.dify.ai` in the
published command reference; newer edge builds use `login --server ...`). Check
`difyctl --help` for the installed version. This avoids manually copying browser
cookies. Check the active account/workspace before changing an app. App API keys
(`app-...`) run published apps; they are not Studio maintenance credentials.
Official reference: https://github.com/langgenius/dify-docs/blob/main/en/cli/reference/auth-and-contexts.mdx

The Windows machine used on 2026-10-08 had no `difyctl` on PATH or local saved
CLI session. A direct Console API check authenticated successfully with the
access and CSRF tokens, but `/apps/imports` rejected the update with the Sandbox
app limit. No Lead finder update was applied. Arrya explicitly skipped this
import. Do not treat the generated Lead finder YAML as already published.

The chat-driven Business Context selection uses the existing published
Strategist schema and its runtime `extra_instructions` input; it requires no
Dify app import.

## How the apps are built

The YAML files here are generated. Do not edit them in the Dify UI and then
forget to bring the change back: the next import overwrites it.

```bash
python dify/build_apps.py
difyctl import studio-app -f dify/strategist.yml --app-id 516e0f3c-866c-42d3-92fb-db0a2b04d0e4
difyctl import studio-app -f dify/finalizer.yml  --app-id f7d3e6a6-aa5c-4159-93b9-2893b6a8a414
difyctl import studio-app -f dify/knowledge.yml  --app-id e1950fd4-7d7e-4840-be5d-e27b71cf6922
difyctl import studio-app -f dify/product_owner.yml --app-id 08102bff-059c-463c-aad5-b827fbc6bb0d
difyctl import studio-app -f dify/lead_finder.yml --app-id 2266c4de-5764-4411-8b04-03f9b4f7cccc
```

An import only updates the draft. **Publish each app in Studio afterwards**;
the API always serves the published version (an app that was never published
answers `400 Workflow not published`). After every import: refresh the editor
tab first (a stale tab can overwrite the import), publish, then check with
`difyctl export studio-app <id>` that the published draft holds the change.

`build_apps.py` reads `system_prompt.txt`, `finalizer_prompt.txt`,
`knowledge_assistant_prompt.txt`, `product_owner_prompt.txt` and the Pydantic models, so a prompt change in
SIP reaches Dify on the next build. Structured answers use OpenAI strict JSON
schema generated from the same models SIP validates against.

Design choices:

- **Models per job.** The Strategist and the Finalizer run on `gpt-5.6-terra`,
  because what they produce lands in the portfolio. The knowledge assistant
  (query rewrite and answer) runs on `gpt-5.6-luna`, where speed matters more
  than depth. The Foundry path keeps `MODEL_DEPLOYMENT`.

- **SIP owns the conversation.** History is sent as the `history` input on
  every call and Dify memory is off, so conversations survive a provider switch.
- **Query rewrite before retrieval.** A fast model turns a follow-up such as
  "and what does it cost?" into a standalone query first.
- **Hybrid retrieval**, 0.7 semantic / 0.3 keyword, top 12. SIP's own hybrid
  mode (`SIP_RETRIEVAL=hybrid`) fuses both with Reciprocal Rank Fusion, which
  Dify does not offer.
- **Uploads and Business Contexts are indexed in Dify** so the knowledge
  assistant can use them. This places them outside Azure: use test data only
  until there is a processing agreement.
- **Permissions are emulated with metadata.** Dify has no per-user permissions
  inside a knowledge base. Every document carries an `owner` value: `public` for
  the ETIL corpus, approved contexts and published evidence; a pseudonymous user
  label (a hash of the SIP user id) for drafts and private uploads. The knowledge
  app retrieves only `owner = public OR owner = <asking user>`. If that filter is
  misconfigured, private documents reach other users; Foundry IQ on Azure AI
  Search can instead trim results by the user's Entra identity. This is a
  criterion for the comparison, not just an implementation detail.

### Product Owner app

One LLM step on `gpt-5.6-terra` with a strict `ProductOwnerTurn` schema
(`message`, `stage`, `draft`, `open_questions` (max one), `split_suggestion`).
Inputs from SIP: `language`, `history`, `targets` (backlog and open sprints SIP
read from Azure DevOps) and `draft` (the saved proposal, including the user's
edits). The app has no Azure DevOps token and no tools: it only drafts. SIP
stores each version, checks it and creates the story itself after the user
confirmed that version. There is deliberately no approved/success field.
No knowledge base is attached.

### Lead finder app

One app for four tasks, so the Lead finder costs one app on the free plan. SIP
sends `task` (`intake`, `queries`, `select` or `extract`), `language`, `history`
and a ready-made `payload` (built by the same functions as the Foundry path in
`assistants.py`); an if-else routes to one structured-output step per task. The
intake runs on `gpt-5.6-terra`, the three search steps on `gpt-5.6-luna`.

The app does not search. SIP runs the search itself (`backend/app/lead_search.py`):
Serper for Google results, the companies' public pages (robots.txt respected,
private addresses refused, never LinkedIn), and the model only for judgement.
SIP then enforces what the model cannot be trusted with: at most 50 leads, a
fetched source for every fact, generic contact details only, and the score,
which is computed in code from the scorecard. See
`docs/specs/2026-10-07-lead-intelligence-design.md`.

## Configuration

| Variable | Value |
|---|---|
| `SIP_ASSISTANT_PROVIDER` | `dify` or `foundry` (default) |
| `DIFY_STRATEGIST_API_KEY` | app key of the Product Strategist app |
| `DIFY_FINALIZER_API_KEY` | app key of the Finalizer app |
| `DIFY_KNOWLEDGE_API_KEY` | app key of the Knowledge Assistant app |
| `DIFY_PRODUCT_OWNER_API_KEY` | app key of the Product Owner app; optional, without it only the Product Owner chat reports it is unavailable |
| `DIFY_LEAD_FINDER_API_KEY` | app key of the Lead finder app; optional, without it the Lead finder page says it is not set up |
| `DIFY_DATASET_API_KEY` | knowledge base API key (Knowledge → Service API, starts with `dataset-`) |
| `DIFY_DATASET_ID` | optional, default the knowledge base above |
| `DIFY_API_BASE` | optional, default `https://api.dify.ai/v1` |

With `dify` selected the app refuses to start unless all four keys are set.
Run `dify/setup_knowledge_metadata.py` once per knowledge base to create the
`owner` field and mark the corpus public.
Create a key in Studio → the app → **API Access** → **API Key**.

## Known differences from the Foundry path

- No near misses: Dify does not report documents that scored just below the bar.
- The Sandbox plan allows 50 documents per workspace. The corpus uses 32, so
  about 18 uploads and Business Contexts fit.
- The legacy `/api/chat` and `/api/contexts/prepare` endpoints, which chain
  Foundry response ids and are not used by the UI, stay on Foundry.
