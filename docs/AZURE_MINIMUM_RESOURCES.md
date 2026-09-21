# Minimum Azure resources for SIP

Status: discussion checklist  
Last updated: 21 September 2026

This is the minimum Azure setup needed to move the current SIP proof of concept
from Railway to Azure and replace the local retrieval index with Foundry IQ. Review
this list with the senior developer before resources are provisioned.

## Minimum required resources

| Resource | Why SIP needs it | Required for first Azure version |
|---|---|---|
| **Resource group** | Keeps the SIP resources, access and lifecycle together. | Yes |
| **Microsoft Foundry project** | Hosts the chat model and connects the application to Foundry capabilities. The existing project can be reused if its tenant, region and ownership are suitable. | Yes |
| **Azure AI Search** | Mandatory foundation for a Foundry IQ knowledge base. It provides the underlying indexed and agentic retrieval. This is a separate Azure resource and cost item. | Yes for Foundry IQ |
| **Foundry IQ knowledge base** | Becomes SIP's managed knowledge and retrieval layer. It replaces SIP's local `vectors.bin`, custom RRF and corpus indexing. | Yes for retrieval migration |
| **Azure Storage account with Blob Storage** | Stores the reviewed website corpus and uploaded documents independently from the application container. | Yes |
| **Azure Container Registry** | Stores immutable SIP container images built from GitHub. | Yes |
| **Azure Container Apps environment and app** | Runs the current FastAPI/Docker application. It can also run a later ASP.NET Core version without changing the hosting model. | Yes |
| **Azure Database for PostgreSQL Flexible Server** | Replaces SQLite for users, conversations, Business Contexts, portfolio records and document metadata. Works from both Python and C#. | Yes before production data |
| **Microsoft Entra ID app registration** | Replaces demo usernames and passwords with organisation-managed login. | Yes before real users |
| **Managed identity and Azure RBAC assignments** | Lets SIP access Storage, PostgreSQL, Key Vault, Foundry and Search without embedding credentials in code. | Yes |
| **Azure Key Vault** | Holds only the secrets that cannot be replaced by managed identity. | Yes |
| **Log Analytics workspace and Application Insights** | Central logging, request tracing, dependency monitoring and alerts. | Yes |

## Models

At minimum, the Foundry environment needs:

- one chat model deployment for the Product Strategist and Knowledge Assistant;
- a Foundry IQ-compatible model when LLM-based query planning or answer synthesis
  is enabled;
- an embedding deployment if required by the selected indexed knowledge-source
  configuration.

Do not create duplicate model deployments until the Foundry IQ configuration and
current project resources have been inventoried.

## Minimum data layout

```text
Azure Blob Storage
├── curated-knowledge/       reviewed website and organisational sources
├── private-uploads/         user-owned documents, private by default
└── approved-evidence/       documents explicitly approved for wider retrieval

Azure Database for PostgreSQL
├── users and role mappings
├── conversations and messages
├── Business Contexts and approval state
├── portfolio records
└── upload metadata, ownership and visibility
```

The storage containers alone do not enforce SIP's complete permission model. Entra
identity, application authorisation and Foundry IQ knowledge-source permissions
must agree on what is private and what is organisation-wide.

## Connections that should use managed identity

The SIP Container App should use managed identity for:

- Azure Blob Storage;
- Azure Key Vault;
- Microsoft Foundry/model access;
- Azure AI Search and Foundry IQ;
- PostgreSQL where the chosen database configuration supports Entra authentication;
- pulling images from Azure Container Registry.

API keys and connection-string passwords are a fallback, not the target design.

## Required environments

Start with two isolated environments:

1. **Development** — synthetic or non-sensitive data, used for integration and
   Foundry IQ evaluation.
2. **Production** — created only after identity, retrieval permissions, backup,
   restore and data residency have been approved.

A separate acceptance environment can be added when external stakeholders need a
stable test system. It is not required for the first Azure development deployment.

## Not required initially

Do not add these without a demonstrated need:

- Kubernetes or Azure Kubernetes Service;
- multiple application microservices;
- Service Bus, Redis or Event Grid;
- API Management;
- Azure Front Door;
- a second custom vector database;
- a C# rewrite before the existing application runs correctly in Azure;
- separate Python and .NET backends without a real ownership boundary.

These can be added later when scale, integration or security requirements justify
them.

## Decisions for the technical review

Resolve these questions before provisioning production resources:

- [ ] Which Azure subscription and resource group will own SIP?
- [ ] Which Microsoft Entra tenant will authenticate IBC Group and ETIL users?
- [ ] Which approved EEA region supports Container Apps, Foundry, Foundry IQ,
      Azure AI Search, Storage and PostgreSQL for this project?
- [ ] Can the existing Foundry project be reused, or should SIP receive a dedicated
      project?
- [ ] Which Azure AI Search tier supports the agreed Foundry IQ configuration and
      expected usage?
- [ ] Which model deployments already exist and can be reused?
- [ ] Is PostgreSQL accepted, or is Azure SQL an organisational standard?
- [ ] Which SIP roles map to which Entra users or groups?
- [ ] How are private uploads represented and filtered in Foundry IQ?
- [ ] Who owns Azure infrastructure, application support and security review?
- [ ] What budget and cost alerts apply to Search, models and Container Apps?
- [ ] What backup retention, restore target and deletion policy are required?

## Recommended provisioning order

1. Confirm subscription, tenant, EEA region, owners and budget.
2. Create the resource group, monitoring and Key Vault.
3. Create Container Registry and the Container Apps development environment.
4. Enable managed identity and RBAC.
5. Create Blob Storage and PostgreSQL.
6. Inventory or create the Foundry project and model deployments.
7. Create Azure AI Search and the Foundry IQ knowledge base.
8. Deploy SIP from GitHub using synthetic data.
9. Configure Entra ID and role mapping.
10. Validate retrieval, privacy, backup, restore and monitoring before creating the
    production environment.

## Related documentation

- [Full Azure target architecture and migration plan](AZURE_TARGET_ARCHITECTURE.md)
- [POC-to-production technical migration notes](../MIGRATION.md)
- [Foundry IQ FAQ](https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/foundry-iq-faq)
- [Authentication in Azure Container Apps](https://learn.microsoft.com/en-us/azure/container-apps/authentication)
- [Managed identities in Azure Container Apps](https://learn.microsoft.com/en-us/azure/container-apps/managed-identity)

