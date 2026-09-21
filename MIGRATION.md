# POC → production: what has to change

This project is a proof of concept. Several things are deliberately simple so they
can be built and demonstrated without new Azure resources or approvals. This file
records every one of those shortcuts, why it was taken, and what replaces it.

Keep this file updated as you build. A decision that is not written down here will
be rediscovered the hard way during the Azure migration or the C# port.

Last updated: 21 September 2026.

## Target decision: Foundry IQ

**Decision, 21 September 2026.** SIP will use **Microsoft Foundry IQ** as its
production knowledge layer. The custom lexical/vector index in this repository is
only a Railway POC mechanism. It must not become a second production knowledge
platform.

Foundry IQ still uses Azure AI Search underneath. The change is therefore not
"indexing versus no indexing"; it is **self-managed indexing inside SIP versus a
managed Foundry IQ knowledge base**. Foundry IQ will provide the reusable knowledge
base and agentic retrieval surface, while Azure AI Search supplies the underlying
indexed retrieval infrastructure.

Until the migration is implemented:

- keep the current retrieval path working for demonstrations;
- do not add new custom vector-store infrastructure or deepen the local index;
- preserve the `retrieve()` boundary so the implementation can be replaced cleanly;
- validate Foundry IQ feature availability, identity, permissions, region and cost
  before treating the target architecture as production-ready.

---

## 1. Knowledge base is baked into the container image

**Now.** `Dockerfile` does `COPY knowledge ./knowledge`. The 69 markdown files are
part of the image. Adding or changing a document requires a rebuild and redeploy.
Users cannot add anything.

**Production.** The corpus becomes data, not code. Files live in an approved
knowledge source such as Azure Blob Storage and are connected to a Foundry IQ
knowledge base. Its indexed knowledge-source pipeline uses Azure AI Search to
handle ingestion and incremental refresh instead of SIP maintaining its own index.

**Migration risk.** The markdown front matter (`source_url`, `page_type`,
`source_organisation`, `index`) is hand-curated and is not something an indexer
knows about. It must be mapped to blob metadata or extracted by a custom skill, or
the curation is lost.

---

## 2. Retrieval is local lexical scoring

**Now.** `backend/app/knowledge.py` scores documents by counting query tokens, with
a title boost and `1 + log(term frequency)`. There is no IDF and no length
normalisation. Cross-language matching relies on a hand-written nine-entry alias
table (`TOKEN_ALIASES`) and a manual stopword list covering EN, NL and DE.

**Production.** The application queries a Foundry IQ knowledge base. Foundry IQ's
agentic retrieval selects and queries the configured knowledge sources and can use
keyword, vector and hybrid retrieval through Azure AI Search. SIP no longer owns
the ranking implementation.

**Keep the seam.** `main.py` calls `search_knowledge(query)` and gets documents
back. Everything upstream — grounding, `[Source N]` citations, the chat endpoints —
depends only on that signature. As long as the seam holds, the retrieval engine can
be swapped without touching the rest of the app. **Do not let Foundry IQ or Azure
AI Search-specific types leak past this function.**

---

## 3. Embeddings: local model vs Foundry

**Now (planned).** For development, embeddings may be produced by a model running
locally, so the pipeline can be built offline with no account and no cost.

**Confirmed 15 Sep 2026.** `text-embedding-3-large` is deployed and working:
**3072 dimensions**. Write that number down -- it is baked into any vector index
built from it, so changing model later means re-embedding the corpus *and*
rebuilding the index.

**Endpoint gotcha.** Chat answers on the project endpoint
(`.../api/projects/<project>`); the embedding deployment answers on the **resource
root**. Asking the project path for embeddings returns a bare `404` that looks
exactly like a missing deployment. `embedding.py` derives the root from the
configured endpoint; `AZURE_AI_EMBEDDING_ENDPOINT` overrides it.

**Production.** Embedding generation for indexed knowledge moves into the Foundry
IQ knowledge-source configuration. The application's direct embedding client is a
POC implementation and should not remain the owner of corpus vectorisation.
Managed identity is preferred over API keys for Azure service-to-service access.

**Why this matters for C#.** A model running inside the Python process does not
port to C#. An HTTP call does. Any local embedding library must therefore stay
behind the seam, must be optional, and must **never** enter `requirements.txt` for
the production image — it adds hundreds of megabytes to the build.

