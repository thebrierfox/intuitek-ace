"""
IntuiTek¹ — The Answer
One-time diagnostic product.

Flow:
  POST /answer/checkout         → Stripe Checkout Session URL (caller redirects)
  GET  /answer/form/{token}     → HTML intake form (shown after Stripe payment)
  POST /answer/submit/{token}   → validate payment, call Claude, deliver HTML email

DB table: answer_sessions (added via init_db)
"""

import logging
import os
import sqlite3
import time
import uuid
from typing import Optional

import httpx
import stripe
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, EmailStr

log = logging.getLogger("ace.answer")

router = APIRouter(prefix="/answer", tags=["the-answer"])

# ── CONFIG ───────────────────────────────────────────────────
RESEND_API_KEY       = os.environ.get("RESEND_API_KEY", "")
ANTHROPIC_API_KEY    = os.environ.get("ANTHROPIC_API_KEY", "")
THE_ANSWER_PRICE_ID  = os.environ.get("THE_ANSWER_PRICE_ID", "price_1TWot2BDuMBkXxIDbULckhXe")
ACE_BASE_URL         = os.environ.get("ACE_BASE_URL", "https://ace-license-server-production.up.railway.app")
CLAUDE_MODEL         = "claude-sonnet-4-6"

ANSWER_SYSTEM_PROMPT = """\
You are Kyle Million's diagnostic voice.

Kyle has spent years developing a precise way of reading situations — not as problems to \
solve but as systems producing predictable outputs. His diagnostic sequence:

1. System detection before symptom analysis — what system is producing this?
2. False dependency audit — what do they believe they need that they don't?
3. Motion vs. progress distinction — are they moving or are they advancing?
4. Completion identification — what is actually done that they're treating as in-flight?
5. Naming the stop — what are they not naming?
6. The one move — what is the single highest-leverage next action?

You write ONE document. Four sections, in order. No preamble. No header above POSITION. \
Exactly 400–600 words total across all four sections. No bullet points — prose only.

Sections:
POSITION
What is actually happening — not the situation they described but the system underneath it. \
Name the system. Name where they actually are inside it.

WHAT IS ACTUALLY AT RISK
Not what they fear losing. What is actually at risk if nothing changes. The real thing, not \
the stated thing.

WHY YOU CANNOT SEE IT FROM INSIDE
What makes this invisible from their vantage point. Not a failure of intelligence — a \
structural feature of being inside the system.

THE ONE MOVE
One action. Not a plan. Not a framework. One specific thing they can do in the next 48 hours \
that changes their position in the system. Name it precisely.
"""


# ── DATABASE ─────────────────────────────────────────────────
_DB_PATH = os.environ.get("ACE_DB_PATH", "/data/ace.db")


def _get_db() -> sqlite3.Connection:
    import sqlite3 as _sqlite3
    conn = _sqlite3.connect(_DB_PATH, check_same_thread=False)
    conn.row_factory = _sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _verify_stripe_payment(session_id: str) -> Optional[str]:
    """Return customer email if session is paid, else None."""
    try:
        session = stripe.checkout.Session.retrieve(session_id, expand=["customer"])
        if session.payment_status == "paid":
            email = session.customer_details.email if session.customer_details else None
            return email
        return None
    except stripe.error.StripeError as exc:
        log.error("Stripe session lookup failed: %s", exc)
        return None


def _generate_diagnosis(name: str, role: str, situation: str, tried: str, cant_name: str) -> str:
    """Call Claude Sonnet via direct HTTPS to generate the diagnostic document."""
    user_message = (
        f"Name: {name}\n"
        f"Role / what they do: {role}\n\n"
        f"What is currently happening:\n{situation}\n\n"
        f"What they have tried or considered:\n{tried}\n\n"
        f"What they cannot name or put into words:\n{cant_name}"
    )

    resp = httpx.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": CLAUDE_MODEL,
            "max_tokens": 1024,
            "system": ANSWER_SYSTEM_PROMPT,
            "messages": [{"role": "user", "content": user_message}],
        },
        timeout=60,
    )
    resp.raise_for_status()
    data = resp.json()
    return data["content"][0]["text"]


