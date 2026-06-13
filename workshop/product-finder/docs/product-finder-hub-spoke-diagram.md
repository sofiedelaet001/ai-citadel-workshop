# Product Finder Hub-Spoke Diagram

This diagram shows the Product Finder request path and governance boundaries.

```mermaid
---
config:
  layout: fixed
---
flowchart TB
 subgraph HUB["Citadel Hub Boundary"]
        APIM["APIM Gateway<br>Unified AI Gateway"]
        HUBAPIC["API Center (Hub)<br>Control plane registry"]
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
    APIM --> ORCH
    PROD --> SEARCH & APIM
    COMP --> SEARCH
    CTXT --> APIM
    BLOB -- Indexing source --> SEARCH
    HUBAPIC -- API CENTER MCP SERVER --> ORCH
    COMP -- LLM call & Response Orchestrator --> APIM
    ALIGN --> APIM
    SAMPLE --> SEARCH & APIM
    ORCH -- LLM call & Specaialized Agents call --> APIM
```

## Reading Guide

- Hub boundary: APIM enforces policy and acts as the mandatory gateway for traffic.
- Spoke boundary: orchestrator and specialists execute the Product Finder use case logic.
- API Center appears in both boundaries to show governance publication and consumption points.
- Data flow: Blob stores source CSV data; Azure AI Search serves runtime retrieval for specialists.
- Runtime pattern: orchestrator routes to specialists and returns a bundled answer through APIM.
