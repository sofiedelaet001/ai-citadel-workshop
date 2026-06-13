# Product Finder Manual Expansion Playbook

## Purpose

This guide describes the manual steps required to expand the Product Finder flow with new specialist agents (and features).

It is intended for engineers that want to extend the existing workshop implementation while preserving Citadel governance patterns to understand the amount of manual work (and correct order) required to do so.

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

## A. Add a New Specialist Agent (Manual Steps)

### 1) Define the agent contract first (manual)

Before writing code, define:

- Agent name (use pf- prefix)
- Agent Required Metadata
  - Intent coverage
  - Allowed personas
  - Risk tiers supported
  - Inputs required
  - Outputs produced
  - Run order dependencies

Use governance schema constraints from:

- workshop/product-finder/registry/governance-contract/governance-profile.template.json

### 2) Create the runtime files with the required environment variables (automated)

By creating a script (inspire by notebook 3) the following files can be generated automatically:

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

### 3) Build and deploy specialist image (automated)

Also scriptable:

- Build and push image to ACR
- Deploy hosted specialist to Foundry project
- Persist updated PF_DEPLOYED_SPECIALISTS in azd env

## B. Expose New Specialist Through APIM (out-of-the-box)

PF orchetrator uses a single APIM endpoint with a param to specify the specific specialized agent to call, therefore no changes are required here when onbaoarding a new specialized agent.

## C. Keep Model Access Contract Aligned (manual)

If new functionality requires additional models, the model-access contract APIM policy 'allow-list' must be expanded.

## D. Register Governance Metadata in API Center (automated)

Publish specialist metadata (generated in step D.4) into API Center and persist discovery configuration for orchestrator use. (scriptable - inspired by notebook 5)

## E. Update Orchestrator Logic for New Functionality

### 4) Decide if functionality can be metadata-only or needs code changes

Metadata-only change examples:

- New specialist route order
- Persona/risk gating
- Disclaimer requirements

### 5) If needed, update orchestrator source (manual)

Common manual updates:

- Core classification logic (Expanded route planning constraints)
- Additional governance stop conditions
- Output payload contract updates

## F. Re-validate End-to-End Flow (automated)

### 6) Run smoke and scenarios

Run smoke tests and confirm:

- New specialist appears in discovery
- It is selected only when governance allows
- Blocking/disclaimer behavior is correct
- etc ...

### 7) Validate telemetry and governance evidence (automated)

Check:

- APIM request paths and status codes
- Token usage visibility
- Governance decision evidence in logs/traces

## G. Manual Expansion Checklist (Quick Use)

Use this checklist for each expansion:

- [ ] Agent contract defined
- [ ] Running scripts for agent runtime files creation and agent building and deployment
- [ ] Expland model access contract (OPTIONAL)
- [ ] Running Scripts to publish agents & custom metadata to API Center
- [ ] Update Orchestrator logic (OPTIONAL)
- [ ] Testing and Telemetry observation

## H. Common Failure Modes

- Agent deployed but not discoverable:
  - API Center publishing missing
- Agent discoverable but never selected:
  - supported_intents or persona/risk filters do not match incoming context (improve metadata of specialized agent)
- Agent selected but call fails:
  - APIM route or rewrite policy mismatch
- Model call fails from specialist:
  - model access contract/allow-list does not include required model
- Compatibility flow fails:
  - disclaimer/trust-level metadata blocks elevated-risk path