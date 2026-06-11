import os, asyncio, json, uuid, requests
from typing import Annotated
from pydantic import Field
from agent_framework import Agent, tool
from agent_framework.openai import OpenAIChatClient
from agent_framework_foundry_hosting import ResponsesHostServer
from azure.identity import DefaultAzureCredential

_DISCOVERY_MODE = os.environ.get("PF_DISCOVERY_MODE", "api_center_live")
_API_CENTER_MCP_URL = os.environ.get("PF_API_CENTER_MCP_URL", "").strip().rstrip("/")
_API_CENTER_APIS_URL = os.environ["PF_API_CENTER_APIS_URL"]
_FOUNDRY_PROJECT_ENDPOINT = os.environ["FOUNDRY_PROJECT_ENDPOINT"].rstrip("/")
_FOUNDRY_AGENT_API_VERSION = os.environ.get("PF_FOUNDRY_AGENT_API_VERSION", "2025-05-15-preview")

_TOKEN_CRED = DefaultAzureCredential()


def _arm_token() -> str:
    token = _TOKEN_CRED.get_token("https://management.azure.com/.default")
    return token.token


def _foundry_token() -> str:
    token = _TOKEN_CRED.get_token("https://ai.azure.com/.default")
    return token.token


def _extract_output_text(payload: object) -> str:
    if isinstance(payload, dict):
        if isinstance(payload.get("output_text"), str):
            return payload["output_text"]
        output = payload.get("output")
        if isinstance(output, list):
            chunks = []
            for item in output:
                if not isinstance(item, dict):
                    continue
                for c in item.get("content", []):
                    if isinstance(c, dict) and c.get("type") in ("output_text", "text") and c.get("text"):
                        chunks.append(c["text"])
            if chunks:
                return "\n".join(chunks)
        return json.dumps(payload)
    if isinstance(payload, str):
        return payload
    return str(payload)


def _call_specialist(agent_name: str, message: str, persona: str) -> str:
    url = f"{_FOUNDRY_PROJECT_ENDPOINT}/agents/{agent_name}/endpoint/protocols/openai/responses?api-version={_FOUNDRY_AGENT_API_VERSION}"
    try:
        headers = {
            "Authorization": f"Bearer {_foundry_token()}",
            "Content-Type": "application/json",
        }
        payload = {
            "input": f"[GOVERNANCE CONTEXT]\npersona: {persona}\n\n{message}",
            "metadata": {"conversation_id": str(uuid.uuid4()), "target_agent": agent_name},
        }

        last_status = None
        last_body = ""
        last_error = None

        for attempt in range(3):
            try:
                # Try with SSL verification first
                resp = requests.post(url, headers=headers, json=payload, timeout=90)
                last_status = resp.status_code
                last_body = resp.text
                if resp.status_code < 500:
                    break
            except requests.exceptions.SSLError as ssl_err:
                # SSL cert verification failed - log but try to proceed
                last_error = str(ssl_err)
                if attempt < 2:
                    # Retry: on second attempt, disable SSL verification as fallback
                    try:
                        resp = requests.post(url, headers=headers, json=payload, timeout=90, verify=False)
                        last_status = resp.status_code
                        last_body = resp.text
                        if resp.status_code < 500:
                            break
                    except Exception as retry_err:
                        last_error = str(retry_err)
                        continue
            except Exception as e:
                last_error = str(e)
                last_status = None
                continue

        if last_status is None or last_status >= 400:
            error_msg = f"Direct Foundry call failed: HTTP {last_status}"
            if last_error and "SSL" in last_error:
                error_msg += " (SSL cert verification issue - may be intermittent)"
            return json.dumps({
                "error": error_msg,
                "agent": agent_name,
                "body": (last_body or "")[:1200],
                "ssl_error": "SSL_CERT_VERIFY_FAILED" if last_error and "SSL" in last_error else None,
            })
        try:
            return _extract_output_text(resp.json())
        except Exception:
            return resp.text
    except Exception as e:
        return json.dumps({"error": str(e), "agent": agent_name})


def _parse_governance_profile(api_item: dict) -> dict:
    props = api_item.get("properties") or {}
    custom = props.get("customProperties") or {}
    profile_raw = custom.get("governanceProfile")
    profile = {}
    if isinstance(profile_raw, str) and profile_raw.strip():
        try:
            profile = json.loads(profile_raw)
        except Exception:
            profile = {}

    # Fill from flattened fields as fallback.
    if "supported_intents" not in profile:
        profile["supported_intents"] = [x for x in (custom.get("supportedIntents", "") or "").split(",") if x]
    if "allowed_personas" not in profile:
        profile["allowed_personas"] = [x for x in (custom.get("allowedPersonas", "") or "").split(",") if x]
    if "risk_tiers_supported" not in profile:
        profile["risk_tiers_supported"] = [x for x in (custom.get("riskTiersSupported", "") or "").split(",") if x]

    profile.setdefault("agent_name", custom.get("agentName", props.get("title", api_item.get("name", ""))))
    profile.setdefault("priority", int(custom.get("priority", "999")))
    profile.setdefault("trust_level", custom.get("trustLevel", "unknown"))
    profile.setdefault("verification_status", custom.get("verificationStatus", "unknown"))
    profile.setdefault("orchestration_stage", custom.get("orchestrationStage", "unknown"))
    profile.setdefault("requires_disclaimer", (custom.get("requiresDisclaimer", "false") == "true"))
    profile.setdefault("auth_required", (custom.get("authRequired", "false") == "true"))
    profile.setdefault("supports_simulation", (custom.get("supportsSimulation", "false") == "true"))
    return profile


