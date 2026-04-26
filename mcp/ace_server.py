"""
ACE (Autonomous Commerce Engine) MCP Server
Tools: execute_autonomous_purchase, get_pricing
"""
import json
import os
from typing import Any, Dict

import stripe as _stripe
from mcp.server import MCPServer

_stripe.api_key = os.environ.get("STRIPE_SECRET_KEY", "sk_test_dev")

PAY_TO_ADDRESS = "0xf615BDa54D576e757B51A6128aC8A7C67a1C3d6C"
USDC_BASE_ASSET = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"

_CHECKOUT_PRICE_MAP = {
    "yield-intelligence-pro": {"starter": 2900, "professional": 9900, "enterprise": 49900},
    "ace-autonomous-commerce": {"starter": 3900, "professional": 14900},
    "counselor-ai-strategy": {"starter": 4900, "professional": 19900},
}

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
        tier = args.get("tier", "starter")

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
        per_call_price = per_request["price_usd"] if per_request else 0.05

        if limit and per_call_price and per_call_price > limit:
            return {
                "status": "rejected",
                "reason": f"Per-call price ${per_call_price} exceeds spending limit ${limit}",
                "product_id": product_id,
            }

        if payment_method == "x402":
            usdc_micro = str(int(per_call_price * 1_000_000))
            return {
                "status": "payment_required",
                "payment_method": "x402",
                "product_id": product_id,
                "per_call_price_usd": per_call_price,
                "payment_requirements": {
                    "x402Version": 1,
                    "accepts": [
                        {
                            "scheme": "exact",
                            "network": "base",
                            "maxAmountRequired": usdc_micro,
                            "resource": "https://api.intuitek.ai/v1/",
                            "description": f"IntuiTek¹ {product['name']} — per-call",
                            "mimeType": "application/json",
                            "payTo": PAY_TO_ADDRESS,
                            "maxTimeoutSeconds": 300,
                            "asset": USDC_BASE_ASSET,
                            "extra": {"name": "USDC", "version": "1"},
                        }
                    ],
                },
                "instructions": (
                    "Send USDC payment proof on Base in the x-payment header, "
                    "then re-invoke this tool to complete the purchase."
                ),
            }

        # ACP / Stripe subscription checkout
        tier_prices = _CHECKOUT_PRICE_MAP.get(product_id, {})
        amount_cents = tier_prices.get(tier, tier_prices.get("starter", 3900))
        monthly_usd = amount_cents / 100

        if limit and monthly_usd > limit:
            return {
                "status": "rejected",
                "reason": f"Subscription price ${monthly_usd}/mo exceeds spending limit ${limit}",
                "product_id": product_id,
                "tier": tier,
            }

        try:
            session = _stripe.checkout.Session.create(
                mode="subscription",
                line_items=[
                    {
                        "price_data": {
                            "currency": "usd",
                            "unit_amount": amount_cents,
                            "recurring": {"interval": "month"},
                            "product_data": {
                                "name": f"IntuiTek¹ {product['name']} ({tier})",
                            },
                        },
                        "quantity": 1,
                    }
                ],
                success_url="https://intuitek.ai/success",
                cancel_url="https://intuitek.ai/",
                metadata={
                    "product_id": product_id,
                    "tier": tier,
                    "payment_method": payment_method,
                },
            )
            return {
                "status": "checkout_created",
                "product_id": product_id,
                "tier": tier,
                "payment_method": payment_method,
                "monthly_price_usd": monthly_usd,
                "checkout_url": session.url,
                "checkout_id": session.id,
                "instructions": (
                    "Complete payment at checkout_url to activate subscription. "
                    "License delivered by email within 5 minutes of payment."
                ),
            }
        except Exception as exc:
            return {
                "status": "error",
                "error": str(exc),
                "product_id": product_id,
                "contact": "agent@intuitek.ai",
                "fallback": "https://api.intuitek.ai/checkouts",
            }

    def _get_pricing(self, args: Dict) -> Dict:
        product_id = args.get("product_id")
        if product_id:
            products = [p for p in PRICING_DATA["products"] if p["id"] == product_id]
            return {**PRICING_DATA, "products": products}
        return PRICING_DATA


ace_mcp_server = AceMCPServer()
ace_mcp_app = ace_mcp_server.app
