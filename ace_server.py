"""
IntuiTek¹ Agent Commerce Engine — ACE Server v1.0.0
Operator: ~K¹ (William Kyle Million) / IntuiTek¹

Surfaces:
  POST /stripe/webhook          — Stripe event ingestion (signed)
  GET  /validate                — License key validation (customer Docker containers)
  POST /intake/submit           — Customer intake form backend
  GET  /intake/verify/{token}   — Token validity check (frontend pre-validation)
  GET  /health                  — Aegis heartbeat probe

Deploy: Railway (single service, HTTPS via Railway TLS)
"""

import hashlib
import hmac
import logging
import os
import sqlite3
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import stripe
from cryptography.fernet import Fernet
from fastapi import FastAPI, Header, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, EmailStr
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from package_generator import generate_and_deliver

# ── CONFIGURATION ────────────────────────────────────────────
DB_PATH              = os.environ.get("ACE_DB_PATH", "/data/ace.db")
STRIPE_SECRET_KEY    = os.environ.get("STRIPE_SECRET_KEY", "sk_test_dev")
STRIPE_WEBHOOK_SECRET= os.environ.get("STRIPE_WEBHOOK_SECRET", "whsec_dev")
RESEND_API_KEY       = os.environ.get("RESEND_API_KEY", "dev_token")
FERNET_KEY           = os.environ.get("FERNET_KEY", "Drmhze6EPcv0fN_81Bj-nA==").encode()  # bytes
PRICE_CENTS          = 3900                                   # $39.00/month

stripe.api_key = STRIPE_SECRET_KEY
fernet         = Fernet(FERNET_KEY)
limiter        = Limiter(key_func=get_remote_address)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
log = logging.getLogger("ace")

# ── STARTUP DIAGNOSTICS ──────────────────────────────────────
log.info("[ACE] Startup — checking database configuration")
log.info("[ACE] DB_PATH resolved to: %s", DB_PATH)
db_dir = os.path.dirname(DB_PATH)
log.info("[ACE] DB parent directory: %s", db_dir if db_dir else "(current dir)")
log.info("[ACE] DB dir exists: %s", os.path.isdir(db_dir) if db_dir else "N/A (using cwd)")
if db_dir:
    log.info("[ACE] DB dir writable: %s", os.access(db_dir, os.W_OK))

