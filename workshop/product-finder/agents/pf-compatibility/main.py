import os
import json
import asyncio
import requests
from agent_framework import Agent, tool
from agent_framework.openai import OpenAIChatClient
from agent_framework_foundry_hosting import ResponsesHostServer

SEARCH_ENDPOINT = os.environ["PF_RAG_SEARCH_ENDPOINT"].rstrip("/")
SEARCH_INDEX = os.environ["PF_RAG_INDEX"]
SEARCH_API_KEY = os.environ["PF_RAG_SEARCH_API_KEY"]
SEARCH_API_VERSION = "2024-07-01"

def _trim_text(value: str, max_len: int = 400) -> str:
    value = (value or "").strip()
    if len(value) <= max_len:
        return value
    return value[:max_len] + "..."

def _search_context(entity_type: str, query: str, top_k: int = 4):
    url = f"{SEARCH_ENDPOINT}/indexes/{SEARCH_INDEX}/docs/search?api-version={SEARCH_API_VERSION}"
    headers = {"Content-Type": "application/json", "api-key": SEARCH_API_KEY}
    select_fields = "id,title,text,product_a,product_b,compatibility,risk_tier,confidence"
    if entity_type == "product":
        select_fields = "id,title,text,product_id"

    payload = {
        "search": query or "*",
        "filter": f"entity_type eq '{entity_type}'",
        "select": select_fields,
        "top": top_k,
    }
    r = requests.post(url, headers=headers, json=payload, timeout=45)
    r.raise_for_status()
    return r.json().get("value", [])

@tool(approval_mode="never_require")
def search_compatibility(query: str, top_k: int = 4) -> str:
    """Query live compatibility rows from Azure AI Search and return JSON rows."""
    try:
        rows = _search_context(entity_type="compatibility", query=query, top_k=top_k)
        slim = [
            {
                "product_a": row.get("product_a"),
                "product_b": row.get("product_b"),
                "compatibility": row.get("compatibility"),
                "risk_tier": row.get("risk_tier"),
                "confidence": row.get("confidence"),
                "title": row.get("title"),
                "text": _trim_text(row.get("text", "")),
            }
            for row in rows
        ]
        return json.dumps({"count": len(slim), "rows": slim}, ensure_ascii=False)
    except Exception as exc:
        return json.dumps({"error": f"compatibility_search_failed: {exc}", "rows": []}, ensure_ascii=False)

@tool(approval_mode="never_require")
def search_products(query: str, top_k: int = 6) -> str:
    """Query live product rows from Azure AI Search and return JSON rows."""
    try:
        rows = _search_context(entity_type="product", query=query, top_k=top_k)
        slim = [
            {
                "product_id": row.get("product_id"),
                "title": row.get("title"),
                "text": _trim_text(row.get("text", "")),
            }
            for row in rows
        ]
        return json.dumps({"count": len(slim), "rows": slim}, ensure_ascii=False)
    except Exception as exc:
        return json.dumps({"error": f"product_search_failed: {exc}", "rows": []}, ensure_ascii=False)

SYSTEM_PROMPT = """You are the Syensqo Product Compatibility Agent.
Use Azure AI Search as your source of truth by calling tools for every query.
Call `search_compatibility` first.
Call `search_products` only when extra product details are needed.
Keep tool usage minimal: no more than 2 tool calls per user request.

Given two product names or IDs, respond ONLY with a JSON object:
{
  "product_a": "name",
  "product_b": "name",
  "verdict": "compatible|incompatible|caution",
  "confidence": 0.0,
  "safety_rationale": "detailed explanation citing pH, active ingredients, known interactions",
  "recommendation": "practical advice for the user",
  "warning": "any safety warning or empty string",
  "requires_vet_guidance": false
}
Rules:
- ALWAYS call `search_compatibility` first; use `search_products` for supporting details
- If no explicit compatibility row exists, estimate from tool output and lower confidence
- confidence < 0.90 for risky queries -> set requires_vet_guidance=true
- verdict=incompatible or caution -> include explicit warning
- Never minimise safety concerns
"""

async def setup():
    client = OpenAIChatClient(
        model=os.environ["PF_MODEL_DEPLOYMENT"],
        base_url=f"{os.environ['PF_MODEL_AZURE_ENDPOINT'].rstrip('/')}/models",
        api_key=os.environ["PF_MODEL_SUBSCRIPTION_KEY"],
        default_headers={"api-key": os.environ["PF_MODEL_SUBSCRIPTION_KEY"]},
    )
    agent = Agent(client=client, name="pf-compatibility",
                  instructions=SYSTEM_PROMPT,
                  tools=[search_compatibility, search_products], default_options={"store": False})
    return ResponsesHostServer(agent)

if __name__ == "__main__":
    asyncio.run(setup()).run()