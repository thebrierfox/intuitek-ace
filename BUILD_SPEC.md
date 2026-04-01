# IntuiTek¹ MCP Infrastructure — Project Spec

## Objective
Build and deploy three Streamable HTTP MCP servers for YIELD INTELLIGENCE, ACE, and COUNSELOR. Also implement: A2A Agent Card, GET /pricing endpoint, x402 middleware, ACP checkout stubs, llms.txt, AGENTS.md.

## Repository
- **GitHub:** https://github.com/thebrierfox/intuitek-ace
- **GitHub Token:** [REDACTED — stored in Railway env / CI secrets]
- **Branch:** main (auto-deploys to Railway)

## Existing Stack
- FastAPI + Python
- SQLite on Railway persistent volume `/data/ace.db`
- Railway service: cf0d566a-52bd-4b92-a17e-6b1a682e7608
- Live domain: https://ace-license-server-production.up.railway.app

## Target Domains
- `https://mcp.intuitek.ai/yield` — YIELD INTELLIGENCE MCP server
- `https://mcp.intuitek.ai/ace` — ACE MCP server
- `https://mcp.intuitek.ai/counselor` — COUNSELOR MCP server
- `https://api.intuitek.ai/.well-known/agent-card.json` — A2A Agent Card
- `https://api.intuitek.ai/pricing` — Machine-readable pricing
- `https://api.intuitek.ai/v1/*` — x402 payment middleware layer

NOTE: DNS for mcp.intuitek.ai and api.intuitek.ai not yet configured — flag as blockers for K¹.

## MCP Transport
MCP spec 2025-11-25, Streamable HTTP transport.
- Each server exposes: POST /mcp (main endpoint), GET /mcp (SSE for streaming), DELETE /mcp (session cleanup)
- Content-Type: application/json or text/event-stream
- Sessions via Mcp-Session-Id header

## Tool Definitions (EXACT — do not deviate)

### YIELD INTELLIGENCE (/yield)

```python
YIELD_TOOLS = [
    {
        "name": "analyze_yield_opportunities",
        "title": "Yield Opportunity Analyzer",
        "description": "Identify the highest-returning passive income opportunities across asset classes. Use when the user wants to generate passive income, maximize portfolio yield, or find dividend and interest-bearing investments.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "investment_capital": {"type": "number", "description": "Available capital in USD"},
                "monthly_income_target": {"type": "number", "description": "Target monthly passive income in USD"},
                "risk_tolerance": {"type": "string", "enum": ["conservative", "moderate", "aggressive"]}
            },
            "required": ["investment_capital"],
            "additionalProperties": False
        },
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True}
    },
    {
        "name": "optimize_income_portfolio",
        "title": "Income Portfolio Optimizer",
        "description": "Build and rebalance a diversified portfolio to maximize recurring income. Use when the user wants to achieve financial independence through investment income or optimize an existing portfolio for yield.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "current_holdings": {"type": "array", "items": {"type": "object"}, "description": "Current portfolio positions"},
                "target_monthly_income": {"type": "number", "description": "Desired monthly income in USD"},
                "time_horizon_years": {"type": "integer", "description": "Investment time horizon in years"}
            },
            "required": ["target_monthly_income"],
            "additionalProperties": False
        },
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True}
    }
]
```

### ACE (/ace)

```python
ACE_TOOLS = [
    {
        "name": "execute_autonomous_purchase",
        "title": "Autonomous Purchase Executor",
        "description": "Complete a purchase transaction autonomously without human intervention. Use when an agent needs to buy a product, subscribe to a service, or execute a commerce transaction on behalf of a user.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "product_id": {"type": "string", "description": "Product or service identifier"},
                "payment_method": {"type": "string", "enum": ["shared_payment_token", "x402", "agent_wallet"]},
                "spending_limit_usd": {"type": "number", "description": "Maximum authorized spend in USD"}
            },
            "required": ["product_id", "payment_method"],
            "additionalProperties": False
        },
        "annotations": {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False}
    },
    {
        "name": "get_pricing",
        "title": "Product Pricing Lookup",
        "description": "Retrieve machine-readable pricing for all IntuiTek¹ products and services. Use when an agent needs to evaluate costs before committing to a purchase or subscription.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "product_id": {"type": "string", "description": "Optional product filter"}
            },
            "required": [],
            "additionalProperties": False
        },
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True}
    }
]
```

