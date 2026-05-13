"""
GET /pricing — Machine-readable pricing for all IntuiTek¹ products.
Prices sourced from config/pricing.json — single canonical truth.
"""
import json
import pathlib

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

pricing_router = APIRouter()

_PRICING_PATH = pathlib.Path(__file__).parent.parent / "config" / "pricing.json"
with open(_PRICING_PATH) as _f:
    _CANONICAL = json.load(_f)

# Build price lookup: product_id → x402_price_usd
_PRICE_BY_ID = {p["id"]: p["x402_price_usd"] for p in _CANONICAL["products"]}

PRICING = {
    "products": [
        {
            "id": "yield-intelligence-pro",
            "name": "YIELD INTELLIGENCE Pro",
            "description": "Passive Income Terminal — high-yield dividend stock analysis, portfolio optimization, and AI analyst for income-focused investors.",
            "pricing_models": [
                {"type": "per_request", "protocol": "x402", "price_usd": _PRICE_BY_ID["yield-intelligence-pro"], "unit": "tool_call"},
                {
                    "type": "subscription",
                    "protocol": "acp",
                    "checkout_url": "https://api.intuitek.ai/checkouts",
                    "tiers": [
                        {"name": "starter", "price_usd": 29, "period": "month", "included_calls": 1000},
                        {"name": "professional", "price_usd": 99, "period": "month", "included_calls": 10000},
                        {"name": "enterprise", "price_usd": 499, "period": "month", "included_calls": "unlimited"},
                    ],
                },
                {"type": "credits", "protocol": "nevermined", "credit_price_usd": 0.001, "minimum_purchase": 1000},
            ],
            "payment_methods": ["shared_payment_token", "x402_wallet", "agent_wallet", "api_key_billing"],
            "trial": {"available": True, "calls": 50, "requires_payment": False},
        },
        {
            "id": "ace-autonomous-commerce",
            "name": "ACE Autonomous Commerce Engine",
            "description": "Autonomous purchase execution and license provisioning.",
            "pricing_models": [
                {"type": "per_request", "protocol": "x402", "price_usd": _PRICE_BY_ID["ace-autonomous-commerce"], "unit": "tool_call"},
                {
                    "type": "subscription",
                    "protocol": "acp",
                    "checkout_url": "https://api.intuitek.ai/checkouts",
                    "tiers": [
                        {"name": "starter", "price_usd": 39, "period": "month", "included_calls": 500},
                        {"name": "professional", "price_usd": 149, "period": "month", "included_calls": 5000},
                    ],
                },
            ],
            "payment_methods": ["shared_payment_token", "x402_wallet", "api_key_billing"],
            "trial": {"available": True, "calls": 25, "requires_payment": False},
        },
        {
            "id": "counselor-ai-strategy",
            "name": "COUNSELOR AI Strategy Advisor",
            "description": "Expert AI infrastructure guidance and agent stack evaluation for developers and CTOs building autonomous systems. Get architectural decisions, framework comparisons, and implementation strategy from a specialized AI systems advisor.",
            "pricing_models": [
                {"type": "per_request", "protocol": "x402", "price_usd": _PRICE_BY_ID["counselor-ai-strategy"], "unit": "tool_call"},
                {
                    "type": "subscription",
                    "protocol": "acp",
                    "checkout_url": "https://api.intuitek.ai/checkouts",
                    "tiers": [
                        {"name": "starter", "price_usd": 29, "period": "month", "included_calls": 200},
                        {"name": "professional", "price_usd": 99, "period": "month", "included_calls": 2000},
                    ],
                },
            ],
            "payment_methods": ["shared_payment_token", "x402_wallet", "api_key_billing"],
            "trial": {"available": True, "calls": 25, "requires_payment": False},
        },

    ],
    "mcp_servers": [
        {"product": "yield-intelligence", "url": "https://mcp.intuitek.ai/yield", "transport": "streamable-http"},
        {"product": "ace", "url": "https://mcp.intuitek.ai/ace", "transport": "streamable-http"},
        {"product": "counselor", "url": "https://mcp.intuitek.ai/counselor", "transport": "streamable-http"},
    ],
}


@pricing_router.get("")
@pricing_router.get("/")
async def get_pricing():
    """Machine-readable pricing for all IntuiTek¹ products and services."""
    return JSONResponse(content=PRICING)


@pricing_router.get("/{product_id}")
async def get_pricing_by_product(product_id: str):
    """Return pricing for a specific product by ID."""
    product = next((p for p in PRICING["products"] if p["id"] == product_id), None)
    if not product:
        raise HTTPException(
            status_code=404,
            detail=f"Product '{product_id}' not found. "
                   f"Available: {[p['id'] for p in PRICING['products']]}",
        )
    return JSONResponse(content=product)
