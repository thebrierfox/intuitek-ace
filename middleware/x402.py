"""
x402 Payment Middleware — CDP-backed validator
Applies to all /v1/* routes.
Returns HTTP 402 with payment requirements when no valid payment is present.
Spec: https://x402.org | Facilitator: https://api.cdp.coinbase.com/platform/v2/x402
"""
import base64
import json
import logging
import os
import pathlib
import secrets
import time
from typing import Optional

import httpx
import jwt as pyjwt
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, NoEncryption, PrivateFormat
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

log = logging.getLogger("ace.x402")

# Load canonical pricing from config/pricing.json (one directory up from middleware/)
_PRICING_PATH = pathlib.Path(__file__).parent.parent / "config" / "pricing.json"
with open(_PRICING_PATH) as _f:
    _PRICING = json.load(_f)

CDP_FACILITATOR_URL = os.environ.get(
    "CDP_FACILITATOR_URL", "https://api.cdp.coinbase.com/platform/v2/x402"
)
PAY_TO_ADDRESS = os.environ.get("X402_PAY_TO", _PRICING["x402"]["pay_to"])
USDC_BASE = _PRICING["x402"]["asset"]

# Per-route x402 prices loaded from canonical pricing.json
_ROUTE_PRICES = {
    route: (cfg["amount_micro"], cfg["description"])
    for route, cfg in _PRICING["x402"]["routes"].items()
}
_DEFAULT_PRICE = (
    _PRICING["x402"]["default"]["amount_micro"],
    _PRICING["x402"]["default"]["description"],
)


def _payment_requirements_for_path(path: str) -> dict:
    amount, description = _DEFAULT_PRICE
    for prefix, (amt, desc) in _ROUTE_PRICES.items():
        if path.startswith(prefix):
            amount, description = amt, desc
            break
    return {
        "x402Version": 1,
        "accepts": [
            {
                "scheme": "exact",
                "network": "base",
                "maxAmountRequired": amount,
                "resource": f"https://api.intuitek.ai{path}",
                "description": description,
                "mimeType": "application/json",
                "payTo": PAY_TO_ADDRESS,
                "maxTimeoutSeconds": 300,
                "asset": USDC_BASE,
                "extra": {"name": "USDC", "version": "1"},
            }
        ],
    }


X402_PAYMENT_REQUIREMENTS = _payment_requirements_for_path("/v1/")


def _build_cdp_jwt(key_id: str, key_secret_b64: str, endpoint_url: str) -> str:
    """
    Build a CDP API JWT for authenticating requests to the CDP facilitator.
    CDP API key secret is a 64-byte value: 32-byte Ed25519 seed + 32-byte public key.
    JWT URI claim format: "METHOD hostname/path" — no scheme prefix (verified 2026-04-28).
    """
    raw_key = base64.b64decode(key_secret_b64)
    # First 32 bytes are the Ed25519 private key seed
    private_key = Ed25519PrivateKey.from_private_bytes(raw_key[:32])
    pem = private_key.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption())

    # Strip scheme: "https://api.cdp.coinbase.com/path" → "api.cdp.coinbase.com/path"
    from urllib.parse import urlparse
    parsed = urlparse(endpoint_url)
    uri_no_scheme = f"{parsed.netloc}{parsed.path}"

    now = int(time.time())
    payload = {
        "sub": key_id,
        "iss": "cdp",
        "nbf": now,
        "exp": now + 120,
        "uris": [f"POST {uri_no_scheme}"],
    }
    headers = {"kid": key_id, "nonce": secrets.token_hex(16)}
    return pyjwt.encode(payload, pem, algorithm="EdDSA", headers=headers)


async def _cdp_request(path: str, payment_token: str, requirements: dict) -> Optional[dict]:
    """
    POST to a CDP facilitator endpoint (verify or settle).
    Returns parsed JSON response or None on any failure.
    """
    key_id = os.environ.get("CDP_API_KEY_ID")
    key_secret = os.environ.get("CDP_API_KEY_SECRET")

    if not key_id or not key_secret:
        log.error("x402: CDP_API_KEY_ID or CDP_API_KEY_SECRET not configured")
        return None

    url = f"{CDP_FACILITATOR_URL}/{path}"
    try:
        token = _build_cdp_jwt(key_id, key_secret, url)
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                url,
                json={"paymentHeader": payment_token, "paymentRequirements": requirements},
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            )
        if resp.status_code == 200:
            return resp.json()
        log.warning("x402: CDP %s → HTTP %s: %s", path, resp.status_code, resp.text[:300])
        return None
    except Exception as exc:
        log.error("x402: CDP %s failed: %s", path, exc)
        return None


def _is_v1_route(path: str) -> bool:
    return path.startswith("/v1/") or path == "/v1"


def _extract_payment_token(request: Request) -> Optional[str]:
    return request.headers.get("x-payment")


def _payment_required_response(path: str) -> JSONResponse:
    reqs = _payment_requirements_for_path(path)
    return JSONResponse(
        status_code=402,
        content={
            "error": "Payment required",
            "x402Version": 1,
            "paymentRequirements": reqs,
        },
        headers={"x-payment-requirements": json.dumps(reqs)},
    )


class X402Middleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if not _is_v1_route(request.url.path):
            return await call_next(request)

        path = request.url.path
        reqs = _payment_requirements_for_path(path)

        payment_token = _extract_payment_token(request)
        if not payment_token:
            log.info("x402: no payment header for %s", path)
            return _payment_required_response(path)

        # Step 1: Verify EIP-3009 signature via CDP facilitator
        verify = await _cdp_request("verify", payment_token, reqs)
        if not verify or not verify.get("isValid"):
            reason = (verify or {}).get("invalidReason", "unverified")
            log.info("x402: payment invalid for %s — %s", path, reason)
            return JSONResponse(
                status_code=402,
                content={
                    "error": "Payment invalid",
                    "x402Version": 1,
                    "invalidReason": reason,
                    "paymentRequirements": reqs,
                },
                headers={"x-payment-requirements": json.dumps(reqs)},
            )

        # Step 2: Settle on-chain via CDP (produces cryptographic event that triggers Bazaar indexing)
        settle = await _cdp_request("settle", payment_token, reqs)
        if not settle or not settle.get("success"):
            log.error("x402: CDP settle failed for %s", path)
            return JSONResponse(
                status_code=402,
                content={
                    "error": "Payment settlement failed",
                    "x402Version": 1,
                    "paymentRequirements": reqs,
                },
                headers={"x-payment-requirements": json.dumps(reqs)},
            )

        # Verified and settled — forward request
        log.info(
            "x402: payment settled via CDP for %s, txHash=%s",
            path,
            settle.get("txHash"),
        )
        response = await call_next(request)
        response.headers["x-payment-response"] = json.dumps(
            {
                "status": "settled",
                "network": "base",
                "protocol": "x402",
                "facilitator": "cdp",
                "txHash": settle.get("txHash"),
                "settleReceipt": settle.get("settleReceipt"),
            }
        )
        return response
