# Azure provisioning runbook — development environment

Status: ready to execute
Last updated: 22 September 2026

Step-by-step creation of the SIP development environment in the Azure portal.
The order matters: the web app is created early so that its identity exists, and
every resource after it is granted its role at the moment it is created. That
leaves no separate RBAC pass at the end.

This runbook stops short of Azure SQL and the DevOps service connection. Those
belong to later phases and are listed under
[What this does not create](#what-this-does-not-create).

See [Agreed direction](../README.md#agreed-direction) for the decisions behind
these choices.

## Before you start

Four things block this runbook if they are not in place.

| Check | Why it matters |
|---|---|
| Subscription and Entra tenant confirmed | Both are effectively permanent for these resources. |
| **Contributor _and_ Role Based Access Control Administrator** on the resource group | Contributor cannot assign roles. Without the second role this runbook stops at step 6. Owner covers both. |
| `az login` succeeds from your device | Conditional Access can block an unmanaged device. An `AADSTS53000` or `AADSTS53003` code means a policy refused it, not that your account lacks rights. |
| Nobody else holds the free AI Search service | Only one free search service exists per subscription. |

Two properties cannot be changed after creation: **region** and **name**.
Everything goes in **West Europe**. The storage account and web app names must be
globally unique across all of Azure; the storage account allows only lowercase
letters and digits — if a name is taken, append `etil`.

Add these tags on every resource, from the Tags tab of each Create page:

| Tag | Value |
|---|---|
| `project` | `sip` |
| `environment` | `dev` |
| `owner` | your name or email |

Without them the SIP resources are indistinguishable from every other project's
in Cost Management.

## How to assign a role

Steps 6 through 9 each end with a role assignment. The procedure is identical
every time:

1. Open the resource
2. **Access control (IAM)** → **+ Add** → **Add role assignment**
3. **Role** tab → search the role name → select it
4. **Members** tab → Assign access to **Managed identity** → **+ Select members**
   → Managed identity: **App Service** → `app-sip-dev-weu`
5. **Review + assign**

Always assign on the resource itself, never on the resource group. A role granted
at group scope covers everything in that group, including resources added later,
which is the usual way too much access is handed out by accident.

## Steps

### 1. Resource group

Search **Resource groups** → **+ Create**.

| Field | Value |
|---|---|
| Subscription | the ETIL subscription |
| Resource group | `rg-sip-dev-weu` |
| Region | West Europe |

A resource group's region only stores its metadata; the resources inside choose
their own. Keeping them identical avoids confusion later.

One resource group per environment. Production gets its own, so that granting a
role there is a deliberate act rather than an accident.

### 2. Log Analytics workspace

Search **Log Analytics workspaces** → **+ Create**.

| Field | Value |
|---|---|
| Resource group | `rg-sip-dev-weu` |
| Name | `log-sip-dev-weu` |
| Region | West Europe |

Create this before Application Insights, which asks for it.

### 3. Application Insights

Search **Application Insights** → **+ Create**.

| Field | Value |
|---|---|
| Name | `appi-sip-dev-weu` |
| Region | West Europe |
| Resource Mode | **Workspace-based** |
| Log Analytics Workspace | `log-sip-dev-weu` |

Because the application is debugged in Azure rather than through a debugger, this
resource is the primary diagnostic instrument. If telemetry does not arrive here,
nothing else can be diagnosed.

### 4. App Service plan

Search **App Service plans** → **+ Create**.

| Field | Value |
|---|---|
| Name | `plan-sip-dev-weu` |
| Region | West Europe |
| Operating system | Linux |
| Pricing plan | **B1 Basic** |

The plan is the machine; the web app is what runs on it. B1 costs €11.28 per
month in West Europe and is enough for development. Several small apps can share
one plan, so a later test environment can run alongside on this same plan.
Production gets its own, so that a test run cannot slow it down.

Deployment slots require Standard, Premium or Isolated, and Linux plans no longer
offer Standard — the cheapest tier with slots is Premium v4 (P0v4) at €65.19 per
month. Development rolls back by redeploying the previous build instead.

### 5. Web App

Search **App Services** → **+ Create** → **Web App**.

| Tab | Field | Value |
|---|---|---|
| Basics | Name | `app-sip-dev-weu` — becomes `app-sip-dev-weu.azurewebsites.net` |
| Basics | Publish | Code |
| Basics | Runtime stack | the .NET version the project targets |
| Basics | Operating system | Linux |
| Basics | Region | West Europe |
| Basics | App Service plan | `plan-sip-dev-weu` |
| Monitoring | Application Insights | Enable → `appi-sip-dev-weu` |

No container image is involved: the pipeline publishes compiled .NET output
directly, which is why this environment needs no Dockerfile and no container
registry.

Then, in the new web app, open **Settings → Identity → System assigned** and set
**Status** to **On**.

That one switch creates the application's identity in Entra ID. It has no
permissions yet — an identity is only a *who*, never a *may* — and the steps
below grant it exactly what it needs and nothing else. Because the identity
belongs to this single app, `DefaultAzureCredential` finds it without being told
which identity to use, so no client ID has to be configured anywhere.

**Record the application URL.** Microsoft Entra ID needs it later as the redirect
URI, and it is where the first deployment is verified.

### 6. Storage account

Search **Storage accounts** → **+ Create**.

| Tab | Field | Value |
|---|---|---|
| Basics | Name | `stsipdevweu` |
| Basics | Region | West Europe |
| Basics | Primary service | Azure Blob Storage |
| Basics | Performance | Standard |
| Basics | Redundancy | **LRS** (three copies in one datacenter; production uses ZRS) |
| Security | Require secure transfer | on (default) |
| Security | Allow anonymous access on individual containers | **off** |
| Security | Minimum TLS version | 1.2 |

Then **Data storage → Containers → + Container**, three times, all with access
level **Private**:

- `curated-knowledge` — reviewed website and organisational sources
- `private-uploads` — user-owned documents
- `approved-evidence` — documents approved for wider retrieval

The containers organise the data and make per-container permissions possible;
they do not by themselves enforce SIP's visibility model. That remains the
application's responsibility.

**Role:** `Storage Blob Data Contributor`

### 7. Key Vault

Search **Key vaults** → **+ Create**.

| Tab | Field | Value |
|---|---|---|
| Basics | Name | `kv-sip-dev-weu` |
| Basics | Region | West Europe |
| Basics | Pricing tier | Standard |
| Basics | Soft-delete retention | 7 days |
| Basics | Purge protection | **off** for development |
| Access configuration | Permission model | **Azure role-based access control** |

The permission model matters. Vault access policies are a separate, older system
that would have to be maintained alongside RBAC. Purge protection stays off in
development because it blocks reuse of a deleted vault's name for 90 days, and
during setup you want to be able to delete and start over. Production turns it on.

**Role:** `Key Vault Secrets User` — read access is enough, because the
application never writes secrets.

### 8. Azure AI Search

Search **AI Search** → **+ Create**.

| Field | Value |
|---|---|
| Name | `srch-sip-dev-weu` |
| Region | West Europe |
| Pricing tier | **Change Pricing Tier → Free** |

West Europe supports agentic retrieval and the semantic ranker on the free tier,
so the full Foundry IQ behaviour is available at no cost. The corpus in
`knowledge/` is roughly 316 KB and produces an index of about 8 MB, comfortably
inside the free tier's 50 MB.

Keep the development index limited to that public corpus. Private uploads do not
belong in a development search index.

**Roles:** `Search Service Contributor` (manage indexes and knowledge bases) and
`Search Index Data Contributor` (write data into them).

### 9. Foundry project

No new resource — verify the existing one.

| Check | |
|---|---|
| Subscription | the same one as the resources above |
| Tenant | the ETIL tenant |
| Region | West Europe |
| Ownership | not a personal or trial environment |

If any of these is wrong, the project moves or is recreated before the
application is pointed at it. A Foundry project has no standing cost; only token
usage is billed.

**Role:** the inference role. The portal offers `Cognitive Services OpenAI User`
and `Azure AI Developer` among others; which applies depends on how the project
was created. Pick the one available on this resource.

## Verify before moving on

Check each of these. A missing role surfaces later as a `403` on an endpoint that
exists, which is easy to mistake for a bug in the application.

| Resource | Expected role for `app-sip-dev-weu` |
|---|---|
| `stsipdevweu` | Storage Blob Data Contributor |
| `kv-sip-dev-weu` | Key Vault Secrets User |
| `srch-sip-dev-weu` | Search Service Contributor |
| `srch-sip-dev-weu` | Search Index Data Contributor |
| Foundry project | inference role |

Per resource: **Access control (IAM) → Role assignments**, filtered on the
application name.

Then record these values; the application and the pipeline both need them.

- Blob endpoint — `https://stsipdevweu.blob.core.windows.net`
- Key Vault URI — `https://kv-sip-dev-weu.vault.azure.net`
- Search endpoint — `https://srch-sip-dev-weu.search.windows.net`
- Application URL — `https://app-sip-dev-weu.azurewebsites.net`

## What this does not create

| Resource | When | Why not now |
|---|---|---|
| DevOps project and service connection | next phase | belongs with the pipeline |
| Azure SQL | when the data layer is written | the first substantial fixed cost; create it when work on it starts |
| Production environment | last | only after backup, restore, retrieval permissions and data residency are approved |

Production repeats this runbook with `prod` in every name, in its own resource
group, with its own web app and therefore its own identity. That identity is
never granted a role on a development resource, and the development identity is
never granted one on a production resource.

That absence is the whole separation mechanism. A managed identity carries no
permissions of its own; each resource keeps its own list of who may do what. When
the development application calls a production endpoint, the production resource
looks in its list, does not find that identity, and returns `403`. Nothing has to
be blocked, because nothing was ever allowed.

It is also why a leaked endpoint is not a leaked secret. Pasting a production
address into a development configuration gives that application the address, not
the access — which is not true of a connection string or an API key, where
possession is permission.

## Cost after this runbook

The App Service plan is the only meaningful line: **B1 at €11.28 per month**.
AI Search is on the free tier, the Foundry project has no standing cost, the
resource group and the managed identity are free, and storage, Key Vault and
monitoring bill by usage at cents per month.

The next fixed cost arrives with Azure SQL, and the two after that in production:
its own App Service plan and AI Search on Basic.

Prices are list prices excluding VAT for West Europe, checked on 22 September
2026. Verify them before quoting them in a budget.
