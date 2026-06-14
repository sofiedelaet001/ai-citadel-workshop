# 🚀 Product Finder Workshop — Client Deployment Guide

This guide helps you run the **Product Finder** workshop use case on your own **Citadel-deployed** Azure environment.

---

## ✅ Prerequisites

Before you start, ensure your Citadel deployment and client environment are set up correctly.

### 1. Citadel Hub Deployed

Your organization must have already deployed the **Citadel Governance Hub** following the [official guidance](https://github.com/mohamedsaif/ai-hub-gateway-solution-accelerator/tree/workshop).

**Verify:** 
- Hub resource group exists with API Management instance
- Hub APIM has at least one API product and subscription key
- Hub is in the same Azure subscription as your spoke

### 2. Citadel Spoke Deployed

A spoke environment where the Product Finder will run.

**Verify:**
- Spoke resource group exists
- Foundry (AI Foundry) account created in the spoke
- Foundry project exists
- Role assignments (RBAC) allow your user access to both hub and spoke resources

### 3. Client Environment Setup

On your local machine or dev VM:

- **Azure CLI** installed (`az --version` to check)
- **Azure Developer CLI (azd)** installed (`azd version` to check)
- **Python 3.10+** installed (`python --version` to check)
- **Git** installed
- **Jupyter** support (or use VS Code Notebooks)
- **Permissions:** Azure subscription `Owner` role (or equivalent in spoke resource group)
- **Network access:** Can reach hub APIM and spoke Foundry endpoints

**Quick install check:**
```bash
az --version && azd version && python --version
```

### 4. Azure Credentials

You must be authenticated to Azure CLI and azd.

```bash
az login
az account set --subscription <YOUR_SUBSCRIPTION_ID>
```

---

## 🔧 Setup Steps

### Step 1: Local Workshop Bootstrap 

Run these steps in order on a clean machine/repo clone:

1. Clone repo

2. Go to correct workshop branch
```bash
git checkout workshop
```

3. Copy over `.azure` folder from existing Citadel-enabled clone

4. Authenticate azd for the right tenant
```bash
azd auth login --tenant-id <TENANT_ID>
```

5. Refresh environment values
```bash
azd env refresh
```

6. Open Command Palette
- Press `Ctrl + Shift + P`

7. Python: Create Environment

8. Select `Venv`

9. Select Python interpreter

10. Select `workshop/requirements.txt` only

### Step 3: Run Pre-Flight Validation

Before running notebooks, validate your environment is correctly configured.

```bash
cd workshop/product-finder
python scripts/validate-client-environment.py
```

**Expected output:**
```
✅ Azure CLI authenticated
✅ Hub resource group exists
✅ APIM instance found
✅ Spoke Foundry account found
✅ All prerequisites met. Ready to proceed!
```

## Step 4: Execute Notebooks sequentially in VS Code

The workshop consists of 10 numbered notebooks in `workshop/product-finder/notebooks/`
Each notebook builds on the previous one. **Run them in order:**

| # | Notebook | Purpose | Est. Time |
|---|----------|---------|-----------|
| 1 | Foundation Prereq | Set up model access contract, APIM subscriptions, runtime config | 10 min |
| 2 | Data Readiness | Load product data, create search index | 5 min |
| 3 | Deploy Specialists | Build and deploy agent images, register in Foundry | 15 min |
| 4 | APIM Specialists Exposure | Create APIM product/subscription for agent access | 10 min |
| 5 | API Center Sync | Register agents in API Center for discovery | 10 min |
| 6 | Orchestrator Smoke | Deploy orchestrator, run smoke tests | 15 min |
| 7–9 | Scenario Tests | Run end-to-end scenarios (customer, scientist, etc.) | 20 min |
| 10 | Observability | Validate telemetry, view logs | 10 min |

**In VS Code:**
- Install the Jupyter extension if not already installed
- Open `notebooks/1. product-finder-foundation-prereq.ipynb`
- Follow the cell comments and Markdown instructions

---

## Read docs for further improvements

If interested, you can wrap up by reading following material in the /docs folder:

- optimization-options.md : to understand how you can improve this workshop and go from POC --> PROD
- manual-expansion-playbook.md : to understand how much manual work expanding this architecture with a new use case would require