"""
A2A Agent Card — published at /.well-known/agent-card.json
Spec: https://google.github.io/A2A
"""
from fastapi import APIRouter
from fastapi.responses import JSONResponse

agent_card_router = APIRouter()

AGENT_CARD = {
    "schemaVersion": "1.0",
    "name": "IntuiTek\u00b9 ACE",
    "description": (
        "IntuiTek\u00b9 Autonomous Commerce Engine — AI agent infrastructure providing "
        "yield intelligence, autonomous commerce execution, and AI strategy consulting. "
        "Accessible via MCP (Streamable HTTP) and A2A protocols."
    ),
    "url": "https://api.intuitek.ai",
    "provider": {
        "organization": "IntuiTek\u00b9",
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
            "or x402 micropayment via x-payment header (USDC on Base)"
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
            "mcpServer": "https://mcp.intuitek.ai/yield",
            "pricing": {
                "perCall": {"protocol": "x402", "price_usd": 0.05},
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
                "Get pricing for all IntuiTek\u00b9 products",
            ],
            "inputModes": ["text", "application/json"],
            "outputModes": ["application/json"],
            "mcpServer": "https://mcp.intuitek.ai/ace",
            "pricing": {
                "perCall": {"protocol": "x402", "price_usd": 0.05},
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
            "mcpServer": "https://mcp.intuitek.ai/counselor",
            "pricing": {
                "perCall": {"protocol": "x402", "price_usd": 0.10},
                "subscription": {"protocol": "acp", "checkout_url": "https://api.intuitek.ai/checkouts"},
            },
        },
    ],
    "defaultInputModes": ["text", "application/json"],
    "defaultOutputModes": ["application/json"],
    "supportsAuthenticatedExtendedCard": False,
    "blockers": [
        "DNS for mcp.intuitek.ai not yet configured — flag for K\u00b9",
        "DNS for api.intuitek.ai not yet configured — flag for K\u00b9",
    ],
}


@agent_card_router.get("/.well-known/agent-card.json")
async def get_agent_card():
    """A2A Agent Card — advertises IntuiTek\u00b9 ACE capabilities to the agent network."""
    return JSONResponse(
        content=AGENT_CARD,
        headers={"Cache-Control": "public, max-age=3600"},
    )