def _format_html_email(name: str, diagnosis: str) -> str:
    first = name.split()[0] if name else "—"
    # Convert section headers to bold in HTML
    html_body = diagnosis
    for section in ("POSITION", "WHAT IS ACTUALLY AT RISK", "WHY YOU CANNOT SEE IT FROM INSIDE", "THE ONE MOVE"):
        html_body = html_body.replace(section, f"<strong>{section}</strong>")
    html_body = html_body.replace("\n\n", "</p><p>").replace("\n", "<br>")

    return f"""\
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family:Georgia,serif;max-width:640px;margin:40px auto;padding:0 24px;color:#1a1a1a;line-height:1.7;">
<p style="color:#888;font-size:13px;margin-bottom:32px;">IntuiTek¹ — The Answer</p>
<p>{first},</p>
<p>{html_body}</p>
<hr style="border:none;border-top:1px solid #e0e0e0;margin:40px 0;">
<p style="color:#888;font-size:12px;">— ~K¹ / IntuiTek¹<br>https://intuitek.ai</p>
</body>
</html>"""


def _send_answer_email(email: str, name: str, html: str) -> None:
    resp = httpx.post(
        "https://api.resend.com/emails",
        headers={"Authorization": f"Bearer {RESEND_API_KEY}"},
        json={
            "from": "kyle@intuitek.ai",
            "to": [email],
            "subject": "The Answer",
            "html": html,
        },
        timeout=20,
    )
    if resp.status_code not in (200, 201):
        raise RuntimeError(f"Resend error {resp.status_code}: {resp.text}")


# ── ENDPOINTS ────────────────────────────────────────────────

@router.post("/checkout")
async def create_checkout(request: Request):
    """Create a Stripe Checkout Session for The Answer. Returns {checkout_url}."""
    if not THE_ANSWER_PRICE_ID or not THE_ANSWER_PRICE_ID.startswith("price_"):
        raise HTTPException(status_code=503, detail="Stripe price not configured")

    token = str(uuid.uuid4())
    success_url = f"{ACE_BASE_URL}/answer/form/{token}?session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url  = "https://intuitek.ai/the-answer"

    try:
        session = stripe.checkout.Session.create(
            mode="payment",
            line_items=[{"price": THE_ANSWER_PRICE_ID, "quantity": 1}],
            success_url=success_url,
            cancel_url=cancel_url,
        )
    except stripe.error.StripeError as exc:
        log.error("Stripe checkout creation failed: %s", exc)
        raise HTTPException(status_code=502, detail="Payment system error")

    with _get_db() as conn:
        conn.execute(
            """
            INSERT INTO answer_sessions (token, stripe_session_id, status, created_at)
            VALUES (?, ?, 'pending_payment', unixepoch())
            """,
            (token, session.id),
        )

    return {"checkout_url": session.url}


INTAKE_FORM_HTML = """\
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>The Answer — IntuiTek¹</title>
<style>
  body{{font-family:Georgia,serif;max-width:640px;margin:60px auto;padding:0 24px;
        color:#1a1a1a;line-height:1.7;background:#fff}}
  h1{{font-size:1.4em;font-weight:normal;margin-bottom:4px}}
  .sub{{color:#666;font-size:0.95em;margin-bottom:40px}}
  label{{display:block;font-size:0.9em;color:#444;margin-top:24px;margin-bottom:6px}}
  input,textarea{{width:100%;box-sizing:border-box;border:1px solid #ccc;padding:10px 12px;
                  font-family:Georgia,serif;font-size:1em;border-radius:3px;color:#1a1a1a}}
  textarea{{min-height:120px;resize:vertical}}
  button{{margin-top:32px;background:#1a1a1a;color:#fff;border:none;padding:14px 28px;
          font-size:1em;cursor:pointer;border-radius:3px;font-family:Georgia,serif}}
  button:hover{{background:#333}}
  .note{{color:#888;font-size:0.85em;margin-top:12px}}
</style>
</head>
<body>
<h1>The Answer</h1>
<p class="sub">400–600 words. Delivered to your inbox in under 5 minutes.</p>
<form method="POST" action="/answer/submit/{token}">
  <input type="hidden" name="session_id" value="{session_id}">
  <label>Your name</label>
  <input type="text" name="name" required maxlength="120">
  <label>Your role — what you do</label>
  <input type="text" name="role" required maxlength="240">
  <label>What is currently happening in your work or situation</label>
  <textarea name="situation" required maxlength="2000"></textarea>
  <label>What have you already tried or considered</label>
  <textarea name="tried" required maxlength="1000"></textarea>
  <label>What are you unable to name or put into words — even approximately</label>
  <textarea name="cant_name" required maxlength="1000"></textarea>
  <label>Email address (where to send The Answer)</label>
  <input type="email" name="email" required maxlength="320">
  <button type="submit">Send The Answer</button>
  <p class="note">Delivered in under 5 minutes. No follow-up required from you.</p>
</form>
</body>
</html>
"""


