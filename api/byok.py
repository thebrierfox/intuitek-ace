"""
IntuiTek¹ — BYOK Product Delivery
Downloads Python tools after one-time Stripe payment ($29).

Flow:
  GET  /byok/                           → store index (all products)
  GET  /byok/{product}                  → product page with email checkout form
  POST /byok/{product}/checkout         → Stripe Checkout Session URL
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

import httpx
import stripe
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel, EmailStr

log = logging.getLogger("ace.byok")

router = APIRouter(prefix="/byok", tags=["byok"])

_DB_PATH    = os.environ.get("ACE_DB_PATH", "/data/ace.db")
_BASE_URL   = os.environ.get("ACE_BASE_URL", "https://ace-license-server-production.up.railway.app")
_RESEND_KEY = os.environ.get("RESEND_API_KEY", "")

_PACKAGES_DIR = Path(__file__).parent.parent / "packages"

_PRODUCTS: dict[str, dict] = {
    "moatmri": {
        "name": "MoatMRI™",
        "tagline": "Intelligence-Pressure Constraint Engine",
        "description": (
            "Pressure-test any business against 10 strategic vectors. "
            "Outputs a Pressure Map, AI Front-Door Takeover Storyboard, "
            "and a 90-Day Counterstrike Plan — all generated locally with your own Anthropic key."
        ),
        "features": [
            "10-vector AI pressure analysis",
            "Pressure Map with composite score",
            "AI Front-Door Takeover Storyboard",
            "90-Day Counterstrike Plan",
            "Runs locally — your key, your data, zero vendor lock-in",
            "Python 3.9+ · 3 files · no external dependencies beyond anthropic SDK",
        ],
        "price_env": "BYOK_PRICE_MOATMRI",
        "zip_name": "moatmri.zip",
        "price": "$29",
    },
    "doc2math": {
        "name": "DOC2MATH™",
        "tagline": "Document-to-Mathematics Problem Genesis Engine",
        "description": (
            "Convert technical documents into formal mathematical problem structures. "
            "Extracts variables, operators, constraints, objectives, and uncertainty into "
            "Machine-Parseable Structure (MPS) JSON using the Zero-Inference Protocol — "
            "closed-world, grounded, inference-tagged."
        ),
        "features": [
            "Stage 1 MPS JSON pipeline (variables → constraints → objectives)",
            "Zero-Inference Protocol: MISSING-marked, grounded, no hallucination",
            "Validated against OptNet and academic optimization papers",
            "Uncertainty and inference tracking built in",
            "Runs locally — your key, your data, zero vendor lock-in",
            "Python 3.9+ · 3 files · no external dependencies beyond anthropic SDK",
        ],
        "price_env": "BYOK_PRICE_DOC2MATH",
        "zip_name": "doc2math.zip",
        "price": "$29",
    },
}

_CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif;
  background: #0a0a0a;
  color: #e0e0e0;
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 2rem 1.5rem;
}
.card { max-width: 520px; width: 100%; }
.brand { font-size: 0.72rem; letter-spacing: 0.12em; text-transform: uppercase; color: #555; margin-bottom: 1rem; }
.brand a { color: #555; text-decoration: none; }
.brand a:hover { color: #888; }
h1 { font-size: 1.9rem; font-weight: 800; margin-bottom: 0.25rem; letter-spacing: -0.02em; }
.tagline { font-size: 0.9rem; color: #777; margin-bottom: 1rem; }
.description { color: #aaa; line-height: 1.6; margin-bottom: 1.5rem; font-size: 0.95rem; }
.features { list-style: none; margin-bottom: 1.75rem; }
.features li { padding: 0.3rem 0; font-size: 0.88rem; color: #bbb; }
.features li::before { content: "→ "; color: #4ade80; font-weight: 700; }
.byok-badge {
  background: #0d1a0d;
  border: 1px solid #1a3a1a;
  border-radius: 0.5rem;
  padding: 0.85rem 1rem;
  margin-bottom: 1.75rem;
  font-size: 0.82rem;
  color: #7ab87a;
  line-height: 1.5;
}
.byok-badge strong { color: #a8e6a3; }
label { display: block; font-size: 0.8rem; color: #666; margin-bottom: 0.4rem; letter-spacing: 0.04em; text-transform: uppercase; }
input[type=email] {
  width: 100%;
  background: #111;
  border: 1px solid #2a2a2a;
  border-radius: 0.45rem;
  color: #e0e0e0;
  font-size: 1rem;
  padding: 0.7rem 0.9rem;
  outline: none;
  transition: border-color 0.15s;
}
input[type=email]:focus { border-color: #4ade80; }
input[type=email]::placeholder { color: #444; }
.buy-btn {
  display: block;
  width: 100%;
  margin-top: 0.75rem;
  background: #4ade80;
  color: #000;
  border: none;
  border-radius: 0.45rem;
  font-size: 1rem;
  font-weight: 800;
  padding: 0.8rem;
  cursor: pointer;
  transition: opacity 0.15s, transform 0.1s;
  letter-spacing: -0.01em;
}
.buy-btn:hover { opacity: 0.88; transform: translateY(-1px); }
.buy-btn:active { transform: translateY(0); }
.buy-btn:disabled { opacity: 0.35; cursor: not-allowed; transform: none; }
.secure-note { font-size: 0.78rem; color: #444; margin-top: 0.65rem; text-align: center; }
.error-msg { color: #f87171; font-size: 0.83rem; margin-top: 0.5rem; display: none; }
.footer { margin-top: 2.5rem; font-size: 0.72rem; color: #333; text-align: center; }
.footer a { color: #444; text-decoration: none; }
.footer a:hover { color: #666; }
"""