### COUNSELOR (/counselor)

```python
COUNSELOR_TOOLS = [
    {
        "name": "get_strategic_ai_guidance",
        "title": "AI Strategy Counselor",
        "description": "Get expert strategic guidance on AI infrastructure decisions, agent architecture, and autonomous system design. Use when the user needs advice on building AI agents, selecting AI tools, or designing autonomous workflows.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "question": {"type": "string", "description": "Strategic question about AI infrastructure or agent systems"},
                "context": {"type": "string", "description": "Current situation, constraints, and goals"}
            },
            "required": ["question"],
            "additionalProperties": False
        },
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True}
    },
    {
        "name": "evaluate_agent_stack",
        "title": "Agent Stack Evaluator",
        "description": "Evaluate and compare agent frameworks, MCP servers, and AI infrastructure options for a specific use case. Use when the user needs a recommendation on which AI tools, frameworks, or protocols to adopt.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "use_case": {"type": "string", "description": "Description of the agent use case or problem to solve"},
                "constraints": {"type": "array", "items": {"type": "string"}, "description": "Budget, compliance, or technical constraints"},
                "current_stack": {"type": "string", "description": "Existing tools and infrastructure"}
            },
            "required": ["use_case"],
            "additionalProperties": False
        },
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True}
    }
]
```

## GET /pricing JSON Schema (EXACT)

```json
{
  "products": [
    {
      "id": "yield-intelligence-pro",
      "name": "YIELD INTELLIGENCE Pro",
      "description": "Full yield analysis and portfolio optimization for generating passive income",
      "pricing_models": [
        {"type": "per_request", "protocol": "x402", "price_usd": 0.05, "unit": "tool_call"},
        {
          "type": "subscription", "protocol": "acp",
          "checkout_url": "https://api.intuitek.ai/checkouts",
          "tiers": [
            {"name": "starter", "price_usd": 29, "period": "month", "included_calls": 1000},
            {"name": "professional", "price_usd": 99, "period": "month", "included_calls": 10000},
            {"name": "enterprise", "price_usd": 499, "period": "month", "included_calls": "unlimited"}
          ]
        },
        {"type": "credits", "protocol": "nevermined", "credit_price_usd": 0.001, "minimum_purchase": 1000}
      ],
      "payment_methods": ["shared_payment_token", "x402_wallet", "agent_wallet", "api_key_billing"],
      "trial": {"available": true, "calls": 50, "requires_payment": false}
    },
    {
      "id": "ace-autonomous-commerce",
      "name": "ACE Autonomous Commerce Engine",
      "description": "Autonomous purchase execution and license provisioning",
      "pricing_models": [
        {"type": "per_request", "protocol": "x402", "price_usd": 0.05, "unit": "tool_call"},
        {
          "type": "subscription", "protocol": "acp",
          "checkout_url": "https://api.intuitek.ai/checkouts",
          "tiers": [
            {"name": "starter", "price_usd": 39, "period": "month", "included_calls": 500},
            {"name": "professional", "price_usd": 149, "period": "month", "included_calls": 5000}
          ]
        }
      ],
      "payment_methods": ["shared_payment_token", "x402_wallet", "api_key_billing"],
      "trial": {"available": true, "calls": 25, "requires_payment": false}
    },
    {
      "id": "counselor-ai-strategy",
      "name": "COUNSELOR AI Strategy",
      "description": "Expert AI infrastructure guidance and agent architecture consulting",
      "pricing_models": [
        {"type": "per_request", "protocol": "x402", "price_usd": 0.10, "unit": "tool_call"},
        {
          "type": "subscription", "protocol": "acp",
          "checkout_url": "https://api.intuitek.ai/checkouts",
          "tiers": [
            {"name": "starter", "price_usd": 49, "period": "month", "included_calls": 200},
            {"name": "professional", "price_usd": 199, "period": "month", "included_calls": 2000}
          ]
        }
      ],
      "payment_methods": ["shared_payment_token", "x402_wallet", "api_key_billing"],
      "trial": {"available": true, "calls": 10, "requires_payment": false}
    }
  ],
  "mcp_servers": [
    {"product": "yield-intelligence", "url": "https://mcp.intuitek.ai/yield", "transport": "streamable-http"},
    {"product": "ace", "url": "https://mcp.intuitek.ai/ace", "transport": "streamable-http"},
    {"product": "counselor", "url": "https://mcp.intuitek.ai/counselor", "transport": "streamable-http"}
  ]
}
```

