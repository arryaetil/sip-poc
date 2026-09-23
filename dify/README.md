# Dify apps for SIP

SIP can run its assistants on hosted Dify instead of Azure AI Foundry.
`SIP_ASSISTANT_PROVIDER=dify` switches every model call to the three apps below;
the default, `foundry`, keeps the original path. The switch lives in
`backend/app/assistants.py` and nowhere else.

| App | Dify app id | Used by | Returns |
|---|---|---|---|
| SIP — Product Strategist (Dify) | `516e0f3c-866c-42d3-92fb-db0a2b04d0e4` | context chat, discussing an upload | `ProductStrategistTurn` JSON |
| SIP — Business Context Finalizer (Dify) | `f7d3e6a6-aa5c-4159-93b9-2893b6a8a414` | saving a conversation to the portfolio | `BusinessContext` JSON |
| SIP — Knowledge Assistant (Dify) | `e1950fd4-7d7e-4840-be5d-e27b71cf6922` | knowledge chat | answer + retriever resources |

The knowledge app searches the Dify knowledge base *SIP — ETIL corpus (3-large)*
(`cc833d3d-e595-41c7-a7ca-1bc1c5b7decd`), filled from `knowledge/markdown/etil`
with `text-embedding-3-large`, the same embedding model SIP uses.

## How the apps are built

The YAML files here are generated. Do not edit them in the Dify UI and then
forget to bring the change back: the next import overwrites it.

```bash
python dify/build_apps.py
difyctl import studio-app -f dify/strategist.yml --app-id 516e0f3c-866c-42d3-92fb-db0a2b04d0e4
difyctl import studio-app -f dify/finalizer.yml  --app-id f7d3e6a6-aa5c-4159-93b9-2893b6a8a414
difyctl import studio-app -f dify/knowledge.yml  --app-id e1950fd4-7d7e-4840-be5d-e27b71cf6922
```

An import only updates the draft. **Publish each app in Studio afterwards**;
the API always serves the published version.

`build_apps.py` reads `system_prompt.txt`, `finalizer_prompt.txt`,
`knowledge_assistant_prompt.txt` and the Pydantic models, so a prompt change in
SIP reaches Dify on the next build. Structured answers use OpenAI strict JSON
schema generated from the same models SIP validates against.

Design choices:

- **SIP owns the conversation.** History is sent as the `history` input on
  every call and Dify memory is off, so conversations survive a provider switch.
- **Query rewrite before retrieval.** A fast model turns a follow-up such as
  "and what does it cost?" into a standalone query first.
- **Hybrid retrieval**, 0.7 semantic / 0.3 keyword, top 12. SIP's own hybrid
  mode (`SIP_RETRIEVAL=hybrid`) fuses both with Reciprocal Rank Fusion, which
  Dify does not offer.
- **Uploads stay in SIP.** They are not indexed in Dify, because that would place
  user documents outside Azure without a processing agreement. Discussing an
  upload does send its text to the Strategist app, so the same caveat applies
  there: use public or test documents only.

## Configuration

| Variable | Value |
|---|---|
| `SIP_ASSISTANT_PROVIDER` | `dify` or `foundry` (default) |
| `DIFY_STRATEGIST_API_KEY` | app key of the Product Strategist app |
| `DIFY_FINALIZER_API_KEY` | app key of the Finalizer app |
| `DIFY_KNOWLEDGE_API_KEY` | app key of the Knowledge Assistant app |
| `DIFY_API_BASE` | optional, default `https://api.dify.ai/v1` |

With `dify` selected the app refuses to start unless all three keys are set.
Create a key in Studio → the app → **API Access** → **API Key**.

## Known differences from the Foundry path

- No near misses: Dify does not report documents that scored just below the bar.
- Workspace uploads are not searchable by the knowledge assistant.
- The legacy `/api/chat` and `/api/contexts/prepare` endpoints, which chain
  Foundry response ids and are not used by the UI, stay on Foundry.