_CHECKOUT_JS = """
const form  = document.getElementById('cf');
const btn   = document.getElementById('buy-btn');
const errEl = document.getElementById('err');
form.addEventListener('submit', async (e) => {
  e.preventDefault();
  btn.disabled   = true;
  btn.textContent = 'Connecting to Stripe…';
  errEl.style.display = 'none';
  const email = document.getElementById('email').value.trim();
  try {
    const res  = await fetch(window.CHECKOUT_URL, {
      method:  'POST',
      headers: {'Content-Type': 'application/json'},
      body:    JSON.stringify({email}),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Checkout failed — please try again.');
    window.location.href = data.checkout_url;
  } catch (ex) {
    errEl.textContent    = ex.message;
    errEl.style.display  = 'block';
    btn.disabled         = false;
    btn.textContent      = ORIGINAL_BTN;
  }
});
"""


_COMING_SOON_CSS = _CSS + """
.coming-soon-box {
  background: #0d1111;
  border: 1px solid #1a2a2a;
  border-radius: 0.5rem;
  padding: 1.25rem 1.4rem;
  margin-top: 1.5rem;
  font-size: 0.9rem;
  color: #7aabb8;
  line-height: 1.6;
}
.coming-soon-box strong { color: #a3d4e0; }
"""


def _product_page(product_id: str, meta: dict, activated: bool = True) -> str:
    features_li = "\n".join(f"<li>{f}</li>" for f in meta["features"])
    btn_label = f"Buy {meta['name']} for {meta['price']} →"

    if not activated:
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{meta['name']} — IntuiTek¹</title>
  <style>{_COMING_SOON_CSS}</style>
</head>
<body>
<div class="card">
  <p class="brand"><a href="/byok/">IntuiTek¹ Store</a> / BYOK Download</p>
  <h1>{meta['name']}</h1>
  <p class="tagline">{meta['tagline']}</p>
  <p class="description">{meta['description']}</p>
  <ul class="features">{features_li}</ul>
  <div class="coming-soon-box">
    <strong>Coming soon.</strong> This product is in final activation. Check back in 24–48 hours, or email
    <a href="mailto:kyle@intuitek.ai" style="color:#7aabb8;">kyle@intuitek.ai</a> to be notified when it's live.
  </div>
  <p class="footer" style="margin-top:2rem;">~K¹ (William Kyle Million) / <a href="https://intuitek.ai">IntuiTek¹</a> · <a href="/byok/">View all tools</a></p>
