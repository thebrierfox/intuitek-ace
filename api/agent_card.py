"""
A2A Agent Card — published at /.well-known/agent-card.json
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
    ],
    "defaultInputModes": ["text", "application/json"],
    "defaultOutputModes": ["application/json"],
    "supportsAuthenticatedExtendedCard": False,
}


@agent_card_router.get("/.well-known/agent-card.json")
async def get_agent_card():
    """A2A Agent Card — advertises IntuiTek¹ ACE capabilities to the agent network."""
    return JSONResponse(
        content=AGENT_CARD,
        headers={"Cache-Control": "public, max-age=3600"},
    )
