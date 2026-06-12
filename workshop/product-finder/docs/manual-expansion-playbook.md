# Product Finder Manual Expansion Playbook

## Purpose

This guide describes the manual steps required to expand the Product Finder flow with:

- New specialist agents
- New routing/governance behavior
- New APIM/API Center contract and discovery capabilities

It is intended for engineers who want to extend the existing workshop implementation while preserving Citadel governance patterns.

## Scope and Principles

The current flow is APIM-first and governance-first:

- All model and agent traffic routes through APIM
- Specialist agents are deployed first, then registered for discovery
- Runtime selection is metadata-driven
- Access contracts and policy controls are required, not optional

Keep this deployment order:

1. Foundation and model-access contract
2. Data readiness
3. Specialist deploy
4. APIM specialist exposure
5. API Center registration and discovery sync
6. Orchestrator smoke and scenarios
7. Observability validation

## Repository Areas You Will Touch

- workshop/product-finder/agents/
- workshop/product-finder/access-contracts/contracts/
- workshop/product-finder/registry/governance-contract/
- workshop/product-finder/notebooks/
- workshop/product-finder/docs/

## A. Add a New Specialist Agent (Manual Steps)

### 1) Define the agent contract first

Before writing code, define:

- Agent name (use pf- prefix)
- Intent coverage
- Allowed personas
- Risk tiers supported
- Inputs required
- Outputs produced
- Run order dependencies

Use governance schema constraints from:

- workshop/product-finder/registry/governance-contract/governance-profile.template.json

### 2) Create the agent folder and runtime files

Create a new folder under workshop/product-finder/agents/, following existing agents:

- agent.yaml
- main.py
- Dockerfile
- requirements.txt

Reference patterns:

- workshop/product-finder/agents/pf-contextualizer/
- workshop/product-finder/agents/pf-product-intelligence/
- workshop/product-finder/agents/pf-compatibility/
- workshop/product-finder/agents/pf-aligner/
- workshop/product-finder/agents/pf-sample-request/

### 3) Add environment variables in agent.yaml

Ensure your new agent.yaml includes all required variables for:

- Model call path through APIM
- Optional retrieval dependencies (search endpoint/index/key)
- Telemetry service name

### 4) Add deployment inclusion in Notebook 3

Update specialist lists and source-generation/mapping logic in:

- workshop/product-finder/notebooks/3. product-finder-deploy-specialists.ipynb

Make sure your new specialist is included where the existing specialist list is defined.

### 5) Build and deploy specialist image

Run Notebook 3 to:

- Build and push image to ACR
- Deploy hosted specialist to Foundry project
- Persist updated PF_DEPLOYED_SPECIALISTS in azd env

If this step is skipped, APIM exposure and API Center registration will not include your agent.

## B. Expose New Specialist Through APIM

### 6) Refresh APIM dynamic routing setup

Run Notebook 4:

- workshop/product-finder/notebooks/4. product-finder-apim-specialists-exposure.ipynb

This notebook:

- Reads PF_DEPLOYED_SPECIALISTS
- Creates/updates APIM backend for Foundry project
- Maintains dynamic route /agents/{agent}/invoke
- Persists runtime routes/keys

### 7) Validate agent-access APIM policy behavior

Review and adjust if needed:

- workshop/product-finder/access-contracts/contracts/pf-productfinderagentaccess/dev/ai-product-policy.xml

Confirm:

- Path parsing still resolves new agent name
- Rate limits and security behavior meet requirements
- Rewrite URI points to correct Foundry responses endpoint

### 8) Update agent-access contract params if needed

Review and adjust contract parameters:

- workshop/product-finder/access-contracts/contracts/pf-productfinderagentaccess/dev/main.bicepparam

Use this when adding APIs, changing Key Vault secret names, or modifying Foundry connection details.

## C. Keep Model Access Contract Aligned

### 9) Expand model allow-list and model contract policy

If new functionality requires additional models:

- Update model policy allow-list in:
  - workshop/product-finder/access-contracts/contracts/pf-productfindermodelaccess/dev/ai-product-policy.xml
- Review contract parameters in:
  - workshop/product-finder/access-contracts/contracts/pf-productfindermodelaccess/dev/main.bicepparam

### 10) Re-run Notebook 1 when model contract changes