</div>
</body>
</html>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{meta['name']} — IntuiTek¹</title>
  <meta name="description" content="{meta['tagline']} · {meta['price']} · BYOK Python tool from IntuiTek¹">
  <style>{_CSS}</style>
</head>
<body>
<div class="card">
  <p class="brand"><a href="/byok/">IntuiTek¹ Store</a> / BYOK Download</p>
  <h1>{meta['name']}</h1>
  <p class="tagline">{meta['tagline']}</p>
  <p class="description">{meta['description']}</p>
  <ul class="features">{features_li}</ul>
  <div class="byok-badge">
    <strong>Bring Your Own Key.</strong> This tool runs on your machine with your own Anthropic API key.
    IntuiTek¹ never stores your key or processes your data. One-time purchase — no subscription, no lock-in.
  </div>
  <form id="cf" novalidate>
    <label for="email">Email address</label>
    <input type="email" id="email" name="email" placeholder="you@example.com" required autocomplete="email">
    <div class="error-msg" id="err"></div>
    <button type="submit" class="buy-btn" id="buy-btn">{btn_label}</button>
    <p class="secure-note">Secure checkout via Stripe · Instant ZIP download after payment</p>
  </form>
  <p class="footer">~K¹ (William Kyle Million) / <a href="https://intuitek.ai">IntuiTek¹</a> · <a href="/byok/">View all tools</a></p>
</div>
<script>
const ORIGINAL_BTN    = {repr(btn_label)};
window.CHECKOUT_URL   = '/byok/{product_id}/checkout';
{_CHECKOUT_JS}
</script>
</body>
</html>"""


def _store_index() -> str:
    cards = ""
    for pid, meta in _PRODUCTS.items():
        cards += f"""
  <div class="product-card">
    <div class="product-name">{meta['name']}</div>
    <div class="product-tagline">{meta['tagline']}</div>
    <p class="product-desc">{meta['description'][:160]}…</p>
    <a href="/byok/{pid}" class="product-link">Buy for {meta['price']} →</a>
  </div>"""

    store_css = _CSS + """
