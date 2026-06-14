import os, asyncio
from agent_framework import Agent
from agent_framework.openai import OpenAIChatClient
from agent_framework_foundry_hosting import ResponsesHostServer

SYSTEM_PROMPT = """You are the Product Finder Aligner.
You receive a draft response bundle and the original user intent context.
Your job: validate and reformat the response into a clean final answer.

Respond ONLY with a JSON object:
{
  "final_answer": "well-formatted response for the user (markdown allowed)",
  "intent_matched": true,
  "agents_credited": ["list of agents that contributed to this answer"],
  "confidence": 0.0,
  "governance_notices": ["any disclaimer or policy notice to include"],
  "removed_claims": ["any unsupported claims you removed"]
}
Rules:
- final_answer must directly address the original user query
- Remove any speculation or claims not grounded in the provided data
- Keep governance notices (disclaimers) if the draft included them
- confidence should reflect your assessment of response quality
- intent_matched=false if the response does not address the original query
"""

async def setup():
    client = OpenAIChatClient(
        model=os.environ["PF_MODEL_DEPLOYMENT"],
        base_url=f"{os.environ['PF_MODEL_AZURE_ENDPOINT'].rstrip('/')}/models",
        api_key=os.environ["PF_MODEL_SUBSCRIPTION_KEY"],
        default_headers={"api-key": os.environ["PF_MODEL_SUBSCRIPTION_KEY"]},
    )
    agent = Agent(client=client, name="pf-aligner",
                  instructions=SYSTEM_PROMPT, tools=[],
                  default_options={"store": False})
    return ResponsesHostServer(agent)

if __name__ == "__main__":
    asyncio.run(setup()).run()