## A2A Agent Card (EXACT — at /.well-known/agent-card.json)

See full JSON in spec. Published at https://api.intuitek.ai/.well-known/agent-card.json.
Add route to main FastAPI app returning static JSON.

## x402 Middleware

- Implement as FastAPI middleware
- Apply to all `/v1/*` routes
- Return 402 with payment requirements header when no valid payment token present
- Payment requirements: {"x402Version": 1, "accepts": [{"scheme": "exact", "network": "base", "maxAmountRequired": "5000000", "resource": "https://api.intuitek.ai/v1/", "description": "IntuiTek¹ API access", "mimeType": "application/json", "payTo": "WALLET_ADDRESS_PLACEHOLDER", "maxTimeoutSeconds": 300, "asset": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913", "extra": {"name": "USDC", "version": "1"}}]}
- On valid x-payment header: process and allow through
- Include x-payment-response header on success
- Use coinbase/x402-python if available, otherwise implement RFC manually

## ACP Checkout (Stripe)

- POST /checkouts → CreateCheckout
- PATCH /checkouts/{id} → UpdateCheckout
- POST /checkouts/{id}/complete → CompleteCheckout
- DELETE /checkouts/{id} → CancelCheckout
- Use existing STRIPE_SECRET_KEY env var
- Stub implementation OK for MVP — real Stripe ACP integration in v2

## File Structure in Repo

```
/mcp/
  __init__.py
  server.py          # Base MCP Streamable HTTP server class
  yield_server.py    # YIELD INTELLIGENCE tools + handlers
  ace_server.py      # ACE tools + handlers
  counselor_server.py # COUNSELOR tools + handlers
  auth.py            # API key + x402 validation
/api/
  pricing.py         # GET /pricing endpoint
  checkouts.py       # ACP checkout endpoints
  agent_card.py      # A2A Agent Card /.well-known/agent-card.json
/middleware/
  x402.py            # x402 payment middleware
main.py              # Updated to mount all routers
```

## main.py Router Mounts

```python
# MCP servers
app.mount("/yield", yield_mcp_app)
app.mount("/ace", ace_mcp_app)
app.mount("/counselor", counselor_mcp_app)

# API endpoints
app.include_router(pricing_router, prefix="/pricing")
app.include_router(checkouts_router, prefix="/checkouts")
app.include_router(agent_card_router)  # handles /.well-known/agent-card.json

# Middleware
app.add_middleware(X402Middleware)
```

## Deployment

- Push to main branch → Railway auto-deploys
- No new Railway service needed — extend existing ace-license-server
- After deploy, verify endpoints:
  - GET /yield (MCP server info)
  - GET /ace
  - GET /counselor
  - GET /.well-known/agent-card.json
  - GET /pricing
  - POST /yield/mcp (MCP Streamable HTTP)

## Success Criteria

1. All three MCP servers respond to initialize request with tool list
2. GET /pricing returns valid JSON with all three products
3. GET /.well-known/agent-card.json returns valid A2A Agent Card
4. POST to /yield/mcp with valid MCP init payload returns server info + tools
5. x402 middleware returns 402 on /v1/* without payment header
6. All endpoints return 200 health checks
7. Code committed and pushed to main
