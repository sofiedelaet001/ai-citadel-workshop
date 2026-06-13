# Product Finder Hub-Spoke Diagram

This diagram shows the Product Finder request path and governance boundaries.

```mermaid
---
config:
  layout: fixed
---
flowchart TB
 subgraph MODELS["LLMs"]
        GPT4["gpt-4.1"]
        DS["DeepSeek-R1"]
        EM["text-embedding-3-large"]
        MIS["Mistral-Large-3"]
        GPTM["gpt-5.4-mini"]
        PHI["Phi-4"]
        GPT5["gpt-5.2"]
  end
 subgraph HUB["Citadel Hub Boundary"]
        APIM["APIM Gateway<br>Unified AI Gateway"]
        HUBAPIC["API Center (Hub)<br>Control plane registry"]
        MODELS
  end
 subgraph SPEC["Specialized Agents"]
        CTXT["pf-contextualizer"]
        PROD["pf-product-intelligence"]
        COMP["pf-compatibility"]
        ALIGN["pf-aligner"]
        SAMPLE["pf-sample-request"]
  end
 subgraph SPOKE["Product Finder Spoke Boundary"]
        ORCH["pf-orchestrator<br>Hosted Orchestrator Agent"]
        SPEC
        SEARCH["Azure AI Search<br>RAG index"]
        BLOB["Blob Storage<br>products.csv + compatibility_matrix.csv"]
  end
    User["User"] -- "Ocp-Apim-Subscription-Key<br>+ persona context" --> ORCH
    SEARCH --> PROD & COMP
    PROD <--> APIM
    CTXT <--> APIM
    BLOB -- Indexing source --> SEARCH
    COMP <-- LLM call & Response Orchestrator --> APIM
    ALIGN <--> APIM
    SAMPLE <--> APIM
    ORCH <-- LLM call & Specaialized Agents call --> APIM
    HUBAPIC -- API CENTER MCP SERVER --> ORCH
    APIM <--> MODELS

    style GPT4 fill:#FFE0B2
    style DS fill:#FFE0B2
    style EM fill:#FFE0B2
    style MIS fill:#FFE0B2
    style GPTM fill:#FFE0B2
    style PHI fill:#FFE0B2
    style GPT5 fill:#FFE0B2
    style APIM fill:#E1BEE7
    style HUBAPIC fill:#FFCDD2
    style CTXT fill:#BBDEFB
    style PROD fill:#BBDEFB
    style COMP stroke:#000000,fill:#BBDEFB
    style ALIGN fill:#BBDEFB
    style SAMPLE fill:#BBDEFB
    style ORCH fill:#C8E6C9
    style SEARCH fill:#FFF9C4
    style BLOB fill:#FFF9C4
```

## Reading Guide

- Hub boundary: APIM enforces policy and acts as the mandatory gateway for traffic.
- Spoke boundary: orchestrator and specialists execute the Product Finder use case logic.
- API Center appears in both boundaries to show governance publication and consumption points.
- Data flow: Blob stores source CSV data; Azure AI Search serves runtime retrieval for specialists.
- Runtime pattern: orchestrator routes to specialists and returns a bundled answer through APIM.
