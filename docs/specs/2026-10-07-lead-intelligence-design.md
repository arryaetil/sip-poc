# SIP — Lead intelligence

**Status:** design agreed in brainstorm, not implemented. Open items in section 9 must be
resolved before step 2.
**Date:** 7 October 2026
**Audience:** the developer or agent implementing this, and the senior developer reviewing it
**Repo:** https://github.com/arryaetil/sip-poc

The Lead intelligence page promises: *"This workspace uses approved Business Contexts to
find and assess relevant organisations."* This document records what that means: for whom,
what it produces, where the data comes from, and what it may and may not do.
[EXTENSIBILITY.md](../EXTENSIBILITY.md) ("Planned: lead generation") asks three questions
before anything is built — lawful basis, data source, retention. Section 7 answers the
last two and hands the first to the privacy officer.

---

## 1. Goal

From an approved Business Context, produce a list of organisations that sales can
approach — the same shape as `SAM_leads_definitief.xlsx` (28 car dealer groups in
Limburg, Belgium and the German border region, with phone, generic e-mail, website,
number of branches and a link to the company's LinkedIn people page).

**Users:** sales. Roles `sales` and `admin` only.

**Name in SIP:** the homepage robot and the chat assistant are called **Lead finder**
(replaces the placeholder "Lead intelligence"). The search step behind it is the
*lead search workflow*.

**A lead is an organisation, never a person.** SIP stores no names, personal e-mail
addresses or personal phone numbers of decision makers. Sales finds the right person
themselves via the LinkedIn company page link.

## 2. Flow

```
 SIP                               Dify
 ───                               ────
 Ask ibc group: "find leads  ─┐
 for this"                    ├──▶ 1. LEAD FINDER (chatflow)
 or open Lead finder  ───────┘       reads the Business Context, asks targeted
                                      questions, proposes a scorecard
                                      └─▶ search brief (JSON)
                                               │
 SIP validates brief (max 50),                 ▼
 splits into batches of 10  ──────▶ 2. LEAD SEARCH (workflow), per batch
                                      a. LLM writes search queries
                                      b. Serper: Google results
                                      c. LLM keeps real companies, drops news,
                                         directories and duplicates
                                      d. per company: fetch public pages
                                         (contact, about, locations), LLM extracts
                                         each column + source URL, or "unknown"
                                      e. LLM writes "why this fits" (one sentence)
                                               │
 SIP computes score from      ◀────────────────┘
 scorecard, stores list (90 days),
 shows table, Excel export
```

### Search brief

The structured result of the intake. Example for SAM:

```json
{
  "business_context_id": "…",
  "description": "Car dealer groups with multiple branches",
  "industries": ["automotive dealers"],
  "regions": ["NL-Limburg", "BE-Limburg", "DE border region"],
  "extra_columns": [{"name": "branches", "description": "number of branches/locations"}],
  "scorecard": [
    {"criterion": "branches", "high": ">= 10", "medium": "4-9", "low": "<= 3"},
    {"criterion": "region", "high": "NL-Limburg or BE-Limburg", "medium": "rest of NL/BE", "low": "DE"}
  ],
  "count": 30
}
```

### Intake rules (Lead finder)

- Starts from the Business Context fields `target_organisations`, `relevant_industries`,
  `relevant_roles_and_decision_makers`, `geographic_focus`, `value_proposition`.
- Proposes 1–3 solution-specific extra columns and a scorecard; the user adjusts and
  confirms both.
- Asks openly *"How many leads do you want?"* — it does **not** mention a maximum. Only
  when the user asks for more than 50 does it answer that 50 is the maximum per request
  and offer to start with 50.

## 3. Columns

**Fixed:**

| # | Column | Rule |
|---|---|---|
| 1 | Company name | |
| 2 | City | |
| 3 | Country | NL / BE / DE … |
| 4 | Website | |
| 5 | General phone | Main number only. Never a mobile number of an employee |
| 6 | General e-mail | Role addresses only (`info@`, `sales@`, `hr@`, `directie@`). An address containing a person's name is left empty |
| 7 | LinkedIn company page | Link to `linkedin.com/company/…/people/`, found via a search result. Never a personal profile |
| 8 | Why this fits | One sentence, referring to the Business Context |
| 9 | Sources | URLs the values came from |

**Per solution:** 1–3 extra columns agreed in the intake (SAM: number of branches).

**Every filled cell has a source.** A value the agent cannot back with a fetched page is
`unknown`, not a guess. This is the existing grounding rule ("empty beats invented").

## 4. Score

- **High / medium / low**, based on the scorecard in the search brief.
- The LLM extracts facts ("27 branches, source: anmgroup.be/vestigingen"); **code** applies
  the scorecard. Same facts → same score, and the reason is always explainable.
- An `unknown` fact can never produce `high`.
- The user can edit the scorecard **after** the list exists; scores are recalculated
  without searching again.

## 5. Sources and what the agent may do

- **Serper** (Google search API) and **public company website pages** only.
- **No LinkedIn scraping.** LinkedIn's terms forbid automated reading. The agent only
  takes the company page URL from a Google result (e.g. `"Mengelers" site:linkedin.com/company`).
- Only public pages (contact, about, locations); respect `robots.txt`.
- Search queries contain organisation characteristics only, never personal data.
- **Not now:** KvK, KBO, Handelsregister, commercial databases (Company.info, Apollo).
  KBO open data is free but a bulk file; KvK API is paid. Revisit only if the pilot shows
  the website data is not good enough.
- **No filtering of existing customers.** Sales judges that.

## 6. Volume

- The user chooses the number; **maximum 50 per request.**
- SIP enforces the maximum in code before starting the lead search, regardless of what the
  assistant said (fail closed). The assistant instruction alone is not enough.
- SIP runs the workflow in **batches of 10** and shows progress ("10 of 30 found"). A failed
  batch keeps the results of earlier batches.

## 7. Storage, retention, access

- Lists are stored in SIP (search brief, scorecard, rows, sources, creator, created date).
- **Retention: 90 days** (proposal — to be confirmed by the ISMS owner), then deleted
  automatically by a daily cleanup job that logs what it deleted (count and list ids, not
  contents).
- Excel export is allowed; exported files are outside SIP's control, so the export
  includes the creation date.
- **Access:** roles `sales` and `admin`, on every endpoint (create, read, edit scorecard,
  export, delete). Everyone with those roles sees all lists.
- Nothing from lead rows goes into logs.

## 8. Dify or LangGraph

**Dify first.** All SIP assistants already run on Dify, and the C# version talks to Dify
through `IKnowledgeAssistant`. LangGraph only replaces the lead search workflow (step 2) if the
pilot shows Dify cannot handle the run time, step limits or per-cell sources. That
decision is for the senior developer.

## 9. Open items

| Item | Owner |
|---|---|
| Lawful basis for approaching organisations from public company data (likely legitimate interest); own privacy assessment as EXTENSIBILITY.md asks | Privacy officer ibc group |
| Confirm 90-day retention | ISMS owner |
| Dify vs LangGraph; approval to build step 2 on Railway before SIP runs in Azure (EXTENSIBILITY.md) | Senior developer |
| Dify free tier limits; Serper free credit and cost per run | Arrya |

## 10. Smallest first version

**Step 1 — Dify only, nothing in SIP.** Build the lead search workflow with a fixed SAM
search brief, 10 leads, extra column "branches". Compare against the SAM list as the gold
standard and measure:

- how many SAM companies it finds;
- how many cells match;
- that every filled cell has a source (zero invented values);
- run time and cost per 10 leads.

**Step 2 — Lead intelligence page in sip-poc on Railway.** Pick a Business Context, fill in
the search brief and scorecard through a **simple form** (no chat yet), get a scored table,
edit the scorecard, export to Excel. Storage, 90-day cleanup and `sales`/`admin` access as
in section 7. Requires the open items in section 9.

**Step 3 — Lead finder chat** and the "find leads for this" button in Ask ibc group.

Step 1 answers the question everything else depends on: is the data good enough?
