# ACE — IntuiTek¹ Agent Commerce Engine

> Three AI-powered APIs. Pay per call via x402 (USDC on Base) or subscribe. Accessible by agents and developers via MCP (Streamable HTTP) and A2A protocols.

**Live on Railway. 50 free trial calls. No API key required for trial.**

---

## Products

| API | Description | Price |
|-----|-------------|-------|
| **YIELD INTELLIGENCE** | Passive income opportunity scanner — high-yield dividend analysis, portfolio optimization, monthly income targeting | $1 / call |
| **ACE Autonomous Commerce** | Execute purchases and service subscriptions on behalf of users or agents, with spending limit enforcement | $2 / call |
| **COUNSELOR AI Strategy** | AI infrastructure strategy, MCP server selection, agent architecture consulting | $15 / call |

Subscription tiers available (Starter $29/mo · Professional $99/mo · Enterprise $499/mo).

---

## Discovery

### A2A (Agent-to-Agent)

Agent card at the standard discovery location:

```
https://api.intuitek.ai/.well-known/agent-card.json
```

### MCP (Model Context Protocol)

Streamable HTTP, spec 2025-11-25. Mount in any MCP client:

```
https://api.intuitek.ai/yield      # YIELD INTELLIGENCE
https://api.intuitek.ai/ace        # ACE Autonomous Commerce
https://api.intuitek.ai/counselor  # COUNSELOR AI Strategy
```

### Machine-readable pricing

```
https://api.intuitek.ai/pricing
```

---

## Payment

**x402 micropayments (per call):**

```
Asset: USDC on Base (0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913)
payTo: 0x03d773c52B67993e60Ecb3134b17436fE03B584c
x-payment header: follow x402 spec
```

**Subscription (ACP):**

```
POST https://api.intuitek.ai/checkouts
```

**Trial:**

```
50 free calls — no payment required
```

---

## Quick start (developer)

```bash
# Check health
curl https://ace-license-server-production.up.railway.app/health

# Get pricing
curl https://api.intuitek.ai/pricing

# Call a tool (trial — no payment needed for first 50 calls)
curl -X POST https://api.intuitek.ai/yield/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "id": 1,
    "params": {
      "name": "analyze_yield_opportunities",
      "arguments": {
        "investment_capital": 50000,
        "risk_tolerance": "moderate"
      }
    }
  }'
```

---

## License delivery (ClawMart products)

ACE also serves as the backend for [IntuiTek¹ ClawMart products](https://shopclawmart.com/@thebrierfox):

- Stripe webhook intake (signed)
- Fernet-encrypted license key delivery via Resend
- License validation endpoint: `GET /validate?key=<key>`

See [ClawMart store](https://shopclawmart.com/@thebrierfox) for available skill packages.

---

## API reference

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Heartbeat — returns status, active_subscribers, mrr_cents |
| GET | `/pricing` | Machine-readable product and pricing catalog |
| POST | `/stripe/webhook` | Stripe event ingestion (signed) |
| GET | `/validate` | License key validation |
| POST | `/intake/submit` | Customer intake backend |
| GET | `/.well-known/agent-card.json` | A2A agent card (via api.intuitek.ai) |
| POST/GET/DELETE | `/mcp` | MCP Streamable HTTP endpoint (per server) |

---

## Self-hosting

```bash
git clone https://github.com/thebrierfox/intuitek-ace
cp .env.example .env  # fill in STRIPE_*, FERNET_KEY, RESEND_API_KEY
pip install -r requirements.txt
uvicorn ace_server:app --reload --port 8080
```

See `.env.example` for all required variables.

---

*Operator: ~K¹ (William Kyle Million) / IntuiTek¹ · [intuitek.ai](https://intuitek.ai)*
