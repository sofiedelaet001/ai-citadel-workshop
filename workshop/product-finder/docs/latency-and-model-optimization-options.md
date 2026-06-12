# Product Finder: Latency and Model Optimization Options

This note captures the main improvement options discussed for the Product Finder hosted-agent workflow.

## 1. Model Choice: Reasoning Quality vs Latency

Model selection is the largest single lever for end-to-end response time, but it directly affects reasoning quality.

Current practical tradeoff discussed:

1. `gpt-4.1`
- Usually the safer baseline for balanced quality and latency.
- Often faster than stronger reasoning-oriented models.
- Good default when the orchestrator and specialists must stay responsive.

2. `gpt-5.2`
- Better fit when reasoning quality matters more than raw speed.
- Expected to be somewhat slower than `gpt-4.1` in many cases.
- Better candidate when `gpt-5.4-mini` is too weak for the scenario.

3. `gpt-5.4-mini`
- Best latency candidate among the models discussed.
- Lower cost and faster response time are the main advantages.
- May degrade reasoning quality for multi-step or higher-governance tasks.

Recommended operating guidance:

1. If reasoning regressions are visible, prefer `gpt-4.1` or `gpt-5.2`.
2. If latency is the top priority and quality still holds, prefer `gpt-5.4-mini`.
3. If possible, use a split strategy:
- Faster model for orchestrator routing and lightweight specialists.
- Stronger model only for harder reasoning steps.

Important constraint:
- Model switches also need APIM allow-list and policy alignment, not only environment variable changes.

## 2. Latency Analysis and Improvement Options

### 2.1 What Actually Drives Latency

For this architecture, end-to-end latency is usually dominated by:

1. LLM inference time.
2. Number of agent-to-agent calls per request.
3. APIM and Foundry network hops.
4. Cold starts and scale-from-zero behavior.
5. Search or downstream retrieval calls.

Because of that, container-only optimizations help, but they usually do not produce the biggest gains for steady-state requests.

### 2.2 Use a Faster Model

Impact:
- Usually the largest direct latency lever.

Pros:
- Immediate reduction in inference time if quality remains acceptable.
- No architecture change required.

Cons:
- Can reduce reasoning depth, consistency, and safety nuance.
- Requires APIM policy and model-access contract alignment.

When to use:
- When traces show model time dominates total request latency.

### 2.3 Reduce Container Size for Startup Time

Impact:
- Helps cold start more than hot-path latency.

What to do:
- Use multi-stage Dockerfiles.
- Keep runtime image slim.
- Avoid unnecessary build/runtime dependencies.

Pros:
- Faster image pull and startup.
- Cleaner runtime containers.

Cons:
- Little benefit for already warm instances.
- Does not meaningfully reduce LLM inference time.

When to use:
- When startup delays are visible after deploys or scale-out events.

### 2.4 Keep Instances Warm

Impact:
- Can materially reduce cold-start latency.

What to do:
- Prefer infrastructure support for minimum active instances if the platform exposes it.
- If the platform does not expose that setting, use controlled warm-up traffic as a fallback.

Pros:
- Reduces scale-from-zero penalties.
- Helps first-request latency.

Cons:
- Increases cost.
- Warm-up pings are operationally weaker than native min-replica controls.

When to use:
- When latency spikes mostly affect the first request after idle periods.

### 2.5 Increase Agent CPU and Memory

Impact:
- Usually a modest improvement, not a primary fix.

What it can improve:
- Container startup and import time.
- Local parsing, orchestration logic, and HTTP handling.
- Throughput and stability under concurrency.

What it usually does not improve much:
- Model inference time.
- APIM round-trip time.
- Azure AI Search latency.

Pros:
- Simple operational change.
- Can reduce local contention.

Cons:
- Higher cost.
- Limited effect when the bottleneck is external.

Guidance discussed:
- Expect a modest gain, not a dramatic one.
- More likely to help the orchestrator under concurrency than to halve single-request latency.

### 2.6 Shorten Orchestrator Instructions

Impact:
- Can help both latency and consistency if done carefully.

What to do:
- Reduce repetitive instruction text.
- Keep the mandatory routing and governance rules explicit.
- Remove non-essential wording and duplicate constraints.

Pros:
- Reduces prompt token count.
- Can improve routing responsiveness.

Cons:
- Too much compression can weaken behavior and governance adherence.

When to use:
- When the orchestrator prompt is long and every request pays that token cost.

### 2.7 Parallelize Independent Specialist Calls

Impact:
- One of the highest-value architectural optimizations if dependencies allow it.

What to do:
- Run independent specialists concurrently instead of strictly sequentially.
- Keep dependency-constrained steps serialized.
- Preserve deterministic merge and governance checks.

Pros:
- Reduces wall-clock latency for multi-agent flows.
- Targets architecture overhead directly.

Cons:
- Adds orchestration complexity.
- Requires careful treatment of dependencies, failures, and evidence merging.

When to use:
- When multiple specialists are independent once the intent and governance gate are known.

### 2.8 Likely Priority Order

For the Product Finder architecture, the most promising order is:

1. Reduce unnecessary specialist calls.
2. Parallelize truly independent specialist calls.
3. Choose the fastest model that still preserves required reasoning quality.
4. Keep instances warm if cold starts are a visible problem.
5. Shorten orchestrator instructions without removing critical governance behavior.
6. Reduce container size to improve startup behavior.
7. Increase CPU and memory for better headroom and concurrency.