@router.get("/form/{token}", response_class=HTMLResponse)
async def intake_form(token: str, session_id: str = ""):
    with _get_db() as conn:
        row = conn.execute(
            "SELECT status, stripe_session_id FROM answer_sessions WHERE token = ?",
            (token,),
        ).fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Not found")
    if row["status"] == "delivered":
        return HTMLResponse("<p>Your Answer has already been sent. Check your inbox.</p>", status_code=200)

    # Use provided session_id or the stored one
    sid = session_id or row["stripe_session_id"]
    return HTMLResponse(INTAKE_FORM_HTML.format(token=token, session_id=sid))


class AnswerIntake(BaseModel):
    session_id: str
    name: str
    role: str
    situation: str
    tried: str
    cant_name: str
    email: EmailStr


@router.post("/submit/{token}", response_class=HTMLResponse)
async def intake_submit(token: str, request: Request):
    """Accept form POST, verify payment, generate diagnosis, deliver email."""
    form = await request.form()

    name       = str(form.get("name", "")).strip()
    role       = str(form.get("role", "")).strip()
    situation  = str(form.get("situation", "")).strip()
    tried      = str(form.get("tried", "")).strip()
    cant_name  = str(form.get("cant_name", "")).strip()
    email      = str(form.get("email", "")).strip().lower()
    session_id = str(form.get("session_id", "")).strip()

    if not all([name, role, situation, tried, cant_name, email]):
        raise HTTPException(status_code=400, detail="All fields required")

    with _get_db() as conn:
        row = conn.execute(
            "SELECT status, stripe_session_id FROM answer_sessions WHERE token = ?",
            (token,),
        ).fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Session not found")
    if row["status"] == "delivered":
        return HTMLResponse("<p>Already sent. Check your inbox.</p>")

    # Verify payment via Stripe before doing any work
    sid = session_id or row["stripe_session_id"]
    paid_email = _verify_stripe_payment(sid)
    if paid_email is None:
        raise HTTPException(status_code=402, detail="Payment not confirmed")

    # Atomic claim
    with _get_db() as conn:
        result = conn.execute(
            """
            UPDATE answer_sessions
            SET status = 'generating', email = ?
            WHERE token = ? AND status != 'delivered'
            """,
            (email, token),
        )
        if result.rowcount == 0:
            return HTMLResponse("<p>Already in progress. Check your inbox shortly.</p>")

    # Generate + deliver
    try:
        diagnosis = _generate_diagnosis(name, role, situation, tried, cant_name)
        html      = _format_html_email(name, diagnosis)
        _send_answer_email(email, name, html)

        with _get_db() as conn:
            conn.execute(
                "UPDATE answer_sessions SET status = 'delivered', delivered_at = unixepoch() WHERE token = ?",
                (token,),
            )
        log.info("The Answer delivered to %s", email)

        return HTMLResponse(f"""\
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>Sent — IntuiTek¹</title></head>
<body style="font-family:Georgia,serif;max-width:640px;margin:100px auto;padding:0 24px;color:#1a1a1a">
<h2 style="font-weight:normal">Sent.</h2>
<p>Check <strong>{email}</strong>. It should arrive within a few minutes.</p>
<p style="color:#888;font-size:0.9em">— IntuiTek¹</p>
</body>
</html>""")

    except Exception as exc:
        log.exception("The Answer generation/delivery failed for %s", email)
        with _get_db() as conn:
            conn.execute(
                "UPDATE answer_sessions SET status = 'error' WHERE token = ?",
                (token,),
            )
        raise HTTPException(status_code=500, detail="Generation failed — support notified")