# ── DATABASE ─────────────────────────────────────────────────
def get_db() -> sqlite3.Connection:
    # Ensure parent directory exists before opening database
    db_dir = os.path.dirname(DB_PATH)
    if db_dir and not os.path.isdir(db_dir):
        try:
            os.makedirs(db_dir, mode=0o755, exist_ok=True)
            log.info("Created database directory: %s", db_dir)
        except PermissionError as e:
            log.error("FATAL: Cannot create database directory %s: %s", db_dir, e)
            raise RuntimeError(f"Cannot create db directory '{db_dir}': {e}") from e
    
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    # Inline schema to avoid file dependency in Docker
    schema = """
CREATE TABLE IF NOT EXISTS accounts (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS customers (
    id TEXT PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    name TEXT,
    stripe_customer_id TEXT,
    customer_stripe_id TEXT,
    subscription_id TEXT UNIQUE,
    license_key TEXT UNIQUE,
    intake_token TEXT UNIQUE,
    intake_token_exp INTEGER,
    api_key_enc TEXT,
    api_key_hash TEXT,
    agent_name TEXT,
    use_case TEXT,
    status TEXT DEFAULT 'awaiting_intake',
    intake_at INTEGER,
    provisioned_at INTEGER,
    cancelled_at INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS provision_log (
    id TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL,
    step TEXT,
    status TEXT,
    detail TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (customer_id) REFERENCES customers(id)
);

CREATE TABLE IF NOT EXISTS licenses (
    id TEXT PRIMARY KEY,
    account_id TEXT NOT NULL,
    key TEXT UNIQUE NOT NULL,
    status TEXT DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP,
    FOREIGN KEY (account_id) REFERENCES accounts(id)
);

CREATE TABLE IF NOT EXISTS subscriptions (
    id TEXT PRIMARY KEY,
    account_id TEXT NOT NULL,
    stripe_subscription_id TEXT UNIQUE,
    status TEXT DEFAULT 'active',
    plan_id TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (account_id) REFERENCES accounts(id)
);

CREATE TABLE IF NOT EXISTS agents (
    id TEXT PRIMARY KEY,
    account_id TEXT NOT NULL,
    name TEXT NOT NULL,
    model TEXT DEFAULT 'claude-sonnet-4-20250514',
    config TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (account_id) REFERENCES accounts(id)
);

CREATE TABLE IF NOT EXISTS intake_forms (
    id TEXT PRIMARY KEY,
    account_id TEXT NOT NULL,
    email TEXT NOT NULL,
    name TEXT NOT NULL,
    business_type TEXT,
    submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    processed_at TIMESTAMP,
    FOREIGN KEY (account_id) REFERENCES accounts(id)
);

CREATE TABLE IF NOT EXISTS agent_packages (
    id TEXT PRIMARY KEY,
    intake_form_id TEXT NOT NULL,
    agent_id TEXT NOT NULL,
    package_data TEXT,
    delivery_status TEXT DEFAULT 'pending',
    delivered_at TIMESTAMP,
    FOREIGN KEY (intake_form_id) REFERENCES intake_forms(id),
    FOREIGN KEY (agent_id) REFERENCES agents(id)
);

CREATE TABLE IF NOT EXISTS invoices (
    id TEXT PRIMARY KEY,
    account_id TEXT NOT NULL,
    stripe_invoice_id TEXT UNIQUE,
    amount_cents INTEGER,
    status TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (account_id) REFERENCES accounts(id)
);

CREATE TABLE IF NOT EXISTS events (
    id TEXT PRIMARY KEY,
    account_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    event_data TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (account_id) REFERENCES accounts(id)
);

CREATE TABLE IF NOT EXISTS webhook_log (
    event_id TEXT PRIMARY KEY,
    event_type TEXT NOT NULL,
    processed INTEGER DEFAULT 0,
    error TEXT,
    received_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS license_checks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    license_key TEXT NOT NULL,
    result TEXT NOT NULL,
    source_ip TEXT,
    stripe_status TEXT,
    checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;

CREATE INDEX IF NOT EXISTS idx_licenses_account_id ON licenses(account_id);
CREATE INDEX IF NOT EXISTS idx_subscriptions_account_id ON subscriptions(account_id);
CREATE INDEX IF NOT EXISTS idx_agents_account_id ON agents(account_id);
CREATE INDEX IF NOT EXISTS idx_intake_forms_account_id ON intake_forms(account_id);
CREATE INDEX IF NOT EXISTS idx_agent_packages_intake_form_id ON agent_packages(intake_form_id);
CREATE INDEX IF NOT EXISTS idx_invoices_account_id ON invoices(account_id);
CREATE INDEX IF NOT EXISTS idx_events_account_id ON events(account_id);
CREATE INDEX IF NOT EXISTS idx_customers_subscription_id ON customers(subscription_id);
CREATE INDEX IF NOT EXISTS idx_customers_license_key ON customers(license_key);
CREATE INDEX IF NOT EXISTS idx_customers_intake_token ON customers(intake_token);
CREATE INDEX IF NOT EXISTS idx_license_checks_license_key ON license_checks(license_key);
"""
    with get_db() as conn:
        conn.executescript(schema)
    log.info("ACE database initialized at %s", DB_PATH)


