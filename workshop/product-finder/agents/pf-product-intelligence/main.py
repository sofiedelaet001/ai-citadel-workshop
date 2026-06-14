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

def _search_products(query: str, top_k: int = 8):
    url = f"{SEARCH_ENDPOINT}/indexes/{SEARCH_INDEX}/docs/search?api-version=2024-07-01"
    headers = {"Content-Type": "application/json", "api-key": SEARCH_API_KEY}
    payload = {
        "search": query or "*",
        "filter": "entity_type eq 'product'",
        "select": "id,title,text,product_id",
        "top": top_k,
    }
    r = requests.post(url, headers=headers, json=payload, timeout=45)
    r.raise_for_status()
    return r.json().get("value", [])

@tool(approval_mode="never_require")
def search_products(query: str, top_k: int = 8) -> str:
    """Query live Azure AI Search product documents and return JSON rows."""
    try:
        rows = _search_products(query=query, top_k=top_k)
        slim = [
            {
                "product_id": row.get("product_id"),
                "title": row.get("title"),
                "text": row.get("text"),
            }
            for row in rows
        ]
        return json.dumps({"count": len(slim), "rows": slim}, ensure_ascii=False)
    except Exception as exc:
        return json.dumps({"error": str(exc), "rows": []}, ensure_ascii=False)

SYSTEM_PROMPT = """You are the Product Finder Intelligence Agent.
Use Azure AI Search as your source of truth by calling the `search_products` tool for every user query.
Do not answer with product claims unless they are grounded in tool output.

Given a contextualized product query, respond ONLY with a JSON object:
{
  "top_products": [
    {
      "product_id": "SPxxx",
      "name": "product name",
      "match_score": 0.0,
      "why_selected": "explanation grounded in search context",
      "key_features": ["feature1", "feature2"],
      "caution": "any caution or empty string"
    }
  ],
  "recommendation_summary": "one paragraph recommendation for the user",
  "confidence": 0.0,
  "evidence_refs": ["relevant context snippets cited"]
}
Rules:
- Always call `search_products` first using the user's contextualized query
- Only recommend products that genuinely match the query
- Lower confidence if query is ambiguous
- Always cite evidence from the tool output
- Return top 1-3 products maximum
"""

async def setup():
    client = OpenAIChatClient(
        model=os.environ["PF_MODEL_DEPLOYMENT"],
        base_url=f"{os.environ['PF_MODEL_AZURE_ENDPOINT'].rstrip('/')}/models",
        api_key=os.environ["PF_MODEL_SUBSCRIPTION_KEY"],
        default_headers={"api-key": os.environ["PF_MODEL_SUBSCRIPTION_KEY"]},
    )
    agent = Agent(client=client, name="pf-product-intelligence",
                  instructions=SYSTEM_PROMPT,
                  tools=[search_products], default_options={"store": False})
    return ResponsesHostServer(agent)

if __name__ == "__main__":
    asyncio.run(setup()).run()