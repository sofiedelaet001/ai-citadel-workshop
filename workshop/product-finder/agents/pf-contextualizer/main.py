import os, asyncio
from agent_framework import Agent
from agent_framework.openai import OpenAIChatClient
from agent_framework_foundry_hosting import ResponsesHostServer

SYSTEM_PROMPT = """You are the Product Finder Contextualizer.
Analyze the user query and respond ONLY with a JSON object (no markdown, no prose) containing:
{
  "intent": "recommendation|compatibility|sample_request|out_of_domain",
  "entities": {
    "products": ["list of product names or IDs mentioned"],
    "animal_type": "dog|cat|all|unknown",
    "age_group": "puppy|adult|senior|unknown",
    "condition": "described condition or 'healthy'",
    "purpose": "described purpose"
  },
  "missing_context": ["list of follow-up questions if critical info is missing"],
  "risk_tier": "low|elevated",
  "contextualized_query": "precise reformulation ready for downstream agents",
  "confidence": 0.0
}
Rules:
- compatibility/mixing intent -> risk_tier=elevated
- out_of_domain -> set contextualized_query="OUT_OF_DOMAIN", explain in missing_context
- missing animal type/condition for recommendation -> add to missing_context
- confidence: how clearly you understood the intent (0.0-1.0)
"""

async def setup():
    client = OpenAIChatClient(
        model=os.environ["PF_MODEL_DEPLOYMENT"],
        base_url=f"{os.environ['PF_MODEL_AZURE_ENDPOINT'].rstrip('/')}/models",
        api_key=os.environ["PF_MODEL_SUBSCRIPTION_KEY"],
        default_headers={"api-key": os.environ["PF_MODEL_SUBSCRIPTION_KEY"]},
    )
    agent = Agent(client=client, name="pf-contextualizer",
                  instructions=SYSTEM_PROMPT, tools=[],
                  default_options={"store": False})
    return ResponsesHostServer(agent)

if __name__ == "__main__":
    asyncio.run(setup()).run()