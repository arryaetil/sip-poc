# Extending SIP

Status: current
Last updated: 23 September 2026

What the architecture can absorb cheaply, what it cannot, and how the required
Dify-versus-Foundry comparison is built without forking the application.

See [Agreed direction](../README.md#agreed-direction) for the decisions this
builds on.

## The four layers

Everything below follows from one property: whether a change stays in the upper
layers or reaches into the lower ones.

| Layer | Contents | Cost of a new module |
|---|---|---|
| Presentation | browser UI | new screens, no effect elsewhere |
| Domain | Business Context, portfolio, evidence, approval | a new domain beside the existing one — this is the work |
| Platform | model calls, retrieval, storage, Unit of Work | unchanged **if** it sits behind interfaces |
| Infrastructure | App Service, identity, roles, pipeline | unchanged; no new Azure resource |

The condition on the platform layer is the whole game. If EF Core types or the
Foundry client leak into the domain, every new module entangles with the existing
one and the second module costs as much as the first. Keeping `DbContext` behind
the Unit of Work and model access behind an interface is not tidiness — it is the
precondition for everything on this page.

## Required: comparing Dify with Foundry

This comparison is an employer requirement, not an option, so the application is
designed for it rather than around it.

### Where the seam goes

Dify performs retrieval *and* generation in one product. A seam at retrieval
alone therefore does not fit it. The comparable unit is the whole answer:

```csharp
public interface IKnowledgeAssistant
{
    Task<AssistantAnswer> AnswerAsync(
        string question, UserContext user, CancellationToken ct);
}

public record AssistantAnswer(
    string Text,
    IReadOnlyList<Citation> Citations,
    bool Grounded);
```

Two implementations sit behind it:

| Implementation | What it does |
|---|---|
| `FoundryKnowledgeAssistant` | SIP's own orchestration over Foundry IQ and a Foundry model |
| `DifyKnowledgeAssistant` | delegates the whole question to Dify over its API |

Configuration selects which one is active, per environment or per request when
both should run side by side. Nothing above the interface knows which is in use.

The arrangement is deliberately disposable: when the comparison concludes, the
losing implementation is one file to delete and one configuration value to
remove.

### Run the evaluation before integrating

Wiring Dify into the application is not a prerequisite for comparing it. Start
with a fixed set of twenty to thirty realistic questions over the existing
corpus, each with a description of what a good answer contains, and run that set
through both systems.

That produces the quality comparison in days. Build the second implementation
only once the question is how Dify behaves *inside* the product — permissions,
latency, cost per answer.

### What the comparison measures

| Criterion | Why it decides anything |
|---|---|
| Answer quality on the fixed set | the core, including an honest "not found" |
| Citation fidelity | do citations point at what was actually supplied to the model |
| Permission awareness | can results be filtered per user, or does everyone see everything |
| Cost per answer | Dify: hosting plus tokens. Foundry: tokens plus Azure AI Search |
| Operational burden | who patches, backs up and monitors it |
| Data residency | Dify Cloud places data outside Azure; self-hosting does not |
| Workflow adaptability | how quickly someone without programming experience changes a prompt chain |
| Auditability | can you reconstruct what was sent to the model |

Permission awareness deserves attention. SIP's model is built on visibility:
a document belongs to its uploader, and evidence becomes organisation-wide only
after approval. Dify does not know those rules. Whether it can be made to respect
them is a finding for the comparison, not an obstacle to running it.

### Where Dify runs

Dify ships as containers and needs PostgreSQL, Redis and a vector store beside
it. Self-hosting means Azure Container Apps or a virtual machine — containers
alongside the App Service web app, not instead of it. The two are different
workloads and do not conflict.

Dify Cloud removes that operational work but places data outside Azure, which is
a question for the senior developer before any customer document is involved.
Synthetic evaluation data does not raise it.

## Planned: marketing studio

Low architectural risk. Content generation, templates and brand material are new
prompts, new screens and storage that already exists. It adds a domain beside the
existing one and touches nothing below.

## Planned: lead generation

Technically a module like any other. Legally it is not.

Leads are personal data about people who did not ask to be contacted, which is a
different category from documents a customer hands over deliberately. Before it
is built, three questions need answers: what the lawful basis is, where the data
comes from, and how long it may be kept. A retention period and a deletion path
have to exist in the design, not be added afterwards.

Treat it as its own project with its own privacy assessment, not as a feature
added to a sprint.

## Sequence

New capability is only cheap on a foundation that works. Nothing on this page
starts before SIP runs in Azure with the three blockers closed. Adding modules to
a system that is still being migrated multiplies both jobs instead of advancing
either.

The Dify comparison is the exception and can begin earlier, because the
evaluation phase needs only a question set and the existing corpus — no
application changes at all.