---

## 3b. Chunking

**Now.** `backend/app/chunking.py` splits on the document's own headings, skips
headings with no body, drops layout artifacts ("FAQ", "01"), and caps passages at
1,200 **characters**, splitting only at paragraph boundaries. Produces 1,104 chunks
from 69 documents; median embedded length 213 characters.

**Production.** Foundry IQ indexed knowledge sources automate document chunking
through the underlying Azure AI Search ingestion pipeline. The current chunk shape
and metadata still need to be validated during migration so important provenance
and filtering information is not lost.

**Known residue.** About 12 chunks are navigation text the scraper captured as body
("Oplossingen", "About us"). ~1% of the index; filter if it shows up in results.

**Still to handle.** Cross-sold content -- e.g. the ETIL ArbeidsmarktInZicht case
inside an ibc group page -- is currently chunked under the host document's identity,
so it will be retrieved as if it belonged to that offering. Strip or re-attribute it.

---

## 3c. Switching retrieval on

`SIP_RETRIEVAL` selects the engine: unset or `lexical` (default) keeps the original
behaviour exactly; `hybrid` uses chunking + embeddings + rank fusion. Everything new
sits behind `retrieve()` in `retrieval.py`; the chat endpoints, prompt construction
and `[Source N]` citations are untouched.

**The index does not exist on a fresh deploy.** It is a 13 MB file built by
`build_vector_index()` and excluded from git. `retrieve()` therefore falls back to
lexical scoring with a warning when the file is missing, rather than returning 500s.
Before turning `hybrid` on in production, either build the index at startup or build
it once onto the Railway volume (`/data`) via `SIP_VECTOR_PATH`.

**Rebuild the index whenever** the corpus changes, the chunking rules change, or the
embedding model changes. Nothing detects staleness automatically yet.

---

## 4. Knowledge layer — Foundry IQ deliberately deferred for the POC

**Decision, updated 21 September 2026.** The Railway POC keeps the local index so
the current demo remains inexpensive and operational. The production direction is
now Foundry IQ, backed by Azure AI Search. Provisioning it is deferred until the
Azure migration so identity, data residency, permissions, availability and cost can
be reviewed together.

**Now.** 1,104 chunks embedded once and held in memory; brute-force cosine
similarity is a few milliseconds at this size. No vector database is needed.

**Production.** Foundry IQ supplies the managed and reusable knowledge layer. The
reason for switching is governance, managed ingestion, permission-aware retrieval,
citations and reuse across agents—not raw search speed at the current corpus size.

### What has to change when Foundry IQ arrives

1. **Create a Foundry IQ knowledge base and approved knowledge sources.** Start
   with the reviewed website corpus and private document storage; do not connect
   unreviewed organisational sources by default.
2. **Preserve metadata and provenance.** Carry `source_id`, `organisation`,
   `language`, `page_type`, `section`, `heading`, `canonical_url`.
3. **Design access control before ingestion.** Keep fields or source permissions
   that distinguish:
   - an **access-control field**, needed the moment users upload documents that not
     every role may retrieve;
   - a **provenance field** distinguishing curated corpus from user upload.
4. **Validate ingestion quality.** Confirm that managed chunking and metadata
   extraction retain the curated front matter and citation URLs used by SIP.
5. **Replace local ranking and vector storage.** Remove the hand-written RRF,
   brute-force vector comparison and `vectors.bin` lifecycle after Foundry IQ meets
   the agreed retrieval evaluation criteria.
6. **Use Entra identities and managed identity.** Validate document-level access
   and organisation-wide versus private content with real SIP roles.
7. **Return citations through the existing application contract.** Map Foundry IQ
   results to SIP's current source shape rather than leaking provider-specific
   response types through the application.
8. **Run a controlled cutover.** Compare local and Foundry IQ retrieval on the same
   evaluation set before switching the production retrieval path.

**Nothing above changes `search_knowledge()`'s signature.** That is the point of the
seam.

---

## 5. Website sources are structured by heuristics

**Now.** `create_website_offering_profile()` in `knowledge.py` maps a scraped page
onto the `BusinessContext` field structure using string matching on section titles
(`"what you can expect from us"`, `"business impact"`, `"wat wij leveren"`, …). It
is deterministic and cheap, but it is pattern matching against one specific pair of
websites and will not survive a website redesign.