## 3. Persona Enforcement: From Workshop Simulation to Production

The workshop uses a simplified persona flow for demonstration. In a real production system, persona should come from a trusted upstream identity control — not hardcoded in agent code or inferred from prompt text. This section covers all realistic options from lightest-weight simulation to full enterprise identity, so you can choose the right level of enforcement for your deployment.

### 3.1 Core Principle

The important separation is:

1. Authentication: who is calling.
2. Authorization and persona resolution: what that caller is allowed to do.
3. Orchestrator behavior: how the system routes and gates requests based on that resolved persona.

In production, the orchestrator should consume persona as trusted request context. It should not infer persona from user prompt text, and it should not hardcode persona defaults in the agent logic.

### 3.2 Option A: APIM Header-Based Persona Simulation

Best for: workshops, demos, internal prototypes.

Pattern:
- The demo client, notebook, or test harness sends a value such as `x-user-persona: external_customer` or `x-user-persona: internal_scientist`.
- APIM validates that the value is one of the allowed workshop personas.
- APIM forwards a normalized governance context to the orchestrator.

Pros:
- Simple and easy to explain.
- No external identity dependency.
- Good fit for workshops and controlled demos.

Cons:
- Not strong authentication.
- Caller-controlled unless APIM policy constrains and normalizes it.

Best use:
- Workshop and internal demo scenarios.

### 3.3 Option B: APIM Subscription Or Product To Persona Mapping

Best for: customer workshops, demos without Entra, low-overhead persona switching.

Pattern:
- Different APIM subscriptions or APIM products represent different persona classes.
- APIM derives persona from the subscription key or product binding rather than trusting a caller-supplied persona field.
- APIM injects the resolved persona into the downstream request context.

Pros:
- Better than raw header simulation because persona is tied to APIM access provisioning.
- Still works without Entra.
- Cleaner customer demo because the caller does not explicitly set persona.

Cons:
- Still workshop-grade identity, not enterprise user identity.
- Persona is attached to the credential used, not an actual human user profile.

Best use:
- Customer workshops where you want a more realistic persona split without introducing Entra.

### 3.4 Option C: Lightweight JWT Claims Without Enterprise IdP

Best for: pre-production validation, realistic claim-based enforcement without requiring Entra onboarding.

Pattern:
- A simple token issuer creates JWTs with claims like `persona=external_customer` or `persona=internal_scientist`.
- APIM validates the token against a known signing key or issuer.
- APIM extracts persona claims and forwards trusted context.

Pros:
- Much closer to a real production pattern.
- Still avoids Entra if needed.
- Lets you demonstrate claim-based policy enforcement.

Cons:
- More setup than header or subscription mapping.
- You must operate a token issuer, even if minimal.

Best use:
- Advanced workshop or pre-production scenarios where you want realistic auth behavior without requiring customer Entra onboarding.

### 3.5 Option D: Entra ID Workforce Identity

Best for: production internal users — employees, partners, internal scientists.

Pattern:
- Internal users authenticate with Entra ID.
- APIM validates the token.
- Persona or role is derived from Entra app roles, groups, or claims mapping.
- The orchestrator receives only trusted downstream context.

Pros:
- Strong enterprise identity model.
- Centralized access control and auditing.
- Good fit for internal scientist personas.

Cons:
- Requires tenant access and onboarding.
- Not suitable for workshop attendees who do not have Entra access.

Best use:
- Internal employee or partner-only production flows.

### 3.6 Option E: Customer Identity Provider Or External ID

Best for: production external customer flows — B2C, partner portals, customer-facing applications.

Pattern:
- External customers authenticate through a customer-facing identity system such as Entra External ID, B2C-style flow, or another OIDC provider.
- APIM validates the external token.
- Persona is derived from customer account tier, claims, contract, or mapped profile.

Pros:
- Real customer-facing identity story.
- Clear separation between external and internal users.
- Scales better than workshop simulation.

Cons:
- More operational and integration complexity.
- Requires identity design beyond the workshop scope.

Best use:
- Production customer-facing applications.

### 3.7 Recommended Trust Boundary Architecture

A strong architecture for persona enforcement is:

1. Client authenticates to a trusted gateway.
2. APIM validates the credential or workshop access key.
3. APIM resolves persona from a trusted source.
4. APIM forwards normalized persona context to the orchestrator.
5. The orchestrator applies routing, gating, and specialist eligibility rules from that trusted context.

This keeps persona enforcement outside the agents themselves and makes the orchestrator consume, rather than invent, identity context.

### 3.8 Recommended Approach By Scenario

Workshop with no Entra access:
1. Default: APIM subscription-to-persona mapping (Option B).
2. Simplest fallback: APIM-validated persona header (Option A).
3. More realistic demo: lightweight JWT claims (Option C).

Production internal users (employees, scientists):
1. Entra ID Workforce with app roles or group claims (Option D).
2. APIM validates token and forwards trusted persona context downstream.

Production external customers:
1. Entra External ID, B2C, or existing customer IdP (Option E).
2. Persona derived from customer tier, contract, or profile claims.

Across all scenarios, the principle is the same: enforce persona at the gateway, not in agent code.
