# Azure provisioning runbook — development environment

Status: ready to execute
Last updated: 22 September 2026

Step-by-step creation of the SIP development environment in the Azure portal.
The order matters: the managed identity is created first so that every resource
can be granted its role at the moment it is created, leaving no separate RBAC
pass at the end.

This runbook stops short of the Container App, Azure SQL and the DevOps service
connection. Those belong to later phases and are listed under
[What this does not create](#what-this-does-not-create).

See [Agreed direction](../README.md#agreed-direction) for the decisions behind
these choices.

## Before you start

Four things block this runbook if they are not in place.

| Check | Why it matters |
|---|---|
| Subscription and Entra tenant confirmed | Both are effectively permanent for these resources. |
| **Contributor _and_ Role Based Access Control Administrator** on the resource group | Contributor cannot assign roles. Without the second role this runbook stops at step 5. Owner covers both. |
| `az login` succeeds from your device | Conditional Access can block an unmanaged device. An `AADSTS53000` or `AADSTS53003` code means a policy refused it, not that your account lacks rights. |
| Nobody else holds the free AI Search service | Only one free search service exists per subscription. |

Two properties cannot be changed after creation: **region** and **name**.
Everything goes in **West Europe**. Storage account and container registry names
must be globally unique across all of Azure and allow only lowercase letters and
digits — if a name is taken, append `etil`.

Add these tags on every resource, from the Tags tab of each Create page:

| Tag | Value |
|---|---|
| `project` | `sip` |
| `environment` | `dev` |
| `owner` | your name or email |

Without them the SIP resources are indistinguishable from every other project's
in Cost Management.

## How to assign a role

Steps 5 through 9 each end with a role assignment. The procedure is identical
every time:

1. Open the resource
2. **Access control (IAM)** → **+ Add** → **Add role assignment**
3. **Role** tab → search the role name → select it
4. **Members** tab → Assign access to **Managed identity** → **+ Select members**
   → Managed identity: **User-assigned** → `id-sip-dev-weu`
5. **Review + assign**

Always assign on the resource itself, never on the resource group. That keeps
each grant as narrow as the application actually needs.

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

### 2. User-assigned managed identity

Search **Managed Identities** → **+ Create**.

| Field | Value |
|---|---|
| Resource group | `rg-sip-dev-weu` |
| Region | West Europe |
| Name | `id-sip-dev-weu` |

This comes before every other resource because a user-assigned identity is a
standalone resource. A system-assigned identity would only exist once the
Container App existed, which would push all role assignments to the end of the
migration.

**Open the identity and record two values from its Overview page:**

| Value | Needed for |
|---|---|
| Client ID | the `AZURE_CLIENT_ID` setting on the Container App |
| Object (principal) ID | verifying role assignments |

`DefaultAzureCredential` cannot guess which user-assigned identity to use. Without
`AZURE_CLIENT_ID` the application fails to authenticate, and the error does not
say why.

### 3. Log Analytics workspace

Search **Log Analytics workspaces** → **+ Create**.

| Field | Value |
|---|---|
| Resource group | `rg-sip-dev-weu` |
| Name | `log-sip-dev-weu` |
| Region | West Europe |

Create this before Application Insights, which asks for it.

### 4. Application Insights

Search **Application Insights** → **+ Create**.

| Field | Value |
|---|---|
| Name | `appi-sip-dev-weu` |
| Region | West Europe |
| Resource Mode | **Workspace-based** |
| Log Analytics Workspace | `log-sip-dev-weu` |

**Record the Connection String** from the Overview page — not the older
Instrumentation Key.

Because the application is debugged in Azure rather than through a debugger,
this resource is the primary diagnostic instrument. If telemetry does not arrive
here, nothing else can be diagnosed.

### 5. Storage account

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

### 6. Key Vault

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

### 7. Azure AI Search

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

### 8. Foundry project

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

### 9. Container Registry

Search **Container registries** → **+ Create**.

| Field | Value |
|---|---|
| Name | `crsipdevweu` |
| Region | West Europe |
| SKU | Basic |

**Role:** `AcrPull` — so the application pulls its own image with the managed
identity. The registry's admin account stays disabled.

### 10. Container Apps environment

Search **Container Apps** → **+ Create** → create the environment.

| Field | Value |
|---|---|
| Environment name | `cae-sip-dev-weu` |
| Region | West Europe |
| Log Analytics workspace | `log-sip-dev-weu` |

The environment is the shared surroundings — networking, logging, certificates.
The Container App itself is created in the next phase, when there is an image to
run.

## Verify before moving on

Check each of these; a missing role surfaces later as a `403` on an endpoint
that exists, which is hard to recognise for what it is.

| Resource | Expected role for `id-sip-dev-weu` |
|---|---|
| `stsipdevweu` | Storage Blob Data Contributor |
| `kv-sip-dev-weu` | Key Vault Secrets User |
| `srch-sip-dev-weu` | Search Service Contributor |
| `srch-sip-dev-weu` | Search Index Data Contributor |
| Foundry project | inference role |
| `crsipdevweu` | AcrPull |

Per resource: **Access control (IAM) → Role assignments**, filtered on the
identity.

Then record these five values; the application and the pipeline both need them.

- Blob endpoint — `https://stsipdevweu.blob.core.windows.net`
- Key Vault URI — `https://kv-sip-dev-weu.vault.azure.net`
- Search endpoint — `https://srch-sip-dev-weu.search.windows.net`
- Registry login server — `crsipdevweu.azurecr.io`
- Application Insights connection string
- The identity's Client ID

## What this does not create

| Resource | When | Why not now |
|---|---|---|
| Container App | next phase | needs an image to run |
| DevOps project and service connection | next phase | belongs with the pipeline |
| Azure SQL | when the data layer is written | the first real fixed monthly cost; create it when work on it starts |
| Production environment | last | only after backup, restore, retrieval permissions and data residency are approved |

## Cost after this runbook

Close to nothing. AI Search is on the free tier, the Foundry project has no
standing cost, the managed identity and resource group are free, and storage,
Key Vault and monitoring bill by usage at cents per month. The container registry
carries a small fixed charge. The first substantial fixed cost arrives with
Azure SQL, and the second when AI Search moves to Basic for production.
