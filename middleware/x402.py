"""
x402 Payment Middleware
Applies to all /v1/* routes.
Returns HTTP 402 with payment requirements when no valid payment token present.
Spec: https://x402.org
"""
import json
import logging
from typing import Optional

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

log = logging.getLogger("ace.x402")

X402_PAYMENT_REQUIREMENTS = {
    "x402Version": 1,
    "accepts": [
        {
            "scheme": "exact",
            "network": "base",
            "maxAmountRequired": "5000000",
            "resource": "https://api.intuitek.ai/v1/",
            "description": "IntuiTek\u00b9 API access",
            "mimeType": "application/json",
            "payTo": "WALLET_ADDRESS_PLACEHOLDER",
            "maxTimeoutSeconds": 300,
            "asset": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
            "extra": {"name": "USDC", "version": "1"},
        }
    ],
}


def _is_v1_route(path: str) -> bool:
    return path.startswith("/v1/") or path == "/v1"


def _extract_payment_token(request: Request) -> Optional[str]:
    return request.headers.get("x-payment")


def _validate_payment_token(token: str) -> bool:
    """
    Stub validator — in production, verify the x402 payment proof on-chain via Base.
    For MVP: accept any non-empty token (dev mode).
    """
    return bool(token and len(token) > 10)


class X402Middleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if not _is_v1_route(request.url.path):
            return await call_next(request)

        payment_token = _extract_payment_token(request)

        if not payment_token or not _validate_payment_token(payment_token):
            log.info("x402: payment required for %s", request.url.path)
            return JSONResponse(
                status_code=402,
                content={
                    "error": "Payment required",
                    "x402Version": 1,
                    "paymentRequirements": X402_PAYMENT_REQUIREMENTS,
                },
                headers={
                    "x-payment-requirements": json.dumps(X402_PAYMENT_REQUIREMENTS),
                    "Content-Type": "application/json",
                },
            )

        # Valid payment token — process request
        log.info("x402: payment token accepted for %s", request.url.path)
        response = await call_next(request)
        response.headers["x-payment-response"] = json.dumps(
            {"status": "accepted", "network": "base", "protocol": "x402"}
        )
        return response
