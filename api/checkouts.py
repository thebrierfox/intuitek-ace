"""
ACP Checkout endpoints (Stripe-backed stub for MVP).
POST   /checkouts              — Create checkout session
PATCH  /checkouts/{id}         — Update checkout
POST   /checkouts/{id}/complete — Complete checkout
DELETE /checkouts/{id}         — Cancel checkout
"""
import os
import re
import uuid
from typing import Optional

import stripe
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

_ALLOWED_REDIRECT = re.compile(r"^https://intuitek\.ai/")


def _validate_redirect_url(url: str, field: str) -> str:
    if not _ALLOWED_REDIRECT.match(url):
        raise HTTPException(
            status_code=400,
            detail=f"{field} must start with https://intuitek.ai/",
        )
    return url

checkouts_router = APIRouter()

stripe.api_key = os.environ.get("STRIPE_SECRET_KEY", "sk_test_dev")

PRODUCT_PRICE_MAP = {
    "yield-intelligence-pro-starter": {"amount": 2900, "currency": "usd"},
    "yield-intelligence-pro-professional": {"amount": 9900, "currency": "usd"},
    "yield-intelligence-pro-enterprise": {"amount": 49900, "currency": "usd"},
    "ace-autonomous-commerce-starter": {"amount": 3900, "currency": "usd"},
    "ace-autonomous-commerce-professional": {"amount": 14900, "currency": "usd"},
    "counselor-ai-strategy-starter": {"amount": 4900, "currency": "usd"},
    "counselor-ai-strategy-professional": {"amount": 19900, "currency": "usd"},
}


class CreateCheckoutRequest(BaseModel):
    product_id: str
    tier: str = "starter"
    success_url: str = "https://intuitek.ai/success"
    cancel_url: str = "https://intuitek.ai/cancel"
    customer_email: Optional[str] = None
    metadata: Optional[dict] = None


class UpdateCheckoutRequest(BaseModel):
    customer_email: Optional[str] = None
    metadata: Optional[dict] = None


@checkouts_router.post("")
@checkouts_router.post("/")
async def create_checkout(body: CreateCheckoutRequest):
    """Create a Stripe Checkout Session for an IntuiTek\u00b9 subscription."""
    key = f"{body.product_id}-{body.tier}"
    price_info = PRODUCT_PRICE_MAP.get(key)

    if not price_info:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown product/tier combination: {key}. "
                   f"Available: {list(PRODUCT_PRICE_MAP.keys())}",
        )

    success_url = _validate_redirect_url(body.success_url, "success_url")
    cancel_url = _validate_redirect_url(body.cancel_url, "cancel_url")

    try:
        session_params = {
            "mode": "subscription",
            "line_items": [
                {
                    "price_data": {
                        "currency": price_info["currency"],
                        "unit_amount": price_info["amount"],
                        "recurring": {"interval": "month"},
                        "product_data": {
                            "name": f"IntuiTek\u00b9 {body.product_id} ({body.tier})",
                        },
                    },
                    "quantity": 1,
                }
            ],
            "success_url": success_url,
            "cancel_url": cancel_url,
            "metadata": body.metadata or {},
        }
        if body.customer_email:
            session_params["customer_email"] = body.customer_email

        session = stripe.checkout.Session.create(**session_params)
        return {
            "id": session.id,
            "url": session.url,
            "status": session.status,
            "product_id": body.product_id,
            "tier": body.tier,
            "amount_cents": price_info["amount"],
            "currency": price_info["currency"],
        }
    except stripe.error.StripeError as exc:
        raise HTTPException(status_code=502, detail=f"Stripe error: {exc.user_message or str(exc)}")


@checkouts_router.patch("/{checkout_id}")
async def update_checkout(checkout_id: str, body: UpdateCheckoutRequest):
    """Update metadata on an existing Stripe Checkout Session (stub — Stripe Sessions are immutable post-creation)."""
    return {
        "id": checkout_id,
        "status": "stub",
        "message": "Checkout session updates are applied at completion. Full ACP v2.",
        "updates": body.model_dump(exclude_none=True),
    }


@checkouts_router.post("/{checkout_id}/complete")
async def complete_checkout(checkout_id: str):
    """Verify and complete a Stripe Checkout Session."""
    try:
        session = stripe.checkout.Session.retrieve(checkout_id)
        return {
            "id": session.id,
            "status": session.status,
            "payment_status": session.payment_status,
            "customer": session.customer,
            "subscription": session.subscription,
        }
    except stripe.error.StripeError as exc:
        raise HTTPException(status_code=502, detail=f"Stripe error: {exc.user_message or str(exc)}")


@checkouts_router.delete("/{checkout_id}")
async def cancel_checkout(checkout_id: str):
    """Cancel/expire a Stripe Checkout Session."""
    try:
        session = stripe.checkout.Session.expire(checkout_id)
        return {"id": session.id, "status": session.status, "cancelled": True}
    except stripe.error.StripeError as exc:
        raise HTTPException(status_code=502, detail=f"Stripe error: {exc.user_message or str(exc)}")