Notebook 1 establishes the Product Finder model-access contract and saves key settings used by downstream notebooks.

- workshop/product-finder/notebooks/1. product-finder-foundation-prereq.ipynb

## D. Register Governance Metadata in API Center

### 11) Add metadata profile for the new specialist

Add full metadata for the new agent in Notebook 5 profile map:

- workshop/product-finder/notebooks/5. product-finder-api-center-sync.ipynb

Required fields include:

- agent_name
- description
- capabilities
- supported_intents
- allowed_personas
- risk_tiers_supported
- orchestration_stage
- execution_order
- run_after
- requires_disclaimer
- trust_level
- verification_status
- enabled

### 12) Regenerate governance contract artifacts

Notebook 5 writes/updates:

- workshop/product-finder/registry/governance-contract/governance-profile.template.json
- workshop/product-finder/registry/governance-contract/governance-profile.params.json

Validate that the new specialist appears in params with complete metadata.

### 13) Re-register APIs and discovery metadata

Run Notebook 5 end to end to publish specialist metadata into API Center and persist discovery configuration for orchestrator use.

## E. Update Orchestrator Logic for New Functionality

### 14) Decide if functionality can be metadata-only or needs code changes

Metadata-only change examples:

- New specialist route order
- Persona/risk gating
- Disclaimer requirements

Code change examples:

- New hard-coded wrapper behavior
- New tool invocation pattern
- New response contract fields

### 15) If needed, update orchestrator source

Edit:

- workshop/product-finder/agents/pf-orchestrator/main.py

Common manual updates:

- Wrapper/core classification logic (if new wrapper-like agent)
- Additional governance stop conditions
- Expanded route planning constraints
- Output payload contract updates

Also ensure orchestrator runtime env values in:

- workshop/product-finder/agents/pf-orchestrator/agent.yaml

## F. Re-validate End-to-End Flow

### 16) Run smoke and scenarios

Run notebooks in this order:

1. workshop/product-finder/notebooks/6. product-finder-orchestrator-smoke.ipynb
2. workshop/product-finder/notebooks/7. product-finder-scenario-recommendation.ipynb
3. workshop/product-finder/notebooks/8. product-finder-scenario-compatibility.ipynb
4. workshop/product-finder/notebooks/9. product-finder-scenario-scientist.ipynb

Confirm:

- New specialist appears in discovery
- It is selected only when governance allows
- Blocking/disclaimer behavior is correct

### 17) Validate telemetry and governance evidence

Run:

- workshop/product-finder/notebooks/10. product-finder-observability.ipynb

Check:

- APIM request paths and status codes
- Token usage visibility
- Governance decision evidence in logs/traces

## G. Manual Expansion Checklist (Quick Use)

Use this checklist for each expansion:

- [ ] Agent contract defined (intent/persona/risk/input/output/dependencies)
- [ ] New agent folder created with agent.yaml, main.py, Dockerfile, requirements.txt
- [ ] Notebook 3 updated and re-run
- [ ] APIM exposure refreshed via Notebook 4
- [ ] Agent-access policy validated
- [ ] Model-access policy/contract updated if needed
- [ ] API Center metadata profile added in Notebook 5
- [ ] Governance profile params regenerated
- [ ] Orchestrator code updated if metadata-only routing is insufficient
- [ ] Notebooks 6-9 pass functional checks
- [ ] Notebook 10 confirms observability/governance signals

## H. Common Failure Modes

- Agent deployed but not discoverable:
  - Notebook 5 not re-run or metadata incomplete
- Agent discoverable but never selected:
  - supported_intents or persona/risk filters do not match incoming context
- Agent selected but call fails:
  - APIM route or rewrite policy mismatch
- Model call fails from specialist:
  - model access contract/allow-list does not include required model
- Compatibility flow fails unexpectedly:
  - disclaimer/trust-level metadata blocks elevated-risk path

## I. Recommended Change Strategy

For each new capability, apply this sequence:

1. Add specialist with minimal logic and strict metadata
2. Validate APIM exposure and API Center registration
3. Verify orchestrator routing decisions in smoke tests
4. Expand behavior incrementally
5. Capture evidence in observability notebook

This keeps governance behavior predictable and reduces multi-layer debugging.