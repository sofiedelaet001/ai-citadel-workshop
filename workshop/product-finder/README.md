# Product Finder Workshop — Client Deployment Guide

## 📍 Where Does This Fit?

This directory contains a **complete worked example** that builds on top of the Citadel platform. 

- **Citadel** = the governance hub (APIM, policies, observability)
- **Product Finder** = a spoke workload showing how to build agentic applications on Citadel

```
┌─────────────────────────────────────────────────┐
│  Citadel Governance Hub (APIM, policies, etc)   │
│            ✅ Deployed in your org             |
└─────────────────────────────────────────────────┘
                         △
                         │ 
                         │
     ┌───────────────────┴────────────────────┐
     │  Product Finder Spoke (this workshop)  │
     │    - Specialist agents                 │
     │    - Orchestrator                      │
     │    - Data/Search integration           │
     └────────────────────────────────────────┘
```

**Your task:** Set up Product Finder on your existing Citadel deployment.

---

## 📂 Directory Structure

```
product-finder/
├── GETTING_STARTED.md                          ← Client onboarding guide
├── CLIENT_DEPLOYMENT_CHECKLIST.md              ← Values to customize
├── README.md                                   ← This file
│
├── scripts/
│   └── validate-client-environment.py          ← Pre-flight validation
│
├── notebooks/                                  ← 10 numbered Jupyter notebooks
│   ├── 1. product-finder-foundation-prereq.ipynb
│   ├── 2. product-finder-data-readiness.ipynb
│   ├── 3. product-finder-deploy-specialists.ipynb
│   ├── ... (4-10)
│   └── 10. product-finder-observability.ipynb
│
├── agents/                                     ← Specialist agent code
│   ├── pf-contextualizer/                      ← Query understanding
│   ├── pf-product-intelligence/                ← RAG + retrieval
│   ├── pf-compatibility/                       ← Analysis
│   ├── pf-aligner/                             ← Validation
│   ├── pf-sample-request/                      ← Persona-gated
│   └── pf-orchestrator/                        ← Main router
│
├── data/                                       ← Product CSV data
│   └── products.csv
│
├── access-contracts/                           ← APIM policies
│   ├── contracts/
│   └── ai-product-policy.xml                   ← Gateway policies
│
├── registry/                                   ← Agent metadata
│   ├── governance-profile.params.json
│   └── api-registry.json
│
└── docs/                                       ← Reference docs
    ├── manual-expansion-playbook.md            ← How to extend
    ├── optimization-options.md ← Possible optimizations
    └── product-finder-hub-spoke-diagram.md     ← Visual architecture
```

---

## 🔍 Key Architecture Pattern

An architecture diagram is present under the /docs folder

## ❓ Frequently Asked Questions

### Q: Do I need to modify the notebooks?

**A:** Minimally. The first notebook will prompt you to set azd environment variables. Once configured, notebooks should run unchanged.

### Q: What if I already deployed some of this?

**A:** Notebooks check for existing resources and skip creation if already present. Safe to re-run.

### Q: How do I know if something went wrong?

**A:** Each notebook cell includes error handling and informative messages. Also:
- Run `python scripts/validate-client-environment.py` anytime to check setup
- Check Azure Portal for resource creation status

### Q: Can I use a different model than gpt-5.4-mini?

**A:** Yes! Check Notebook 1 for the `PF_MODEL_DEPLOYMENT` variable. Change it to any model available in your APIM deployment (gpt-4, gpt-5.5, etc.).

### Q: How do I add my own specialist agent?

**A:** See [manual-expansion-playbook.md](./docs/manual-expansion-playbook.md) for step-by-step guidance.

### Q: Is this production-ready?

**A:** This is a **reference implementation** and **demonstration**. For production:
- Replace hardcoded persona with Entra ID identity
- Add comprehensive audit logging
- Implement rate limiting policies per user/tenant
- Performance test with realistic query volumes
- Review and customize APIM policies for your organization

---

## 📚 Documentation Map

| Document | Purpose |
|----------|---------|
| **GETTING_STARTED.md** | Client onboarding, prerequisites, setup steps |
| **manual-expansion-playbook.md** | How to extend: add new specialists, modify workflows |
| **optimization-options.md** | Model selection & performance tuning |
| **product-finder-hub-spoke-diagram.md** | Visual architecture reference |

---

## 🎯 Success Criteria

By the end of this workshop, you should be able to:

- [ ] Access your Citadel APIM hub through the governance layer
- [ ] Deploy 6 agents to Foundry with proper metadata
- [ ] Query the Product Finder orchestrator and see it route to appropriate specialists
- [ ] View telemetry and logs showing orchestrator decisions and specialist calls
- [ ] Extend the system with a new specialist agent (optional, see manual-expansion-playbook)

---

## 🎓 Related Learning

- **Citadel Governance Hub:** [github.com/Azure-Samples/ai-hub-gateway-solution-accelerator](https://github.com/Azure-Samples/ai-hub-gateway-solution-accelerator)
- **Azure APIM:** [learn.microsoft.com/azure/api-management](https://learn.microsoft.com/azure/api-management)
- **AI Agents Framework:** [learn.microsoft.com/agent-framework](https://learn.microsoft.com/en-us/agent-framework/overview/?pivots=programming-language-csharp)
- **Foundry:** [learn.microsoft.com/azure/ai-foundry/agents](https://learn.microsoft.com/azure/ai-foundry/agents)

---
**👉 Ready? Start with [GETTING_STARTED.md](./GETTING_STARTED.md)**
