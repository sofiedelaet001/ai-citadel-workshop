# Product Finder Custom Use Case: Deployment Order and Governance Scope

## Direct Answer to Deployment Order

Yes, agents need to be deployed and reachable before the orchestrator can call them at runtime.

Agents can be pre-registered in API Center as draft, but the recommended workshop order is to deploy specialist agents first, then publish active registry entries.

Recommended lifecycle per agent:

1. Deploy hosted agent version in Foundry
- Build image
- Deploy hosted agent
- Verify active state and health

2. Publish runtime endpoint and version in API Center
- Update API Center metadata with deployed version and endpoint contract
- status = active

3. Sync API Center to runtime discovery cache
- Materialize a deployment snapshot for orchestrator routing
- Include snapshot version and checksum

4. Deploy or reload orchestrator
- Orchestrator only routes to status=active entries with health=healthy and environment match

Optional governance-preparation step:

- Create draft entries in API Center before deployment for review only
- Never allow runtime selection of draft entries

## Citadel-Aligned Best Practices (APIM and Governance First)

This custom use case will follow these non-negotiable rules:

1. All model and agent traffic through APIM
- No direct client calls to model endpoints.
- APIM remains the unified AI gateway.

2. Use Citadel governance layers
- Access contracts and policy enforcement remain in the hub.
- Spoke agents conform to governance controls, not bypass them.

3. Keep identity and RBAC least-privileged
- Use managed identities where possible.
- Assign only required roles for each agent identity.

4. Policy and traceability by default
- Enforce policy checks before execution for risky operations.
- Emit audit and telemetry events for routing decisions and final bundles.

5. Explicit risk handling
- Compatibility requests require disclaimer gating and confidence threshold checks.
- Low confidence in elevated-risk flows leads to refusal with explanation.

6. Deterministic deployment sync
- Every deployment performs API Center -> runtime discovery sync.
- Deployment fails if sync validation fails.

## Workshop Permission Baseline (Owner-Only Mode)

For this custom Product Finder workshop, execution is designed to work with:
- Azure subscription `Owner` rights
- No Entra ID app registration/admin permissions

Operational implications for workshop mode:
- Reuse the existing deployed Citadel spoke by default.
- Use APIM subscription key plus persona simulation (`x-user-persona` and governance context block).
- Do not require Entra app registration changes during the workshop flow.
- Keep production JWT + Entra integration as a post-workshop hardening step.

## Runtime Discovery Model

Control plane source of truth:
- API Center

Runtime selection store:
- Runtime discovery snapshot generated at deploy time
- Stored in a local runtime-friendly form (for example JSON artifact or Cosmos item)

Selection guardrails in orchestrator:
- status must be active
- trust level must satisfy risk tier
- persona must be allowed
- capability must match intent
- endpoint health must be healthy

## Pre-Scenario Readiness Gates (Mandatory)

All gates below must be complete before running scenario notebooks.

1. Platform and APIM gate
- Citadel hub and spoke deployment healthy
- APIM endpoint reachable
- Product Finder APIs routed through APIM only

2. Identity and authorization gate
- APIM subscription key policy enabled for Product Finder API calls
- Persona resolution mapping configured:
	- external_customer
	- internal_scientist
- Authorization policy matrix validated in APIM and orchestrator using workshop persona simulation
- (Optional production hardening) JWT + Entra claims validation

3. Data gate
- Product Finder dataset loaded (product descriptions, technical notes, compatibility matrix)
- Required data indexes/materialized views created
- Data quality checks pass (required fields, unique ids, compatibility coverage)

4. Specialist agent gate
- Specialist agents deployed and active in Foundry
- Health checks pass for each specialist agent
- Required agent identities and RBAC role assignments validated

5. API Center registry gate
- Deployed specialist agents registered in API Center with active status
- Metadata schema validation passes
- Capability, persona, trust, and risk fields populated

6. Runtime discovery sync gate
- API Center -> runtime discovery snapshot generated
- Snapshot checksum and version recorded
- Orchestrator configured to load latest valid snapshot

7. Orchestrator gate
- Orchestrator deployed after sync
- Startup validation confirms discoverable active specialists
- Dry-run routing tests pass for recommendation and compatibility intents

## Folder Layout for This Custom Use Case

Everything for Product Finder lives under:

- workshop/product-finder/

Proposed working structure:

- workshop/product-finder/docs/
- workshop/product-finder/notebooks/
- workshop/product-finder/agents/
- workshop/product-finder/registry/
- workshop/product-finder/sync/
- workshop/product-finder/data/
- workshop/product-finder/scripts/

## Notebook Plan (Sequential Execution)

1. Notebook 1: Foundation and Prerequisite Validation
- Verify Citadel/APIM baseline and environment variables
- Confirm existing hub-spoke dependencies are healthy

2. Notebook 2: Data Readiness and Quality Validation
- Load or validate workshop data pack
- Validate required fields, ids, and compatibility coverage
- Validate retrieval readiness for scenario execution

3. Notebook 3: Deploy Specialist Agents
- Build/push images
- Deploy Foundry hosted specialist agents
- Verify active status and identity/RBAC

4. Notebook 4: API Center Registration and Runtime Discovery Sync
- Register deployed specialist agents in API Center
- Validate metadata schema and active status
- Generate runtime snapshot from API Center
- Validate checksum and activate snapshot

5. Notebook 5: Deploy Orchestrator and Run Routing Smoke Tests
- Deploy orchestrator after runtime sync
- Verify orchestrator discovers active specialists from snapshot
- Run routing smoke tests for low-risk and elevated-risk intents

6. Notebook 6: Identity, Authorization, and Persona Setup Validation
- Validate APIM subscription-key access and persona simulation prerequisites
- Validate persona mapping rules for external and internal users
- Run auth simulation tests for persona resolution

7. Notebook 7: Dynamic Routing and Bundled Response Validation
- Run external customer scenarios
- Run internal scientist scenarios
- Confirm multi-agent bundle structure and governance behavior

8. Notebook 8: Observability and Governance Evidence
- Validate traces for routing decisions, policy gates, disclaimers, and confidence checks

9. Notebook 9: Optional Cleanup
- Controlled teardown for workshop reset

## Requirement Coverage Map

- Dynamic routing by metadata and intent: Notebooks 4, 5, 7
- Multi-agent interaction and bundled answer: Notebook 7
- APIM-only governed traffic: Notebooks 1, 5, 6, 7
- Runtime sync on every deployment: Notebook 4 (mandatory)
- Data readiness before scenarios: Notebook 2 (mandatory)
- Persona-aware auth and authorization readiness: Notebook 6 (mandatory)
- Auditability and compliance evidence: Notebook 8

## Implementation Decision to Lock In

Use API Center as the control-plane registry, but never query it directly in hot-path runtime routing. Always route via the deployment-synced runtime snapshot.

This gives governance consistency, lower latency, deterministic behavior, and safer workshop execution.