def _discover_from_api_center_rest() -> list[dict]:
    headers = {
        "Authorization": f"Bearer {_arm_token()}",
        "Content-Type": "application/json",
    }
    resp = requests.get(_API_CENTER_APIS_URL, headers=headers, timeout=45)
    resp.raise_for_status()
    body = resp.json()
    items = body.get("value", []) if isinstance(body, dict) else []
    profiles = []
    for item in items:
        profile = _parse_governance_profile(item)
        agent_name = str(profile.get("agent_name", "")).strip()
        if agent_name.startswith("pf"):
            profiles.append(profile)
    return profiles


def _extract_mcp_assets(payload: object) -> list[dict]:
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)]
    if isinstance(payload, dict):
        for key in ("assets", "value", "items", "results", "data"):
            candidate = payload.get(key)
            if isinstance(candidate, list):
                return [x for x in candidate if isinstance(x, dict)]
        result = payload.get("result")
        if isinstance(result, dict):
            for key in ("assets", "value", "items", "results", "data"):
                candidate = result.get(key)
                if isinstance(candidate, list):
                    return [x for x in candidate if isinstance(x, dict)]
            content = result.get("content")
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict):
                        text = block.get("text")
                        if not isinstance(text, str) or not text.strip():
                            continue
                        try:
                            parsed = json.loads(text)
                        except Exception:
                            continue
                        extracted = _extract_mcp_assets(parsed)
                        if extracted:
                            return extracted
    return []


def _mcp_search_pf_assets() -> list[dict]:
    # API Center data-plane MCP search endpoint: find all assets that start with pf.
    url = f"{_API_CENTER_MCP_URL}/search"
    payloads = [
        {"query": "pf*"},
        {"search": "pf*"},
        {"namePrefix": "pf"},
    ]

    for body in payloads:
        try:
            resp = requests.post(url, json=body, timeout=25)
            if resp.status_code >= 400:
                continue
            assets = _extract_mcp_assets(resp.json())
            if assets:
                filtered = []
                for asset in assets:
                    name = str(
                        asset.get("name")
                        or asset.get("title")
                        or ((asset.get("properties") or {}).get("title") if isinstance(asset.get("properties"), dict) else "")
                    ).strip().lower()
                    if name.startswith("pf"):
                        filtered.append(asset)
                if filtered:
                    return filtered
        except Exception:
            continue
    return []


def _mcp_fetch_asset(asset_stub: dict) -> dict | None:
    asset_id = str(asset_stub.get("id") or asset_stub.get("name") or "").strip()
    if not asset_id:
        return None

    # API Center data-plane MCP fetch endpoint: hydrate each matched asset.
    fetch_url = f"{_API_CENTER_MCP_URL}/assets/{asset_id}"
    try:
        resp = requests.get(fetch_url, timeout=25)
        if resp.status_code < 400:
            payload = resp.json()
            if isinstance(payload, dict):
                return payload
    except Exception:
        pass

    # Fallback attempt: POST fetch contract.
    try:
        resp = requests.post(f"{_API_CENTER_MCP_URL}/fetch", json={"id": asset_id}, timeout=25)
        if resp.status_code < 400:
            payload = resp.json()
            if isinstance(payload, dict):
                return payload
    except Exception:
        pass

    return None


def _profile_from_mcp_asset(asset: dict) -> dict:
    props = asset.get("properties") if isinstance(asset.get("properties"), dict) else {}
    custom = props.get("customProperties") if isinstance(props.get("customProperties"), dict) else {}

    # Normalize to existing parser shape.
    wrapped = {"name": asset.get("name"), "properties": {"title": props.get("title") or asset.get("title"), "customProperties": custom}}
    profile = _parse_governance_profile(wrapped)

    # Last-resort direct mapping if custom properties are already flattened.
    if not profile.get("agent_name"):
        profile["agent_name"] = asset.get("name") or asset.get("title") or ""
    return profile


def _discover_from_api_center_mcp(intent: str, persona: str, risk_tier: str) -> list[dict]:
    # Use MCP endpoint first: search pf* assets, then fetch each matched asset.
    if not _API_CENTER_MCP_URL:
        return _discover_from_api_center_rest()

    stubs = _mcp_search_pf_assets()
    if not stubs:
        return _discover_from_api_center_rest()

    hydrated = []
    for stub in stubs:
        full = _mcp_fetch_asset(stub)
        hydrated.append(full if isinstance(full, dict) else stub)

    profiles = []
    for asset in hydrated:
        if not isinstance(asset, dict):
            continue
        profile = _profile_from_mcp_asset(asset)
        agent_name = str(profile.get("agent_name", "")).strip()
        if agent_name.startswith("pf"):
            profiles.append(profile)

    return profiles or _discover_from_api_center_rest()


