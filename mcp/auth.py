"""
MCP Auth — API key + x402 token validation.
"""
import os
from typing import Optional

from fastapi import Header, HTTPException, Request

ACE_API_KEYS: set = set(filter(None, os.environ.get("ACE_API_KEYS", "").split(",")))


def _is_valid_api_key(key: str) -> bool:
    if not ACE_API_KEYS:
        return True  # open in dev when no keys configured
    return key in ACE_API_KEYS


async def require_auth(
    request: Request,
    authorization: Optional[str] = Header(None),
    x_payment: Optional[str] = Header(None),
) -> str:
    """
    Validates either:
    - Bearer API key (Authorization: Bearer <key>)
    - x-payment header (x402 token)
    Returns the validated credential or 'open' when no auth configured.
    """
    if x_payment:
        return "x402"

    if authorization:
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() == "bearer" and _is_valid_api_key(token):
            return token
        raise HTTPException(status_code=401, detail="Invalid API key")

    if not ACE_API_KEYS:
        return "open"

    raise HTTPException(
        status_code=401,
        detail="Authentication required. Provide Authorization: Bearer <api_key> or x-payment header.",
    )
