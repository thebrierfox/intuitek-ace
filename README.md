# ACE — IntuiTek¹ Agent Commerce Engine

> BYOK Python tools + AI-powered APIs + city market intelligence. One-time purchase or pay-per-report. No subscription required.

---

## BYOK Tools (one-time purchase, $29 each)

Python tools that run on your machine with your own Anthropic API key. No subscription. No data leaves your environment.

**[Browse the store →](https://api.intuitek.ai/byok/)**

| Tool | Description | Price |
|------|-------------|-------|
| **[MoatMRI™](https://api.intuitek.ai/byok/moatmri)** | Pressure-test any business against 10 strategic vectors. Outputs a Pressure Map, AI Front-Door Takeover Storyboard, and 90-Day Counterstrike Plan. | $29 one-time |
| **[DOC2MATH™](https://api.intuitek.ai/byok/doc2math)** | Convert technical documents into formal mathematical problem structures using the Zero-Inference Protocol — grounded, inference-tagged, MISSING-marked. | $29 one-time |

Both tools:
- Run locally — your Anthropic key, your data, zero vendor lock-in
- Python 3.9+ · 3 files · no external dependencies beyond the `anthropic` SDK
- One-time $29 purchase via Stripe — download ZIP immediately after payment

---

## COAP — City Opportunity Analysis (pay-per-report)

Market intelligence for US cities. Identifies the highest-potential business opportunities in any US city by cross-referencing Census data, BLS employment stats, and OpenStreetMap business density — all free public sources.

**[$49/report](https://api.intuitek.ai/coap/checkout) · $149/mo unlimited**

- Submit city + optional focus sector
- Receive structured analysis: demand gaps, estimated revenue ranges, startup cost bands, saturation assessment
- Output validated example: Doniphan MO → auto repair shop recommendation ($260K–$335K Year 1 revenue, $67K–$160K startup)
- No API key required — hosted analysis, results by email
- Pending queue when analysis capacity is limited (email notified on completion)

---

## YIELD INTELLIGENCE MCP Server (free trial, $1/call)

Passive income opportunity scanner — accessible by agents and developers via MCP (Streamable HTTP).

**50 free trial calls. No API key required.**

Add to any MCP client (Claude Desktop, Cursor, Windsurf, Cline, etc.):

```json
{
  "mcpServers": {
    "yield-intelligence": {
      "url": "https://api.intuitek.ai/yield/mcp"
    }
  }
}
```

After adding, your AI assistant gains two tools:

| Tool | What it does |
|------|-------------|
| `analyze_yield_opportunities` | Scans Treasury yields, dividend ETFs, REITs, preferred stocks, and CDs — surfaces the highest-returning options for your capital and risk tolerance |
| `optimize_income_portfolio` | Builds or rebalances a diversified portfolio to hit a target monthly income figure, with suggested allocation percentages and rebalancing cadence |

**Example prompts:**
- *"I have $50k to invest for passive income at moderate risk. What's yielding the most right now?"*
- *"Build me a portfolio targeting $500/month income. I prefer low volatility."*

---

## API Discovery

### A2A (Agent-to-Agent)

Agent card at the standard discovery location:

```
https://api.intuitek.ai/.well-known/agent-card.json
```

### MCP (Model Context Protocol)

Streamable HTTP, spec 2025-11-25. Mount in any MCP client:

```
https://api.intuitek.ai/yield      # YIELD INTELLIGENCE
```

### Machine-readable pricing

```
https://api.intuitek.ai/pricing
```

---

## Payment (pay-per-call)

**x402 micropayments:**

```
Asset: USDC on Base (0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913)
payTo: 0x03d773c52B67993e60Ecb3134b17436fE03B584c
x-payment header: follow x402 spec
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

## BYOK delivery backend

ACE handles one-time product delivery:

- Stripe checkout + signed webhook intake
- Fernet-encrypted download token generation
- Download link delivery via Resend (email on first payment verification)
- Download endpoint: `GET /byok/{product}/download/{token}`

---

## API reference

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Heartbeat — returns status, active_subscribers, mrr_cents |
| GET | `/byok/` | BYOK store index |
| GET | `/byok/{product}` | Product page with Stripe checkout |
| POST | `/byok/{product}/checkout` | Create Stripe Checkout Session |
| GET | `/byok/{product}/download/{token}` | Verify payment, stream ZIP |
| POST | `/coap/checkout` | Create COAP Stripe Checkout Session |
| GET | `/coap/form/{token}` | COAP order form (post-payment) |
| POST | `/coap/submit/{token}` | Submit city analysis request |
| GET | `/pricing` | Machine-readable product and pricing catalog |
| POST | `/stripe/webhook` | Stripe event ingestion (signed) |
| GET | `/validate` | License key validation |
| GET | `/.well-known/agent-card.json` | A2A agent card (via api.intuitek.ai) |
| POST/GET | `/yield/mcp` | YIELD INTELLIGENCE MCP endpoint |

---

## Self-hosting

```bash
git clone https://github.com/thebrierfox/intuitek-ace
cp .env.example .env  # fill in STRIPE_*, FERNET_KEY, RESEND_API_KEY, BYOK_PRICE_MOATMRI, BYOK_PRICE_DOC2MATH
pip install -r requirements.txt
uvicorn ace_server:app --reload --port 8080
```

See `.env.example` for all required variables.

---

*Operator: ~K¹ (William Kyle Million) / IntuiTek¹ · [intuitek.ai](https://intuitek.ai)*