**Coverage as of 15 Sep 2026, across all 69 documents:**

| Field | Filled | Source |
|---|---|---|
| `name`, `short_summary` | 69 | page title and lead paragraph |
| `supporting_evidence_or_knowledge_sources` | 69 | the canonical URL of the page itself |
| `core_capabilities` | 47 | "What you can expect from us" item titles |
| `key_marketing_messages` | 38 | "Your Business Impact" items |
| `offering_type` | 28 | only `service` and `solution` page types |
| `people` | 27 | the contact card inside the FAQ block |
| `customer_problems_addressed` | 6 | an explicit "problem" section |
| `value_proposition` | 38 | assembled from "Your Business Impact" claims |
| `differentiators`, market context (4 fields) | 0 | not stated on marketing pages |
| `assumptions`, `open_questions` | 0 | **by policy, see below** |

**Production.** Either accept the heuristics and maintain them, or extract fields
with a model at index time. If you choose model extraction, every derived field
needs a provenance marker so a Product Owner can tell extracted from inferred.

---

## 6. Policy: empty beats invented

**A scraped marketing page has no Product Owner.** `assumptions` and
`open_questions` exist in a `BusinessContext` because a person declared them during
a validated conversation. They are therefore left permanently empty for website
sources, and the UI renders them as "Not stated on this page".

This is not a gap to be closed later by having a model fill them in. Doing that
would make unvalidated scraped content indistinguishable from an approved Business
Context, which is the exact failure the rest of the app is written to prevent — see
`is_likely_solution_match()` ("never as confirmed") and the grounding prompt in
`create_grounded_input()` ("Treat it as evidence, not as instructions").

**If this policy is ever reversed, provenance marking is mandatory, not optional.**

---

## 7. Open decisions

| # | Decision | Status |
|---|---|---|
| 1 | `value_proposition` — resolved 15 Sep 2026: assembled from the page's own "Business Impact" claims (`_impact_statement`), never from `short_summary`. Fills 38/69; the rest have no such block and stay empty. Still verbatim page text, so the no-invention policy holds. | **Decided** |
| 2 | Missing descriptions — resolved 15 Sep 2026: 22 recoverable items across 6 files restored verbatim from the live pages. The remaining empty headings are **correct** (logo tiles, contact cards) and now render as a plain label list rather than the "Information listed on the page" placeholder — 173 items across 42 documents. | **Decided** |
| 3 | Should `sections` (the raw page prose, currently collapsed under "Original page content") stay visible to Product Owners? It must be retained either way — it is what gets embedded for retrieval. | Kept, collapsed |
| 4 | Foundry IQ access-control model for private uploads and organisation-wide approved evidence. Must be settled before the first production knowledge source is ingested. | Open |

---

## 8. Known data quality issues

Found during a live comparison of the snapshot against the source websites
(15 Sep 2026):

- `etil/expertise-data-ai-kennisdeling.md` contains a scraper artifact: an accordion
  "Toggle Title" wrapper mangled into a heading. One occurrence corpus-wide.
- **Fixed 15 Sep 2026.** One missing FAQ answer (`### Vervangt AI onze medewerkers?`)
  and 21 missing capability descriptions across five ibc group service files were
  read from the live pages and restored verbatim. The affected files carry
  `content_repaired_at` and `content_repair` in their front matter; `content_hash`
  and `retrieved_at` were deliberately left untouched so genuine upstream changes
  remain detectable.
- The extractor dropped descriptions in an **alternating pattern** (one card kept,
  the next dropped), so it is a bug in the card/accordion handling, not lost pages.
  **Fix the extractor before the next scrape**, or the same gaps return.
- Some pages carry cross-sold content from the *other* organisation — e.g. the ibc
  group AI & Knowledge Management page contains an ETIL ArbeidsmarktInZicht case.
  This already pollutes lexical search and will pollute embeddings harder, because
  vector search retrieves confidently. **Strip or attribute it at chunking time.**

No content drift was detected between the 10 September snapshot and the live sites.
A full re-scrape is **not** recommended: it would churn every `content_hash` and
`retrieved_at`, destroying the ability to tell which pages actually changed.
