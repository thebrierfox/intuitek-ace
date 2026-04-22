# ACE — Agent Commerce Engine

FastAPI license server for IntuiTek¹ products. Handles Stripe webhook intake, Fernet-encrypted key delivery via Resend, and exposes MCP tool surfaces for agent-to-agent commerce.

## Surfaces

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/stripe/webhook` | Stripe event ingestion (signed) |
| GET | `/validate` | License key validation |
| POST | `/intake/submit` | Customer intake form backend |
| GET | `/intake/verify/{token}` | Token pre-validation (frontend) |
| GET | `/health` | Heartbeat probe |

MCP servers are mounted under `/mcp/` (ACE, COUNSELOR, YIELD).

## Deployment

Deployed on Railway. Dockerfile builds a single service on port 8080 with Railway TLS.

```bash
# Local dev
pip install -r requirements.txt
cp .env.example .env  # fill in values
uvicorn ace_server:app --reload --port 8080
```

## Environment variables

See `.env.example` for all required variables and how to generate the Fernet key.

## Customer model

Customers are BYOK (bring your own Anthropic key + VPS). ACE delivers encrypted license packages via Resend on successful Stripe payment.

---

*Operator: ~K¹ (William Kyle Million) / IntuiTek¹*
