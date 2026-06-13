import os
import json
import asyncio
import random
from agent_framework import Agent, tool
from agent_framework.openai import OpenAIChatClient
from agent_framework_foundry_hosting import ResponsesHostServer

@tool(approval_mode="never_require")
def generate_confirmation_number() -> str:
    """Generate a realistic workshop confirmation number."""
    return f"SR-{random.randint(100000, 999999)}"

SYSTEM_PROMPT = """You are the Syensqo Sample Request Agent (workshop simulation).
You process product sample requests for authenticated external customers.
Use the upstream product-validation result from Product Intelligence as your source of truth.

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
- Require a validated product_id/product_name in the incoming context
- This is a workshop simulation; call `generate_confirmation_number` when accepted
- If persona is not external_customer -> set auth_status=not_authenticated and request_accepted=false
- If validated product information is missing -> set request_accepted=false and explain in missing_info
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
                  tools=[generate_confirmation_number], default_options={"store": False})
    return ResponsesHostServer(agent)

if __name__ == "__main__":
    asyncio.run(setup()).run()