def _deterministic_filter(candidates: list[dict], intent: str, persona: str, risk_tier: str, disclaimer_accepted: bool) -> list[dict]:
    allowed = []
    for a in candidates:
        supported_intents = a.get("supported_intents", []) or []
        allowed_personas = a.get("allowed_personas", []) or []
        supported_risk = a.get("risk_tiers_supported", []) or []

        if intent not in supported_intents:
            continue
        if persona not in allowed_personas:
            continue
        if risk_tier not in supported_risk:
            continue
        if a.get("auth_required", False) and persona != "external_customer":
            continue
        if a.get("requires_disclaimer", False) and (risk_tier == "elevated") and (not disclaimer_accepted):
            continue

        trust = str(a.get("trust_level", "unknown")).lower()
        verification = str(a.get("verification_status", "unknown")).lower()
        if risk_tier == "elevated" and not (trust in ("high", "verified") and verification in ("verified", "high")):
            continue

        allowed.append(a)

    allowed.sort(key=lambda x: int(x.get("priority", 999)))
    return allowed


@tool(approval_mode="never_require")
def discover_agents_via_api_center(
    intent: Annotated[str, Field(description="Detected intent")],
    persona: Annotated[str, Field(description="Request persona")],
    risk_tier: Annotated[str, Field(description="low|elevated")],
    disclaimer_accepted: Annotated[bool, Field(description="Whether risk disclaimer was accepted")] = True,
) -> str:
    """ALWAYS call this first. Search/fetch agents from API Center MCP and apply deterministic governance filters."""
    try:
        discovered = _discover_from_api_center_mcp(intent=intent, persona=persona, risk_tier=risk_tier)
        allowed = _deterministic_filter(
            candidates=discovered,
            intent=intent,
            persona=persona,
            risk_tier=risk_tier,
            disclaimer_accepted=disclaimer_accepted,
        )
        return json.dumps({
            "discovery_mode": _DISCOVERY_MODE,
            "discovered_count": len(discovered),
            "allowed_count": len(allowed),
            "allowed_agents": [a.get("agent_name") for a in allowed],
            "profiles": allowed,
        })
    except Exception as e:
        return json.dumps({"error": str(e), "allowed_agents": []})


@tool(approval_mode="never_require")
def call_specialist_agent(
    agent_name: Annotated[str, Field(description="Target specialist agent name")],
    message: Annotated[str, Field(description="Message sent to specialist")],
    persona: Annotated[str, Field(description="Request persona")],
) -> str:
    """Call a selected specialist directly via Foundry agent endpoint."""
    return _call_specialist(agent_name=agent_name, message=message, persona=persona)


ORCHESTRATOR_SYSTEM = """You are the Syensqo Product Finder Orchestrator.
You dynamically route user queries to specialist agents discovered from API Center.

You receive messages in this format:
[GOVERNANCE CONTEXT]
persona: external_customer|internal_scientist
disclaimer_accepted: true|false

USER QUERY: <the user's question>

Mandatory routing process:
1. ALWAYS contextualize the request first (intent, entities, risk_tier).
2. ALWAYS call discover_agents_via_api_center immediately after contextualization.
3. Use only agents returned in allowed_agents. Never call agents outside this list.
4. Apply intent-based routing:
   - recommendation: choose product intelligence then aligner
   - compatibility: if disclaimer not accepted, return DISCLAIMER_GATE; else compatibility flow + aligner
   - sample_request: only for external_customer persona
   - out_of_domain: politely refuse
5. Call selected specialists using call_specialist_agent.

Important governance rule:
- Governance filtering is deterministic and done by discover_agents_via_api_center.
- Do not bypass this with prompt-only reasoning.

Return final JSON:
{
  "final_answer": "well-formatted response for the user",
  "agents_used": ["list of specialist agent names called"],
  "routing_decision": {"intent": "...", "risk_tier": "...", "persona": "...", "disclaimer_accepted": false},
  "confidence": 0.0,
  "governance_notices": ["any disclaimers or policy notices"],
  "disclaimer_required": false
}
"""


async def setup():
    client = OpenAIChatClient(
        model=os.environ["PF_MODEL_DEPLOYMENT"],
        base_url=f"{os.environ['PF_MODEL_AZURE_ENDPOINT'].rstrip('/')}/models",
        api_key=os.environ["PF_MODEL_SUBSCRIPTION_KEY"],
        default_headers={"api-key": os.environ["PF_MODEL_SUBSCRIPTION_KEY"]},
    )
    agent = Agent(
        client=client,
        name="pf-orchestrator",
        instructions=ORCHESTRATOR_SYSTEM,
        tools=[discover_agents_via_api_center, call_specialist_agent],
        default_options={"store": False},
    )
    return ResponsesHostServer(agent)


if __name__ == "__main__":
    asyncio.run(setup()).run()