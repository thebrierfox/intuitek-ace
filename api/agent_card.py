"""
A2A Agent Card — published at /.well-known/agent-card.json and /.well-known/agent.json
Spec: https://google.github.io/A2A
"""
import json
import pathlib

from fastapi import APIRouter
from fastapi.responses import JSONResponse

agent_card_router = APIRouter()

_PRICING_PATH = pathlib.Path(__file__).parent.parent / "config" / "pricing.json"
with open(_PRICING_PATH) as _f:
    _CANONICAL = json.load(_f)

_PRICE_BY_ID = {p["id"]: p["x402_price_usd"] for p in _CANONICAL["products"]}
_PAY_TO = _CANONICAL["x402"]["pay_to"]

AGENT_CARD = {
    "schemaVersion": "1.0",
    "name": "IntuiTek¹ ACE",
    "description": (
        "IntuiTek¹ Autonomous Commerce Engine — AI agent infrastructure providing "
        "yield intelligence, autonomous commerce execution, and AI strategy consulting. "
        "Accessible via MCP (Streamable HTTP) and A2A protocols."
    ),
    "url": "https://api.intuitek.ai",
    "provider": {
        "organization": "IntuiTek¹",
        "url": "https://intuitek.ai",
        "contact": "agent@intuitek.ai",
    },
    "version": "1.0.0",
    "documentationUrl": "https://intuitek.ai/docs",
    "capabilities": {
        "streaming": True,
        "pushNotifications": False,
        "stateTransitionHistory": True,
    },
    "authentication": {
        "schemes": ["Bearer", "x402"],
        "description": (
            "API key via Authorization: Bearer <key>, "
            f"or x402 micropayment via x-payment header (USDC on Base, payTo: {_PAY_TO})"
        ),
    },
    "skills": [
        {
            "id": "yield-intelligence",
            "name": "YIELD INTELLIGENCE",
            "description": (
                "Identify passive income opportunities and optimize investment portfolios "
                "for maximum recurring yield."
            ),
            "tags": ["finance", "yield", "passive-income", "portfolio", "investing"],
            "examples": [
                "Analyze yield opportunities for $50,000 with moderate risk tolerance",
                "Optimize my portfolio for $5,000/month passive income",
            ],
            "inputModes": ["text", "application/json"],
            "outputModes": ["application/json"],
            "mcpServer": "https://api.intuitek.ai/yield",
            "pricing": {
                "perCall": {"protocol": "x402", "price_usd": _PRICE_BY_ID["yield-intelligence-pro"], "payTo": _PAY_TO},
                "subscription": {"protocol": "acp", "checkout_url": "https://api.intuitek.ai/checkouts"},
            },
        },
        {
            "id": "ace-commerce",
            "name": "ACE Autonomous Commerce",
            "description": (
                "Execute purchases and service subscriptions autonomously on behalf of users "
                "or other agents, with spending limit enforcement."
            ),
            "tags": ["commerce", "autonomous", "purchasing", "payments", "acp"],
            "examples": [
                "Purchase yield-intelligence-pro subscription with spending limit $99",
                "Get pricing for all IntuiTek¹ products",
            ],
            "inputModes": ["text", "application/json"],
            "outputModes": ["application/json"],
            "mcpServer": "https://api.intuitek.ai/ace",
            "pricing": {
                "perCall": {"protocol": "x402", "price_usd": _PRICE_BY_ID["ace-autonomous-commerce"], "payTo": _PAY_TO},
                "subscription": {"protocol": "acp", "checkout_url": "https://api.intuitek.ai/checkouts"},
            },
        },
        {
            "id": "counselor-strategy",
            "name": "COUNSELOR AI Strategy",
            "description": (
                "Expert guidance on AI infrastructure, agent architecture, MCP server selection, "
                "and autonomous workflow design."
            ),
            "tags": ["ai-strategy", "architecture", "consulting", "mcp", "agents"],
            "examples": [
                "What MCP servers should I use for an autonomous e-commerce agent?",
                "Evaluate LangGraph vs Claude Agent SDK for my use case",
            ],
            "inputModes": ["text", "application/json"],
            "outputModes": ["application/json"],
            "mcpServer": "https://api.intuitek.ai/counselor",
            "pricing": {
                "perCall": {"protocol": "x402", "price_usd": _PRICE_BY_ID["counselor-ai-strategy"], "payTo": _PAY_TO},
                "subscription": {"protocol": "acp", "checkout_url": "https://api.intuitek.ai/checkouts"},
            },
        },
        {
            "id": "coap-city-analysis",
            "name": "COAP — City Opportunity Analysis",
            "description": (
                "AI-powered market analysis for any U.S. city: Census demographics, BLS labor data, "
                "and OpenStreetMap business density combined into a business opportunity report with "
                "startup capital estimates, Year 1 revenue projections, and a 90-day execution plan. "
                "No paid data sources. Validated on real client deliverables."
            ),
            "tags": ["market-analysis", "business-intelligence", "real-estate", "small-business", "location-analysis"],
            "examples": [
                "Analyze Poplar Bluff, MO for the highest-ROI new business opportunity",
                "What business should I open in Cape Girardeau, MO?",
                "Give me a full market report for Fayetteville, AR",
            ],
            "inputModes": ["text", "application/json"],
            "outputModes": ["application/json", "text/markdown"],
            "pricing": {
                "perReport": {
                    "protocol": "stripe",
                    "price_usd": 49.00,
                    "checkout_url": "https://ace-license-server-production.up.railway.app/coap/checkout",
                },
                "subscription": {
                    "protocol": "stripe",
                    "price_usd": 149.00,
                    "interval": "month",
                    "checkout_url": "https://ace-license-server-production.up.railway.app/coap/checkout",
                },
            },
        },
    ],
    "defaultInputModes": ["text", "application/json"],
    "defaultOutputModes": ["application/json"],
    "supportsAuthenticatedExtendedCard": False,
}


@agent_card_router.get("/.well-known/agent-card.json")
@agent_card_router.get("/.well-known/agent.json")
async def get_agent_card():
    """A2A Agent Card — both the legacy path and the Google A2A spec canonical path."""
    return JSONResponse(
        content=AGENT_CARD,
        headers={"Cache-Control": "public, max-age=3600"},
    )
