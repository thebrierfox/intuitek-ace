"""
IntuiTek¹ — BYOK Product Delivery
Downloads Python tools after one-time Stripe payment ($29).

Flow:
  POST /byok/{product}/checkout       → Stripe Checkout Session URL
  GET  /byok/{product}/download/{token} → verify payment, stream ZIP

Products:
  moatmri  — Intelligence-Pressure Constraint Engine (env: BYOK_PRICE_MOATMRI)
  doc2math — Document-to-Mathematics Problem Genesis Engine (env: BYOK_PRICE_DOC2MATH)

Activation: Set env vars BYOK_PRICE_MOATMRI and BYOK_PRICE_DOC2MATH to live Stripe price IDs.
Until set, checkout endpoints return 503 ("product not yet activated").
"""

import io
import logging
import os
import sqlite3
import time
import uuid
import zipfile
from pathlib import Path

import stripe
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, EmailStr

log = logging.getLogger("ace.byok")

router = APIRouter(prefix="/byok", tags=["byok"])

_DB_PATH   = os.environ.get("ACE_DB_PATH", "/data/ace.db")
_BASE_URL  = os.environ.get("ACE_BASE_URL", "https://ace-license-server-production.up.railway.app")
_RESEND_KEY = os.environ.get("RESEND_API_KEY", "")

_PACKAGES_DIR = Path(__file__).parent.parent / "packages"

_PRODUCTS: dict[str, dict] = {
    "moatmri": {
        "name": "MoatMRI™",
        "description": "Intelligence-Pressure Constraint Engine",
        "price_env": "BYOK_PRICE_MOATMRI",
        "zip_name": "moatmri.zip",
    },
    "doc2math": {
        "name": "DOC2MATH™",
        "description": "Document-to-Mathematics Problem Genesis Engine",
        "price_env": "BYOK_PRICE_DOC2MATH",
        "zip_name": "doc2math.zip",
    },
}


# ── DATABASE ─────────────────────────────────────────────────

def _get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(_DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def _ensure_table():
    conn = _get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS byok_sessions (
            token              TEXT PRIMARY KEY,
            email              TEXT NOT NULL,
            product            TEXT NOT NULL,
            stripe_session_id  TEXT,
            status             TEXT DEFAULT 'pending_payment',
            created_at         INTEGER NOT NULL,
            downloaded_at      INTEGER
        )
    """)
    conn.commit()
    conn.close()


# ── ZIP BUILDER ──────────────────────────────────────────────

def _build_zip(product: str) -> bytes:
    """Build in-memory ZIP from packages/{product}/ directory."""
    pkg_dir = _PACKAGES_DIR / product
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for fpath in sorted(pkg_dir.rglob("*")):
            if fpath.is_file() and not fpath.name.endswith(".pyc"):
                arcname = f"{product}/{fpath.relative_to(pkg_dir)}"
                zf.write(fpath, arcname)
    return buf.getvalue()


# ── PAYMENT VERIFICATION ─────────────────────────────────────

def _verify_payment(session_id: str) -> bool:
    try:
        session = stripe.checkout.Session.retrieve(session_id)
        return session.payment_status in ("paid", "no_payment_required")
    except stripe.error.StripeError as exc:
        log.error("Stripe session lookup failed: %s", exc)
        return False


# ── ROUTES ───────────────────────────────────────────────────

class CheckoutRequest(BaseModel):
    email: EmailStr


@router.post("/{product}/checkout")
async def byok_checkout(product: str, body: CheckoutRequest):
    """Create Stripe Checkout Session for a BYOK product ($29 one-time)."""
    meta = _PRODUCTS.get(product)
    if not meta:
        raise HTTPException(status_code=404, detail=f"Unknown product: {product}")

    price_id = os.environ.get(meta["price_env"], "")
    if not price_id:
        raise HTTPException(
            status_code=503,
            detail=f"{meta['name']} is not yet available for purchase. Check back soon.",
        )

    _ensure_table()
    token = str(uuid.uuid4())

    try:
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            mode="payment",
            line_items=[{"price": price_id, "quantity": 1}],
            customer_email=body.email,
            success_url=f"{_BASE_URL}/byok/{product}/download/{token}",
            cancel_url=f"{_BASE_URL}/",
            metadata={"byok_token": token, "product": product},
        )
    except stripe.error.StripeError as exc:
        log.error("Stripe checkout creation failed for %s: %s", product, exc)
        raise HTTPException(status_code=502, detail="Payment session creation failed")

    conn = _get_db()
    conn.execute(
        """INSERT INTO byok_sessions (token, email, product, stripe_session_id, status, created_at)
           VALUES (?, ?, ?, ?, 'pending_payment', ?)""",
        (token, body.email, product, session.id, int(time.time())),
    )
    conn.commit()
    conn.close()

    return {"checkout_url": session.url}


@router.get("/{product}/download/{token}")
async def byok_download(product: str, token: str):
    """Verify Stripe payment and stream product ZIP."""
    meta = _PRODUCTS.get(product)
    if not meta:
        raise HTTPException(status_code=404, detail=f"Unknown product: {product}")

    _ensure_table()
    conn = _get_db()
    row = conn.execute(
        "SELECT token, email, product, stripe_session_id, status FROM byok_sessions WHERE token = ? AND product = ?",
        (token, product),
    ).fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="Session not found")

    if row["status"] == "pending_payment":
        if not _verify_payment(row["stripe_session_id"]):
            raise HTTPException(
                status_code=402,
                detail="Payment not yet confirmed — wait 10 seconds and retry.",
            )
        conn2 = _get_db()
        conn2.execute(
            "UPDATE byok_sessions SET status='paid' WHERE token=?",
            (token,),
        )
        conn2.commit()
        conn2.close()

    pkg_dir = _PACKAGES_DIR / product
    if not pkg_dir.is_dir():
        log.error("Package directory missing for product: %s", product)
        raise HTTPException(status_code=500, detail="Package not found — contact kyle@intuitek.ai")

    zip_bytes = _build_zip(product)

    conn3 = _get_db()
    conn3.execute(
        "UPDATE byok_sessions SET downloaded_at=? WHERE token=?",
        (int(time.time()), token),
    )
    conn3.commit()
    conn3.close()

    log.info("BYOK download: %s → %s (%d bytes)", product, row["email"], len(zip_bytes))

    return StreamingResponse(
        io.BytesIO(zip_bytes),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{meta["zip_name"]}"'},
    )
