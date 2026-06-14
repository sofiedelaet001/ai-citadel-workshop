import os, asyncio, json, uuid, requests, re
from collections import defaultdict
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
_SPECIALIST_CALL_MODE = os.environ.get("PF_SPECIALIST_CALL_MODE", "apim").strip().lower()
_APIM_SPECIALIST_ENDPOINT = (os.environ.get("PF_AGENT_ENDPOINT") or os.environ.get("APIM_GATEWAY_URL") or "").strip().rstrip("/")
_APIM_SUB_KEY = (os.environ.get("PF_AGENT_SUBSCRIPTION_KEY") or "").strip()

_TOKEN_CRED = DefaultAzureCredential()


def _arm_token() -> str:
    token = _TOKEN_CRED.get_token("https://management.azure.com/.default")
    return token.token


def _foundry_token() -> str:
    token = _TOKEN_CRED.get_token("https://ai.azure.com/.default")
    return token.token


def _coerce_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(x).strip() for x in value if str(x).strip()]
    if isinstance(value, str):
        return [x.strip() for x in value.split(",") if x.strip()]
    return []


def _coerce_bool(value: object, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        v = value.strip().lower()
        if v in ("true", "1", "yes", "y", "on"):
            return True
        if v in ("false", "0", "no", "n", "off"):
            return False
    if isinstance(value, (int, float)):
        return bool(value)
    return default


def _coerce_int(value: object, default: int) -> int:
    try:
        return int(str(value).strip())
    except Exception:
        return default


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


def _route_suffix(agent_name: str) -> str:
    return re.sub(r"[^a-z0-9-]", "-", (agent_name or "").strip().lower())


def _call_specialist(agent_name: str, message: str, persona: str) -> str:
    try:
        payload = {
            "input": f"[GOVERNANCE CONTEXT]\npersona: {persona}\n\n{message}",
            "metadata": {"conversation_id": str(uuid.uuid4()), "target_agent": agent_name},
        }

        if _SPECIALIST_CALL_MODE == "apim":
            if not _APIM_SPECIALIST_ENDPOINT or not _APIM_SUB_KEY:
                return json.dumps({
                    "error": "APIM specialist routing is enabled but PF_AGENT_ENDPOINT/PF_AGENT_SUBSCRIPTION_KEY are missing",
                    "agent": agent_name,
                })
            route = _route_suffix(agent_name)
            base = _APIM_SPECIALIST_ENDPOINT
            if base.lower().endswith("/agents"):
                url = f"{base}/{route}/invoke"
            else:
                url = f"{base}/agents/{route}/invoke"
            headers = {
                "Ocp-Apim-Subscription-Key": _APIM_SUB_KEY,
                "Content-Type": "application/json",
            }
        else:
            url = f"{_FOUNDRY_PROJECT_ENDPOINT}/agents/{agent_name}/endpoint/protocols/openai/responses?api-version={_FOUNDRY_AGENT_API_VERSION}"
            headers = {
                "Authorization": f"Bearer {_foundry_token()}",
                "Content-Type": "application/json",
            }

        last_status = None
        last_body = ""
        last_error = None

        for _ in range(3):
            try:
                resp = requests.post(url, headers=headers, json=payload, timeout=90)
                last_status = resp.status_code
                last_body = resp.text
                if resp.status_code < 500:
                    break
            except Exception as e:
                last_error = str(e)
                last_status = None
                continue

        if last_status is None or last_status >= 400:
            mode = "APIM" if _SPECIALIST_CALL_MODE == "apim" else "Direct Foundry"
            error_msg = f"{mode} specialist call failed: HTTP {last_status}"
            return json.dumps({
                "error": error_msg,
                "agent": agent_name,
                "body": (last_body or "")[:1200],
                "exception": last_error,
            })
        try:
            return _extract_output_text(resp.json())
        except Exception:
            return resp.text
    except Exception as e:
        return json.dumps({"error": str(e), "agent": agent_name})


def _parse_governance_profile(api_item: dict) -> dict:
    props = api_item.get("properties") if isinstance(api_item.get("properties"), dict) else {}
    custom = props.get("customProperties") if isinstance(props.get("customProperties"), dict) else {}

    profile_raw = custom.get("governanceProfile")
    profile = {}
    if isinstance(profile_raw, str) and profile_raw.strip():
        try:
            profile = json.loads(profile_raw)
        except Exception:
            profile = {}

    # Flattened metadata fallback (legacy + explicit fields).
    profile.setdefault("agent_name", custom.get("agentName") or props.get("title") or api_item.get("name") or "")
    profile.setdefault("description", custom.get("description") or custom.get("summary") or props.get("description") or "")
    profile.setdefault("capabilities", _coerce_list(profile.get("capabilities") or custom.get("capabilities") or custom.get("skills") or ""))
    profile.setdefault("supported_intents", _coerce_list(profile.get("supported_intents") or custom.get("supportedIntents") or "*"))
    profile.setdefault("allowed_personas", _coerce_list(profile.get("allowed_personas") or custom.get("allowedPersonas") or "*"))
    profile.setdefault("risk_tiers_supported", _coerce_list(profile.get("risk_tiers_supported") or custom.get("riskTiersSupported") or "low,elevated"))
    profile.setdefault("run_after", _coerce_list(profile.get("run_after") or custom.get("runAfter") or custom.get("dependsOn") or ""))
    profile.setdefault("orchestration_stage", str(profile.get("orchestration_stage") or custom.get("orchestrationStage") or "execution").strip().lower())
    profile.setdefault("execution_order", _coerce_int(profile.get("execution_order") or custom.get("executionOrder"), 500))
    profile.setdefault("priority", _coerce_int(profile.get("priority") or custom.get("priority"), 999))
    profile.setdefault("trust_level", str(profile.get("trust_level") or custom.get("trustLevel") or "unknown").strip().lower())
    profile.setdefault("verification_status", str(profile.get("verification_status") or custom.get("verificationStatus") or "unknown").strip().lower())
    profile.setdefault("requires_disclaimer", _coerce_bool(profile.get("requires_disclaimer") if "requires_disclaimer" in profile else custom.get("requiresDisclaimer"), False))
    profile.setdefault("auth_required", _coerce_bool(profile.get("auth_required") if "auth_required" in profile else custom.get("authRequired"), False))
    profile.setdefault("enabled", _coerce_bool(profile.get("enabled") if "enabled" in profile else custom.get("enabled"), True))

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
        agent_name = str(profile.get("agent_name", "")).strip().lower()
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
    # Always start discovery with MCP search for pf* assets.
    if not _API_CENTER_MCP_URL:
        return []

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

    fetch_url = f"{_API_CENTER_MCP_URL}/assets/{asset_id}"
    try:
        resp = requests.get(fetch_url, timeout=25)
        if resp.status_code < 400:
            payload = resp.json()
            if isinstance(payload, dict):
                return payload
    except Exception:
        pass

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

    wrapped = {
        "name": asset.get("name"),
        "properties": {
            "title": props.get("title") or asset.get("title"),
            "description": props.get("description") or asset.get("description"),
            "customProperties": custom,
        },
    }
    profile = _parse_governance_profile(wrapped)
    if not profile.get("agent_name"):
        profile["agent_name"] = asset.get("name") or asset.get("title") or ""
    return profile


def _discover_profiles() -> dict:
    stubs = _mcp_search_pf_assets()
    if stubs:
        hydrated = []
        for stub in stubs:
            full = _mcp_fetch_asset(stub)
            hydrated.append(full if isinstance(full, dict) else stub)

        profiles = []
        for asset in hydrated:
            if not isinstance(asset, dict):
                continue
            profile = _profile_from_mcp_asset(asset)
            agent_name = str(profile.get("agent_name", "")).strip().lower()
            if agent_name.startswith("pf"):
                profiles.append(profile)

        if profiles:
            return {
                "discovery_mode": "api_center_mcp_search",
                "discovered_count": len(profiles),
                "profiles": profiles,
            }

    profiles = _discover_from_api_center_rest()
    return {
        "discovery_mode": "api_center_rest_fallback",
        "discovered_count": len(profiles),
        "profiles": profiles,
    }


def _matches_rule(value: str, allowed: list[str]) -> bool:
    if not allowed:
        return True
    normalized = {x.strip().lower() for x in allowed if x.strip()}
    return "*" in normalized or "any" in normalized or value.strip().lower() in normalized


def _is_contextualizer(profile: dict) -> bool:
    stage = str(profile.get("orchestration_stage", "")).lower()
    caps = {x.lower() for x in _coerce_list(profile.get("capabilities", []))}
    name = str(profile.get("agent_name", "")).lower()
    return (
        "context" in stage
        or "contextualize" in stage
        or "intent" in caps
        or "contextualization" in caps
        or name.endswith("contextualizer")
    )


def _agent_allowed(profile: dict, intent: str, persona: str, risk_tier: str, disclaimer_accepted: bool) -> tuple[bool, str]:
    if not _coerce_bool(profile.get("enabled"), True):
        return False, "disabled"

    if not _matches_rule(intent, _coerce_list(profile.get("supported_intents", []))):
        return False, "intent_not_supported"
    if not _matches_rule(persona, _coerce_list(profile.get("allowed_personas", []))):
        return False, "persona_not_allowed"
    if not _matches_rule(risk_tier, _coerce_list(profile.get("risk_tiers_supported", []))):
        return False, "risk_tier_not_supported"

    if _coerce_bool(profile.get("requires_disclaimer"), False) and risk_tier == "elevated" and not disclaimer_accepted:
        return False, "disclaimer_required"

    # For elevated risk, trust/verification can constrain usage.
    if risk_tier == "elevated":
        trust = str(profile.get("trust_level", "unknown")).lower()
        verification = str(profile.get("verification_status", "unknown")).lower()
        allow_unverified = _coerce_bool(profile.get("allow_elevated_unverified"), False)
        if not allow_unverified and trust not in ("high", "verified") and verification not in ("verified", "high"):
            return False, "trust_or_verification_too_low"

    return True, "allowed"


def _stage_rank(profile: dict) -> int:
    stage = str(profile.get("orchestration_stage", "")).strip().lower()
    explicit = _coerce_int(profile.get("execution_order"), 500)
    stage_defaults = {
        "contextualization": 100,
        "context": 100,
        "discovery": 200,
        "retrieval": 300,
        "analysis": 400,
        "reasoning": 500,
        "validation": 700,
        "alignment": 800,
        "fulfillment": 900,
    }
    return min(explicit, stage_defaults.get(stage, explicit))


def _topological_sort(profiles: list[dict]) -> list[dict]:
    by_name = {str(p.get("agent_name", "")).strip(): p for p in profiles if str(p.get("agent_name", "")).strip()}
    indegree = {name: 0 for name in by_name}
    graph = defaultdict(list)

    for name, profile in by_name.items():
        for dep in _coerce_list(profile.get("run_after", [])):
            dep_name = dep.strip()
            if dep_name in by_name and dep_name != name:
                graph[dep_name].append(name)
                indegree[name] += 1

    ready = [n for n, deg in indegree.items() if deg == 0]
    ready.sort(key=lambda n: (_stage_rank(by_name[n]), _coerce_int(by_name[n].get("priority"), 999), n))

    ordered_names = []
    while ready:
        current = ready.pop(0)
        ordered_names.append(current)
        for nxt in graph[current]:
            indegree[nxt] -= 1
            if indegree[nxt] == 0:
                ready.append(nxt)
        ready.sort(key=lambda n: (_stage_rank(by_name[n]), _coerce_int(by_name[n].get("priority"), 999), n))

    if len(ordered_names) != len(by_name):
        # Cycle fallback: deterministic stage+priority sort.
        ordered_names = sorted(
            by_name.keys(),
            key=lambda n: (_stage_rank(by_name[n]), _coerce_int(by_name[n].get("priority"), 999), n),
        )

    return [by_name[n] for n in ordered_names]


@tool(approval_mode="never_require")
def discover_pf_agents() -> str:
    """Always start orchestration by searching API Center MCP for pf* assets and returning governance profiles."""
    try:
        result = _discover_profiles()
        return json.dumps(result)
    except Exception as e:
        return json.dumps({
            "error": str(e),
            "discovery_mode": _DISCOVERY_MODE,
            "discovered_count": 0,
            "profiles": [],
        })


@tool(approval_mode="never_require")
def plan_dynamic_route(
    profiles_json: Annotated[str, Field(description="JSON array of discovered profiles")],
    intent: Annotated[str, Field(description="Detected intent")],
    persona: Annotated[str, Field(description="Request persona")],
    risk_tier: Annotated[str, Field(description="low|elevated")],
    disclaimer_accepted: Annotated[bool, Field(description="Whether risk disclaimer was accepted")] = True,
) -> str:
    """Build a metadata-driven specialist execution plan with deterministic governance filtering and ordering."""
    try:
        parsed = json.loads(profiles_json)
        profiles = parsed if isinstance(parsed, list) else []

        allowed = []
        blocked = []
        for p in profiles:
            if not isinstance(p, dict):
                continue
            ok, reason = _agent_allowed(
                profile=p,
                intent=intent,
                persona=persona,
                risk_tier=risk_tier,
                disclaimer_accepted=disclaimer_accepted,
            )
            if ok:
                allowed.append(p)
            else:
                blocked.append({"agent_name": p.get("agent_name"), "reason": reason})

        ordered = _topological_sort(allowed)
        route = [str(x.get("agent_name")) for x in ordered if str(x.get("agent_name", "")).strip()]

        blocked_reasons = [str(b.get("reason", "")) for b in blocked if isinstance(b, dict)]
        has_blocked_disclaimer = any(r == "disclaimer_required" for r in blocked_reasons)
        intent_norm = str(intent or "").strip().lower()
        risk_norm = str(risk_tier or "").strip().lower()
        disclaimer_gate_triggered = (
            (not disclaimer_accepted)
            and has_blocked_disclaimer
            and (intent_norm == "compatibility" or risk_norm == "elevated")
        )

        if disclaimer_gate_triggered:
            # Hard-stop route when disclaimer is mandatory but not accepted yet.
            ordered = []
            route = []

        disclaimer_required = (
            disclaimer_gate_triggered
            or any(_coerce_bool(x.get("requires_disclaimer"), False) for x in ordered)
            or has_blocked_disclaimer
        )

        # Check if core specialist for this intent was blocked (not a wrapper agent).
        core_specialist_blocked = False
        blocked_names = {str(b.get("agent_name", "")).strip().lower() for b in blocked}
        allowed_names = {str(a.get("agent_name", "")).strip().lower() for a in allowed}
        wrappers = {"pf-contextualizer", "pf-aligner"}
        core_specialists = {name for name in (blocked_names | allowed_names) if name not in wrappers and name.startswith("pf")}

        # If all non-wrapper specialists for this intent are blocked, flag it.
        intent_specific_specialists = core_specialists
        if intent_specific_specialists and all(name in blocked_names for name in intent_specific_specialists):
            core_specialist_blocked = True

        return json.dumps({
            "intent": intent,
            "persona": persona,
            "risk_tier": risk_tier,
            "allowed_count": len(route),
            "route": route,
            "ordered_profiles": ordered,
            "blocked": blocked,
            "disclaimer_gate_triggered": disclaimer_gate_triggered,
            "disclaimer_required": disclaimer_required,
            "core_specialist_blocked": core_specialist_blocked,
        })
    except Exception as e:
        return json.dumps({
            "error": str(e),
            "route": [],
            "ordered_profiles": [],
            "blocked": [],
            "disclaimer_gate_triggered": False,
            "disclaimer_required": False,
            "core_specialist_blocked": False,
        })


@tool(approval_mode="never_require")
def call_specialist_agent(
    agent_name: Annotated[str, Field(description="Target specialist agent name")],
    message: Annotated[str, Field(description="Message sent to specialist")],
    persona: Annotated[str, Field(description="Request persona")],
) -> str:
    """Call a selected specialist via APIM dynamic route (or direct Foundry in fallback mode)."""
    return _call_specialist(agent_name=agent_name, message=message, persona=persona)


ORCHESTRATOR_SYSTEM = """You are the Product Finder Orchestrator.
Your routing must be metadata-driven and dynamic.

You receive messages in this format:
[GOVERNANCE CONTEXT]
persona: external_customer|internal_scientist
disclaimer_accepted: true|false

USER QUERY: <the user's question>

Mandatory process:

STEP 0 (MANDATORY): DISCOVER AGENTS FIRST
- Always call discover_pf_agents before any other operation.
- This tool must be the first tool call in each conversation.
- Discover all pf* specialists first, then make routing decisions from their metadata.
- Use discovered profile metadata to decide routing; do not assume static workflows.

STEP 1: IDENTIFY A CONTEXTUALIZER DYNAMICALLY
- From discovered profiles, choose the contextualizer agent using metadata:
  - Prefer orchestration_stage indicating contextualization/context.
  - If multiple candidates, prefer lower execution_order then lower priority.
- Call that contextualizer with the full incoming message.
- Parse JSON for intent, risk_tier, and missing_context.

STEP 1A: HANDLE MISSING CONTEXT
- If missing_context is non-empty: stop and ask those clarifying questions.
- Do not call downstream specialists.
- Return final JSON with agents_used containing only the contextualizer.
- If missing_context is empty: continue immediately to STEP 2 in the same turn.

STEP 2: BUILD ROUTE FROM METADATA
- Call plan_dynamic_route with discovered profiles + intent + persona + risk_tier + disclaimer_accepted.
- Route selection must be driven by metadata filters (supported_intents, allowed_personas, risk_tiers_supported, trust/verification, disclaimer, enabled, dependencies/order).
- Use route exactly as returned; do not invent ad-hoc steps.
- If disclaimer_gate_triggered is true, stop and ask the user to accept the disclaimer first.
- When disclaimer_gate_triggered is true, do NOT call any downstream specialist and do NOT provide a compatibility verdict yet.
- **CRITICAL: If core_specialist_blocked is true (required specialist for this intent is not available due to governance constraints), immediately stop and return:**
  ```json
  {
    "final_answer": "I cannot execute this request based on your current role and governance constraints. The required capabilities are restricted by your access level.",
    "agents_used": [],
    "routing_decision": {
      "intent": "...",
      "risk_tier": "...",
      "persona": "...",
      "disclaimer_accepted": false,
      "discovery_mode": "..."
    },
    "confidence": 0.0,
    "governance_notices": ["Request blocked: Required specialist capabilities are not available for this role."],
    "disclaimer_required": false
  }
  ```
  Do NOT proceed to STEP 3 when core_specialist_blocked is true.
- If route is empty (but core_specialist_blocked is false), continue to STEP 3 normally with wrapper agents only.

STEP 3: EXECUTE ROUTE
- Call specialists in route order using call_specialist_agent.
- Never execute STEP 3 when disclaimer_gate_triggered is true.
- Skip re-calling the contextualizer if it already ran in STEP 1.
- Consolidate outputs into final_answer.

Governance rules:
- Persona/risk/disclaimer/trust constraints are enforced by metadata filtering.
- Elevated-risk requests must not bypass metadata eligibility.
- disclaimer_required is true whenever selected or blocked specialists indicate a disclaimer gate.

Return strict JSON:
{
  "final_answer": "well-formatted response for the user",
  "agents_used": ["list of specialist agent names called"],
  "routing_decision": {
    "intent": "...",
    "risk_tier": "...",
    "persona": "...",
    "disclaimer_accepted": false,
    "discovery_mode": "..."
  },
  "confidence": 0.0,
  "governance_notices": ["policy notices, disclaimers, or gating reasons"],
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
        tools=[discover_pf_agents, plan_dynamic_route, call_specialist_agent],
        default_options={"store": False},
    )
    return ResponsesHostServer(agent)


if __name__ == "__main__":
    asyncio.run(setup()).run()