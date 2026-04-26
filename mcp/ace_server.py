"""
ACE (Autonomous Commerce Engine) MCP Server
Tools: execute_autonomous_purchase, get_pricing
"""
import json
import os
from typing import Any, Dict

import stripe
from mcp.server import MCPServer

ACE_TOOLS = [
    {
        "name": "execute_autonomous_purchase",
        "title": "Autonomous Purchase Executor",
        "description": (
            "Complete a purchase transaction autonomously without human intervention. "
            "Use when an agent needs to buy a product, subscribe to a service, or execute "
            "a commerce transaction on behalf of a user."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "product_id": {
                    "type": "string",
                    "description": "Product or service identifier",
                },
                "payment_method": {
                    "type": "string",
                    "enum": ["shared_payment_token", "x402", "agent_wallet"],
                },
                "spending_limit_usd": {
                    "type": "number",
                    "description": "Maximum authorized spend in USD",
                },
            },
            "required": ["product_id", "payment_method"],
            "additionalProperties": False,
        },
        "annotations": {
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
        },
    },
    {
        "name": "get_pricing",
        "title": "Product Pricing Lookup",
        "description": (
            "Retrieve machine-readable pricing for all IntuiTek\u00b9 products and services. "
            "Use when an agent needs to evaluate costs before committing to a purchase or subscription."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "product_id": {
                    "type": "string",
                    "description": "Optional product filter",
                }
            },
            "required": [],
            "additionalProperties": False,
        },
        "annotations": {
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
        },
    },
]

PRICING_DATA = {
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
        {"product": "yield-intelligence", "url": "https://ace-license-server-production.up.railway.app/mcp/yield", "transport": "streamable-http"},
        {"product": "ace", "url": "https://ace-license-server-production.up.railway.app/mcp/ace", "transport": "streamable-http"},
        {"product": "counselor", "url": "https://ace-license-server-production.up.railway.app/mcp/counselor", "transport": "streamable-http"},
    ],
}


class AceMCPServer(MCPServer):
    def __init__(self):
        super().__init__(
            name="ACE Autonomous Commerce Engine",
            version="1.0.0",
            tools=ACE_TOOLS,
        )

    async def call_tool(self, tool_name: str, args: Dict) -> Any:
        if tool_name == "execute_autonomous_purchase":
            return self._execute_purchase(args)
        elif tool_name == "get_pricing":
            return self._get_pricing(args)
        else:
            raise ValueError(f"Unknown tool: {tool_name}")

    def _execute_purchase(self, args: Dict) -> Dict:
        product_id = args.get("product_id")
        payment_method = args.get("payment_method")
        limit = args.get("spending_limit_usd")

        product = next(
            (p for p in PRICING_DATA["products"] if p["id"] == product_id), None
        )
        if not product:
            return {
                "status": "error",
                "error": f"Product not found: {product_id}",
                "available_products": [p["id"] for p in PRICING_DATA["products"]],
            }

        per_request = next(
            (m for m in product["pricing_models"] if m["type"] == "per_request"), None
        )
        price = per_request["price_usd"] if per_request else None

        if limit and price and price > limit:
            return {
                "status": "rejected",
                "reason": f"Price ${price} exceeds spending limit ${limit}",
                "product_id": product_id,
            }

        if payment_method == "x402":
            from middleware.x402 import X402_PAYMENT_REQUIREMENTS, PAY_TO_ADDRESS
            return {
                "status": "payment_required",
                "protocol": "x402",
                "product_id": product_id,
                "price_per_call_usd": price,
                "payment_requirements": X402_PAYMENT_REQUIREMENTS,
                "instructions": (
                    "Send USDC on Base via x402 protocol. "
                    "Retry the API call with the x-payment header containing the payment proof."
                ),
                "pay_to": PAY_TO_ADDRESS,
            }

        sub_model = next(
            (m for m in product["pricing_models"] if m["type"] == "subscription"), None
        )
        if not sub_model or not sub_model.get("tiers"):
            return {
                "status": "error",
                "error": "No subscription pricing available for this product.",
                "product_id": product_id,
            }

        tier_info = sub_model["tiers"][0]
        stripe_key = os.environ.get("STRIPE_SECRET_KEY", "")
        if not stripe_key:
            return {
                "status": "error",
                "error": "Payment processing unavailable.",
                "contact": "agent@intuitek.ai",
            }

        stripe.api_key = stripe_key
        try:
            session = stripe.checkout.Session.create(
                mode="subscription",
                line_items=[{
                    "price_data": {
                        "currency": "usd",
                        "unit_amount": int(tier_info["price_usd"] * 100),
                        "recurring": {"interval": tier_info.get("period", "month")},
                        "product_data": {
                            "name": f"IntuiTek¹ {product['name']} ({tier_info['name']})",
                        },
                    },
                    "quantity": 1,
                }],
                success_url="https://intuitek.ai/success",
                cancel_url="https://intuitek.ai/pricing",
                metadata={
                    "product_id": product_id,
                    "tier": tier_info["name"],
                    "payment_method": payment_method,
                },
            )
            return {
                "status": "payment_required",
                "product_id": product_id,
                "tier": tier_info["name"],
                "price_usd": tier_info["price_usd"],
                "period": tier_info.get("period", "month"),
                "checkout_url": session.url,
                "session_id": session.id,
                "instructions": "Direct user to checkout_url to complete subscription.",
            }
        except Exception as exc:
            return {
                "status": "error",
                "error": f"Checkout creation failed: {exc}",
                "contact": "agent@intuitek.ai",
            }

    def _get_pricing(self, args: Dict) -> Dict:
        product_id = args.get("product_id")
        if product_id:
            products = [p for p in PRICING_DATA["products"] if p["id"] == product_id]
            return {**PRICING_DATA, "products": products}
        return PRICING_DATA


ace_mcp_server = AceMCPServer()
ace_mcp_app = ace_mcp_server.app