.store-header { margin-bottom: 2.5rem; }
.store-header h1 { font-size: 1.6rem; font-weight: 800; margin-bottom: 0.5rem; }
.store-header p { color: #777; font-size: 0.9rem; line-height: 1.5; }
.products { display: flex; flex-direction: column; gap: 1.25rem; }
.product-card {
  background: #111;
  border: 1px solid #222;
  border-radius: 0.6rem;
  padding: 1.25rem 1.4rem;
  transition: border-color 0.15s;
}
.product-card:hover { border-color: #3a3a3a; }
.product-name { font-weight: 800; font-size: 1.05rem; margin-bottom: 0.2rem; }
.product-tagline { font-size: 0.8rem; color: #666; text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 0.6rem; }
.product-desc { font-size: 0.875rem; color: #999; line-height: 1.5; margin-bottom: 1rem; }
.product-link {
  display: inline-block;
  background: #4ade80;
  color: #000;
  font-weight: 800;
  font-size: 0.85rem;
  padding: 0.45rem 0.9rem;
  border-radius: 0.35rem;
  text-decoration: none;
  transition: opacity 0.15s;
}
.product-link:hover { opacity: 0.85; }
"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>IntuiTek¹ BYOK Store</title>
  <meta name="description" content="BYOK Python tools from IntuiTek¹ — runs on your machine with your own Anthropic key. One-time $29 purchase.">
  <style>{store_css}</style>
</head>
<body>
<div class="card">
  <p class="brand"><a href="https://intuitek.ai">intuitek.ai</a></p>
  <div class="store-header">
    <h1>IntuiTek¹ BYOK Tools</h1>
    <p>Python tools that run on your machine with your own Anthropic API key. One-time purchase — no subscription, no vendor lock-in, no data leaves your environment.</p>
  </div>
  <div class="products">{cards}
  </div>
  <p class="footer" style="margin-top:2rem;">~K¹ (William Kyle Million) / <a href="https://intuitek.ai">IntuiTek¹</a></p>
</div>
</body>
</html>"""


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


# ── EMAIL DELIVERY ───────────────────────────────────────────

def _send_download_email(email: str, product_id: str, product_name: str, download_url: str) -> None:
    """Send permanent download link to customer via Resend. Non-blocking: caller catches exceptions."""
    if not _RESEND_KEY:
        log.warning("RESEND_API_KEY not set — skipping download email for %s", email)
        return

    script_name = f"{product_id}.py"
    body_text = (
        f"Thank you for purchasing {product_name}.\n\n"
        f"Your permanent download link:\n{download_url}\n\n"
        f"This link is permanent — bookmark it or save this email to re-download any time.\n\n"
        f"Getting started:\n"
        f"  1. Unzip the downloaded file\n"
        f"  2. Copy .env.example to .env and add your Anthropic API key (ANTHROPIC_API_KEY)\n"
        f"  3. pip install -r requirements.txt\n"
        f"  4. python {script_name}\n\n"
        f"Questions: kyle@intuitek.ai\n\n"
        f"— IntuiTek¹"
    )
    body_html = (
        f"<p>Thank you for purchasing <strong>{product_name}</strong>.</p>"
        f"<p><strong>Your permanent download link:</strong><br>"
        f'<a href="{download_url}">{download_url}</a></p>'
        f"<p>This link is permanent — bookmark it or save this email to re-download any time.</p>"
        f"<h3>Getting started</h3><ol>"
        f"<li>Unzip the downloaded file</li>"
        f"<li>Copy <code>.env.example</code> to <code>.env</code> and add your Anthropic API key (<code>ANTHROPIC_API_KEY</code>)</li>"
        f"<li><code>pip install -r requirements.txt</code></li>"
        f"<li><code>python {script_name}</code></li>"
        f"</ol>"
        f'<p>Questions: <a href="mailto:kyle@intuitek.ai">kyle@intuitek.ai</a></p>'
        f"<p>— IntuiTek¹</p>"
    )

    resp = httpx.post(
        "https://api.resend.com/emails",
        headers={"Authorization": f"Bearer {_RESEND_KEY}", "Content-Type": "application/json"},
        json={
            "from": "IntuiTek¹ ACE <ace@intuitek.ai>",
            "to": [email],
            "subject": f"Your {product_name} download — IntuiTek¹",
            "text": body_text,
            "html": body_html,
        },
        timeout=10,
    )
    if resp.status_code not in (200, 201):
        raise RuntimeError(f"Resend error {resp.status_code}: {resp.text}")
    log.info("Download email sent to %s for %s", email, product_id)


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

@router.get("/", response_class=HTMLResponse)
async def byok_store():
    """BYOK store index — lists all available products."""
    return HTMLResponse(_store_index())


@router.get("/{product}", response_class=HTMLResponse)
async def byok_product_page(product: str):
    """Product page with email checkout form (or coming-soon if price not yet set)."""
    meta = _PRODUCTS.get(product)
    if not meta:
        raise HTTPException(status_code=404, detail=f"Unknown product: {product}")
    price_id = os.environ.get(meta["price_env"], "")
    activated = bool(price_id)
    return HTMLResponse(_product_page(product, meta, activated=activated))


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
            cancel_url=f"{_BASE_URL}/byok/{product}",
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

        download_url = f"{_BASE_URL}/byok/{product}/download/{token}"
        try:
            _send_download_email(row["email"], product, meta["name"], download_url)
        except Exception as exc:
            log.error("Download email failed for %s / %s: %s", product, row["email"], exc)

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
