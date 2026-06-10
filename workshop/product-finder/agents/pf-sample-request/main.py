import os
import json
import asyncio
import random
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
    """Query live Azure AI Search product rows and return JSON rows."""
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

@tool(approval_mode="never_require")
def generate_confirmation_number() -> str:
    """Generate a realistic workshop confirmation number."""
    return f"SR-{random.randint(100000, 999999)}"

SYSTEM_PROMPT = """You are the Syensqo Sample Request Agent (workshop simulation).
You process product sample requests for authenticated external customers.
Use Azure AI Search as your source of truth by calling `search_products` for product validation.

Respond ONLY with a JSON object:
{
  "request_accepted": true,
  "product_id": "SPxxx",
  "product_name": "name",
  "confirmation_number": "SR-XXXXXX",
  "estimated_delivery": "5-7 business days",
  "message": "confirmation message for the customer",
  "missing_info": ["list of missing required fields if request is incomplete"],
  "auth_status": "authenticated|not_authenticated"
}
Rules:
- Always call `search_products` before accepting/rejecting a product request
- This is a workshop simulation; call `generate_confirmation_number` when accepted
- If persona is not external_customer -> set auth_status=not_authenticated and request_accepted=false
- If product does not exist in tool output -> set request_accepted=false and explain
- Always confirm the product name and ID in the response
"""

async def setup():
    client = OpenAIChatClient(
        model=os.environ["PF_MODEL_DEPLOYMENT"],
        base_url=f"{os.environ['PF_MODEL_AZURE_ENDPOINT'].rstrip('/')}/models",
        api_key=os.environ["PF_MODEL_SUBSCRIPTION_KEY"],
        default_headers={"api-key": os.environ["PF_MODEL_SUBSCRIPTION_KEY"]},
    )
    agent = Agent(client=client, name="pf-sample-request",
                  instructions=SYSTEM_PROMPT,
                  tools=[search_products, generate_confirmation_number], default_options={"store": False})
    return ResponsesHostServer(agent)

if __name__ == "__main__":
    asyncio.run(setup()).run()