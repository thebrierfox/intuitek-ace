"""
GET /pricing — Machine-readable pricing for all IntuiTek¹ products.
"""
from fastapi import APIRouter
from fastapi.responses import JSONResponse

pricing_router = APIRouter()

PRICING = {
    "products": [
        {
            "id": "yield-intelligence-pro",
            "name": "YIELD INTELLIGENCE Pro",
            "description": "Full yield analysis and portfolio optimization for generating passive income",
            "pricing_models": [
                {"type": "per_request", "protocol": "x402", "price_usd": 0.05, "unit": "tool_call"},
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
            "description": "Autonomous purchase execution and license provisioning",
            "pricing_models": [
                {"type": "per_request", "protocol": "x402", "price_usd": 0.05, "unit": "tool_call"},
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
            "name": "COUNSELOR AI Strategy",
            "description": "Expert AI infrastructure guidance and agent architecture consulting",
            "pricing_models": [
                {"type": "per_request", "protocol": "x402", "price_usd": 0.10, "unit": "tool_call"},
                {
                    "type": "subscription",
                    "protocol": "acp",
                    "checkout_url": "https://api.intuitek.ai/checkouts",
                    "tiers": [
                        {"name": "starter", "price_usd": 49, "period": "month", "included_calls": 200},
                        {"name": "professional", "price_usd": 199, "period": "month", "included_calls": 2000},
                    ],
                },
            ],
            "payment_methods": ["shared_payment_token", "x402_wallet", "api_key_billing"],
            "trial": {"available": True, "calls": 10, "requires_payment": False},
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
    """Machine-readable pricing for all IntuiTek\u00b9 products and services."""
    return JSONResponse(content=PRICING)