def migrate_schema():
    """Idempotent migration: ensures deployed DB matches current schema.

    Called after init_db() at every startup. Safe on both fresh volumes
    (all CREATE TABLE IF NOT EXISTS are no-ops) and existing Railway volumes
    that predate the C1/C2 schema fixes (ALTER TABLE adds missing columns).
    """
    with get_db() as conn:
        # C1 fix — missing tables: safe on both fresh and existing volumes
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS webhook_log (
                event_id TEXT PRIMARY KEY,
                event_type TEXT NOT NULL,
                processed INTEGER DEFAULT 0,
                error TEXT,
                received_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS license_checks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                license_key TEXT NOT NULL,
                result TEXT NOT NULL,
                source_ip TEXT,
                stripe_status TEXT,
                checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # C2 fix — missing columns on customers; only ALTER when absent
        existing_cols = {
            row[1]
            for row in conn.execute("PRAGMA table_info(customers)").fetchall()
        }
        missing_cols = [
            ("subscription_id",   "TEXT"),
            ("customer_stripe_id","TEXT"),
            ("license_key",       "TEXT"),
            ("intake_token",      "TEXT"),
            ("intake_token_exp",  "INTEGER"),
            ("api_key_enc",       "TEXT"),
            ("api_key_hash",      "TEXT"),
            ("agent_name",        "TEXT"),
            ("use_case",          "TEXT"),
            ("intake_at",         "INTEGER"),
            ("provisioned_at",    "INTEGER"),
            ("cancelled_at",      "INTEGER"),
        ]
        for col_name, col_type in missing_cols:
            if col_name not in existing_cols:
                conn.execute(
                    f"ALTER TABLE customers ADD COLUMN {col_name} {col_type}"
                )
                log.info("migrate_schema: added customers.%s %s", col_name, col_type)

    log.info("migrate_schema: complete")


# ── LIFESPAN ─────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    migrate_schema()
    yield


# ── APP ──────────────────────────────────────────────────────
app = FastAPI(
    title="IntuiTek¹ ACE Server",
    version="1.0.0",
    docs_url=None,   # no public docs in production
    redoc_url=None,
    lifespan=lifespan,
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://intuitek.ai"],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


# ══════════════════════════════════════════════════════════════
# STRIPE WEBHOOK
# ══════════════════════════════════════════════════════════════
@app.post("/stripe/webhook", status_code=200)
async def stripe_webhook(request: Request, stripe_signature: str = Header(None)):
    body = await request.body()

    # Signature validation — reject unsigned
    try:
        event = stripe.Webhook.construct_event(
            body, stripe_signature, STRIPE_WEBHOOK_SECRET
        )
    except stripe.error.SignatureVerificationError:
        log.warning("Stripe signature verification failed")
        raise HTTPException(status_code=400, detail="Invalid signature")

    event_id   = event["id"]
    event_type = event["type"]

    # Idempotency guard
    with get_db() as conn:
        existing = conn.execute(
            "SELECT processed FROM webhook_log WHERE event_id = ?", (event_id,)
        ).fetchone()
        if existing and existing["processed"] == 1:
            log.info("Duplicate webhook ignored: %s", event_id)
            return Response(status_code=200)
        conn.execute(
            "INSERT OR IGNORE INTO webhook_log (event_id, event_type) VALUES (?, ?)",
            (event_id, event_type),
        )

    try:
        if event_type == "customer.subscription.created":
            await _handle_subscription_created(event["data"]["object"])
        elif event_type in ("customer.subscription.deleted",):
            await _handle_subscription_cancelled(event["data"]["object"])
        elif event_type == "invoice.payment_failed":
            await _handle_payment_failed(event["data"]["object"])
        elif event_type == "invoice.payment_succeeded":
            await _handle_payment_succeeded(event["data"]["object"])
        else:
            log.info("Unhandled event type: %s", event_type)

        with get_db() as conn:
            conn.execute(
                "UPDATE webhook_log SET processed = 1 WHERE event_id = ?", (event_id,)
            )
    except Exception as exc:
        log.exception("Error processing webhook %s", event_id)
        with get_db() as conn:
            conn.execute(
                "UPDATE webhook_log SET processed = 2, error = ? WHERE event_id = ?",
                (str(exc), event_id),
            )
        raise HTTPException(status_code=500, detail="Processing error")

    return Response(status_code=200)


async def _handle_subscription_created(subscription: dict):
    """New paying customer. Create record, generate license + intake token, send invite email."""
    sub_id      = subscription["id"]
    stripe_cust = subscription["customer"]
    email       = _get_stripe_customer_email(stripe_cust)

    customer_id    = str(uuid.uuid4())
    license_key    = str(uuid.uuid4())
    intake_token   = str(uuid.uuid4())
    intake_token_exp = int(time.time()) + 172800  # 48 hours

    with get_db() as conn:
        # Upsert-safe: Stripe can fire created twice in edge cases
        existing = conn.execute(
            "SELECT id FROM customers WHERE subscription_id = ?", (sub_id,)
        ).fetchone()
        if existing:
            log.warning("subscription_created: record already exists for %s", sub_id)
            return

        conn.execute(
            """
            INSERT INTO customers
              (id, email, subscription_id, customer_stripe_id, license_key,
               intake_token, intake_token_exp, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'awaiting_intake')
            """,
            (customer_id, email, sub_id, stripe_cust, license_key,
             intake_token, intake_token_exp),
        )
        conn.execute(
            "INSERT INTO provision_log (customer_id, step, status, detail) VALUES (?, ?, ?, ?)",
            (customer_id, "subscription_created", "ok", f"sub={sub_id}"),
        )

    _send_intake_invitation(email, intake_token)
    log.info("New subscriber provisioned: %s → intake token issued", email)


async def _handle_subscription_cancelled(subscription: dict):
    sub_id = subscription["id"]
    with get_db() as conn:
        conn.execute(
            """
            UPDATE customers
            SET status = 'cancelled', cancelled_at = unixepoch()
            WHERE subscription_id = ?
            """,
            (sub_id,),
        )
    log.info("Subscription cancelled: %s", sub_id)


async def _handle_payment_failed(invoice: dict):
    sub_id = invoice.get("subscription")
    if not sub_id:
        return
    with get_db() as conn:
        conn.execute(
            "UPDATE customers SET status = 'payment_failed' WHERE subscription_id = ?",
            (sub_id,),
        )
    log.info("Payment failed: sub=%s", sub_id)


async def _handle_payment_succeeded(invoice: dict):
    """Reinstate cancelled/failed subscription on successful payment."""
    sub_id = invoice.get("subscription")
    if not sub_id:
        return
    with get_db() as conn:
        row = conn.execute(
            "SELECT status FROM customers WHERE subscription_id = ?", (sub_id,)
        ).fetchone()
        if row and row["status"] in ("cancelled", "payment_failed"):
            conn.execute(
                "UPDATE customers SET status = 'provisioned' WHERE subscription_id = ?",
                (sub_id,),
            )
            log.info("Subscription reinstated: sub=%s", sub_id)


def _get_stripe_customer_email(stripe_customer_id: str) -> str:
    cust = stripe.Customer.retrieve(stripe_customer_id)
    email = cust.get("email") or ""
    if not email:
        raise ValueError(f"No email on Stripe customer {stripe_customer_id}")
    return email


def _send_intake_invitation(email: str, intake_token: str):
    """Dispatch intake form invitation via Resend. Latency target: <60s from webhook."""
    import httpx

    intake_url = f"https://intuitek.ai/join?token={intake_token}"
    payload = {
        "from": "agent@intuitek.ai",
        "to": [email],
        "subject": "Set up your IntuiTek¹ agent — action required",
        "text": (
            f"Your IntuiTek¹ subscription is active.\n\n"
            f"Complete your agent setup here (link expires in 48 hours):\n{intake_url}\n\n"
            f"This takes about 3 minutes. After submission your agent package "
            f"will be emailed to you within 5 minutes.\n\n"
            f"— IntuiTek¹\n"
            f"https://intuitek.ai"
        ),
    }
    resp = httpx.post(
        "https://api.resend.com/emails",
        headers={"Authorization": f"Bearer {RESEND_API_KEY}"},
        json=payload,
        timeout=15,
    )
    if resp.status_code not in (200, 201):
        raise RuntimeError(f"Resend error {resp.status_code}: {resp.text}")


# ══════════════════════════════════════════════════════════════
# LICENSE VALIDATION
# ══════════════════════════════════════════════════════════════
@app.get("/validate")
@limiter.limit("10/minute")
async def validate_license(
    request: Request,
    license_key: str,
):
    """
    Customer Docker containers call this on every startup.
    Validates license_key against SQLite + live Stripe subscription status.
    """
    if not license_key or len(license_key) != 36:  # basic UUID format guard
        raise HTTPException(status_code=400, detail="Malformed license_key")

    source_ip = request.client.host if request.client else None

    with get_db() as conn:
        row = conn.execute(
            "SELECT id, subscription_id, status FROM customers WHERE license_key = ?",
            (license_key,),
        ).fetchone()

    if not row:
        _log_license_check(license_key, "invalid", source_ip, "not_found")
        return {"valid": False, "message": "License key not found. Contact support at intuitek.ai."}

    # Fast path: local status is cancelled — no Stripe round-trip needed
    if row["status"] in ("cancelled", "payment_failed"):
        _log_license_check(license_key, "invalid", source_ip, row["status"])
        return {
            "valid": False,
            "message": "Subscription inactive. Renew at intuitek.ai.",
        }

    # Live Stripe check
    try:
        sub = stripe.Subscription.retrieve(row["subscription_id"])
        stripe_status = sub["status"]  # active, past_due, canceled, etc.
        is_valid = stripe_status in ("active", "trialing", "past_due")
        result   = "valid" if is_valid else "invalid"
        _log_license_check(license_key, result, source_ip, stripe_status)

        if is_valid:
            return {"valid": True}
        else:
            return {
                "valid": False,
                "message": "Subscription inactive. Renew at intuitek.ai.",
            }
    except stripe.error.StripeError as exc:
        log.error("Stripe error during license validation: %s", exc)
        _log_license_check(license_key, "error", source_ip, str(exc))
        # Fail open on Stripe API outage — do not punish paying customers
        return {"valid": True, "warning": "License server degraded — operating in grace mode."}


def _log_license_check(license_key: str, result: str, source_ip: Optional[str], stripe_status: str):
    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO license_checks (license_key, result, source_ip, stripe_status)
            VALUES (?, ?, ?, ?)
            """,
            (license_key, result, source_ip, stripe_status),
        )


# ══════════════════════════════════════════════════════════════
# INTAKE FORM
# ══════════════════════════════════════════════════════════════
class IntakePayload(BaseModel):
    token: str
    name: str
    email: EmailStr
    anthropic_api_key: str
    agent_name: str
    use_case_description: str


@app.get("/intake/verify/{token}")
async def verify_intake_token(token: str):
    """Frontend calls this before rendering the form to confirm token validity."""
    with get_db() as conn:
        row = conn.execute(
            """
            SELECT email, intake_token_exp, status
            FROM customers
            WHERE intake_token = ?
            """,
            (token,),
        ).fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Invalid token")
    if row["status"] != "awaiting_intake":
        raise HTTPException(status_code=409, detail="Intake already completed")
    if int(time.time()) > row["intake_token_exp"]:
        raise HTTPException(status_code=410, detail="Token expired — contact support at intuitek.ai")

    return {"email": row["email"], "valid": True}


@app.post("/intake/submit", status_code=202)
@limiter.limit("5/minute")
async def intake_submit(request: Request, payload: IntakePayload):
    """
    Receives customer intake form submission.
    Validates token → encrypts API key → triggers package generation → sends delivery email.
    Target latency: <5 minutes end-to-end.
    """
    now = int(time.time())

    with get_db() as conn:
        row = conn.execute(
            """
            SELECT id, email, subscription_id, license_key, intake_token_exp, status
            FROM customers
            WHERE intake_token = ?
            """,
            (payload.token,),
        ).fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="Invalid token")
        if row["status"] != "awaiting_intake":
            raise HTTPException(status_code=409, detail="Intake already processed")
        if now > row["intake_token_exp"]:
            raise HTTPException(status_code=410, detail="Token expired")

        # Email must match what Stripe provided
        if row["email"].lower() != payload.email.lower():
            raise HTTPException(status_code=400, detail="Email does not match subscription record")

        customer_id = row["id"]
        license_key = row["license_key"]

        # Encrypt API key — never stored plaintext
        api_key_enc  = fernet.encrypt(payload.anthropic_api_key.encode()).decode()
        api_key_hash = hashlib.sha256(payload.anthropic_api_key.encode()).hexdigest()

        conn.execute(
            """
            UPDATE customers SET
              name            = ?,
              agent_name      = ?,
              use_case        = ?,
              api_key_enc     = ?,
              api_key_hash    = ?,
              status          = 'intake_received',
              intake_at       = ?
            WHERE id = ?
            """,
            (
                payload.name,
                payload.agent_name,
                payload.use_case_description,
                api_key_enc,
                api_key_hash,
                now,
                customer_id,
            ),
        )
        conn.execute(
            "INSERT INTO provision_log (customer_id, step, status) VALUES (?, 'intake_received', 'ok')",
            (customer_id,),
        )

    # Hand off to package generator (runs async — FastAPI background task)
    from fastapi.background import BackgroundTasks
    # Inline for simplicity; production: use Celery or APScheduler task queue
    customer_data = {
        "id":           customer_id,
        "name":         payload.name,
        "email":        payload.email,
        "agent_name":   payload.agent_name,
        "use_case":     payload.use_case_description,
        "license_key":  license_key,
        # API key NOT passed — generator retrieves + decrypts from DB only when needed
    }

    import asyncio
    asyncio.create_task(_provision_customer(customer_data))

    return {"status": "received", "message": "Your agent package will be emailed within 5 minutes."}


async def _provision_customer(customer_data: dict):
    """Background task: generate package and send delivery email."""
    try:
        generate_and_deliver(customer_data, DB_PATH, fernet, RESEND_API_KEY)
        with get_db() as conn:
            conn.execute(
                """
                UPDATE customers SET status = 'provisioned', provisioned_at = unixepoch()
                WHERE id = ?
                """,
                (customer_data["id"],),
            )
            conn.execute(
                "INSERT INTO provision_log (customer_id, step, status) VALUES (?, 'provisioned', 'ok')",
                (customer_data["id"],),
            )
        log.info("Customer provisioned: %s", customer_data["email"])
    except Exception as exc:
        log.exception("Provisioning failed for customer %s", customer_data["id"])
        with get_db() as conn:
            conn.execute(
                "INSERT INTO provision_log (customer_id, step, status, detail) VALUES (?, 'provision_error', 'error', ?)",
                (customer_data["id"], str(exc)),
            )


# ══════════════════════════════════════════════════════════════
# POST-PAYMENT SUCCESS PAGE
# ══════════════════════════════════════════════════════════════
@app.get("/success", response_class=HTMLResponse)
async def success_page():
    """Stripe post-payment redirect — clean confirmation page."""
    html_path = Path(__file__).parent / "success.html"
    if html_path.exists():
        return HTMLResponse(content=html_path.read_text(), status_code=200)
    # Fallback if file somehow missing
    return HTMLResponse(content="""
    <html><body style="font-family:sans-serif;text-align:center;padding:60px;background:#0a0a0f;color:#e8e8f0;">
    <h1>&#10003; Payment confirmed.</h1>
    <p>Your license will be delivered to your email within 2 minutes.</p>
    <p><a href="https://www.shopclawmart.com/thebrierfox" style="color:#7c3aed;">Browse more skills</a></p>
    </body></html>
    """, status_code=200)


# HEALTH / AEGIS PROBE
# ══════════════════════════════════════════════════════════════
@app.get("/health")
async def health():
    """Aegis heartbeat probe. Returns active subscriber count + MRR."""
    with get_db() as conn:
        active = conn.execute(
            "SELECT COUNT(*) as c FROM customers WHERE status = 'provisioned'"
        ).fetchone()["c"]
    return {
        "status": "ok",
        "active_subscribers": active,
        "mrr_cents": active * PRICE_CENTS,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

# Rebuild marker: 1774668014

# ══════════════════════════════════════════════════════════════
# MCP SERVERS + API ROUTERS  (added below existing routes)
# ══════════════════════════════════════════════════════════════
from mcp.yield_server import yield_mcp_app
from mcp.ace_server import ace_mcp_app
from mcp.counselor_server import counselor_mcp_app
from api.pricing import pricing_router
from api.checkouts import checkouts_router
from api.agent_card import agent_card_router
from middleware.x402 import X402Middleware

# MCP Streamable HTTP servers
app.mount("/yield", yield_mcp_app)
app.mount("/ace", ace_mcp_app)
app.mount("/counselor", counselor_mcp_app)

# REST API endpoints
app.include_router(pricing_router, prefix="/pricing")
app.include_router(checkouts_router, prefix="/checkouts")
app.include_router(agent_card_router)  # handles /.well-known/agent-card.json

# x402 payment middleware (applies to /v1/* routes)
app.add_middleware(X402Middleware)
