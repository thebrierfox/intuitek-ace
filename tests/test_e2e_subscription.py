"""
ACE E2E subscription flow test — local equivalent of `stripe trigger customer.subscription.created`.

Verifies end-to-end webhook processing on a fresh SQLite volume:
  1. init_db() + migrate_schema() initializes cleanly (no OperationalError)
  2. Signed customer.subscription.created webhook is accepted (HTTP 200)
  3. webhook_log entry created with processed=1
  4. customers row created with all required columns populated
  5. provision_log entry created

No network calls (Stripe API + Resend are patched). No Stripe CLI required.
This is the schema-correctness acceptance gate before Railway deploy.

Run:
  cd ~/intuitek/github_work/intuitek-ace
  pytest tests/test_e2e_subscription.py -v
"""

import hashlib
import hmac
import importlib
import json
import os
import sqlite3
import time
import uuid

import pytest
from fastapi.testclient import TestClient

# ── Fixture ─────────────────────────────────────────────────────────────────

TEST_WEBHOOK_SECRET = "whsec_test_e2e_secret"
TEST_EMAIL          = "e2e-subscriber@test.intuitek.ai"
TEST_SUB_ID         = f"sub_{uuid.uuid4().hex[:16]}"
TEST_CUST_ID        = f"cus_{uuid.uuid4().hex[:16]}"


@pytest.fixture()
def ace(tmp_path, monkeypatch):
    """
    Patch environment, reload ace_server, run schema init, patch external calls.
    Returns (TestClient, db_path).
    """
    db_file = str(tmp_path / "ace_e2e.db")

    # Force a fresh Fernet key (valid 32-byte base64url)
    import base64
    fernet_key = base64.urlsafe_b64encode(b"\x00" * 32).decode()

    monkeypatch.setenv("ACE_DB_PATH",           db_file)
    monkeypatch.setenv("STRIPE_SECRET_KEY",      "sk_test_e2e")
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET",  TEST_WEBHOOK_SECRET)
    monkeypatch.setenv("RESEND_API_KEY",         "re_test_stub")
    monkeypatch.setenv("FERNET_KEY",             fernet_key)

    import ace_server
    importlib.reload(ace_server)
    ace_server.init_db()
    ace_server.migrate_schema()

    # Patch Stripe customer retrieval — avoids live API call
    monkeypatch.setattr(
        ace_server, "_get_stripe_customer_email",
        lambda stripe_cust_id: TEST_EMAIL,
    )
    # Patch Resend email — avoids live send
    monkeypatch.setattr(
        ace_server, "_send_intake_invitation",
        lambda email, token: None,
    )

    client = TestClient(ace_server.app, raise_server_exceptions=False)
    yield client, db_file


# ── Helpers ──────────────────────────────────────────────────────────────────

def _sign_payload(body: bytes, secret: str) -> str:
    """Build Stripe-Signature header matching stripe.WebhookSignature.verify_header()."""
    ts = int(time.time())
    signed = "%d.%s" % (ts, body.decode())
    sig = hmac.new(secret.encode("utf-8"), signed.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"t={ts},v1={sig}"


def _subscription_created_payload(sub_id: str, cust_id: str) -> bytes:
    event = {
        "id": f"evt_{uuid.uuid4().hex[:16]}",
        "object": "event",
        "api_version": "2023-10-16",
        "type": "customer.subscription.created",
        "livemode": False,
        "data": {
            "object": {
                "id": sub_id,
                "object": "subscription",
                "customer": cust_id,
                "status": "active",
            }
        },
    }
    return json.dumps(event).encode()


# ── Tests ────────────────────────────────────────────────────────────────────

class TestSubscriptionCreatedFlow:

    def test_server_health_on_fresh_volume(self, ace):
        """Server starts cleanly and /health responds."""
        client, _ = ace
        r = client.get("/health")
        assert r.status_code == 200

    def test_webhook_returns_200(self, ace):
        """Signed customer.subscription.created webhook is accepted."""
        client, _ = ace
        body = _subscription_created_payload(TEST_SUB_ID, TEST_CUST_ID)
        sig  = _sign_payload(body, TEST_WEBHOOK_SECRET)
        r = client.post(
            "/stripe/webhook",
            content=body,
            headers={"stripe-signature": sig, "content-type": "application/json"},
        )
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"

    def test_webhook_log_processed(self, ace):
        """webhook_log entry has processed=1 after successful handling."""
        client, db_path = ace
        body = _subscription_created_payload(TEST_SUB_ID, TEST_CUST_ID)
        sig  = _sign_payload(body, TEST_WEBHOOK_SECRET)
        client.post(
            "/stripe/webhook",
            content=body,
            headers={"stripe-signature": sig, "content-type": "application/json"},
        )
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM webhook_log WHERE event_type = 'customer.subscription.created'").fetchone()
        conn.close()
        assert row is not None, "webhook_log has no entry for the event"
        assert row["processed"] == 1, f"webhook_log.processed={row['processed']}, expected 1"

    def test_customer_record_created(self, ace):
        """customers row exists with subscription_id, license_key, intake_token."""
        client, db_path = ace
        body = _subscription_created_payload(TEST_SUB_ID, TEST_CUST_ID)
        sig  = _sign_payload(body, TEST_WEBHOOK_SECRET)
        client.post(
            "/stripe/webhook",
            content=body,
            headers={"stripe-signature": sig, "content-type": "application/json"},
        )
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM customers WHERE subscription_id = ?", (TEST_SUB_ID,)).fetchone()
        conn.close()
        assert row is not None, "customers table has no record for the subscription"
        assert row["email"] == TEST_EMAIL
        assert row["license_key"] is not None and len(row["license_key"]) > 10
        assert row["intake_token"] is not None and len(row["intake_token"]) > 10
        assert row["status"] == "awaiting_intake"
        assert row["customer_stripe_id"] == TEST_CUST_ID

    def test_provision_log_entry_created(self, ace):
        """provision_log records the subscription_created step."""
        client, db_path = ace
        body = _subscription_created_payload(TEST_SUB_ID, TEST_CUST_ID)
        sig  = _sign_payload(body, TEST_WEBHOOK_SECRET)
        client.post(
            "/stripe/webhook",
            content=body,
            headers={"stripe-signature": sig, "content-type": "application/json"},
        )
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM provision_log WHERE step = 'subscription_created'"
        ).fetchone()
        conn.close()
        assert row is not None, "provision_log has no subscription_created entry"
        assert row["status"] == "ok"

    def test_idempotency_guard(self, ace):
        """Duplicate webhook with same event_id returns 200 without creating duplicate customer."""
        client, db_path = ace
        body = _subscription_created_payload(TEST_SUB_ID, TEST_CUST_ID)
        sig1 = _sign_payload(body, TEST_WEBHOOK_SECRET)
        sig2 = _sign_payload(body, TEST_WEBHOOK_SECRET)

        r1 = client.post(
            "/stripe/webhook",
            content=body,
            headers={"stripe-signature": sig1, "content-type": "application/json"},
        )
        r2 = client.post(
            "/stripe/webhook",
            content=body,
            headers={"stripe-signature": sig2, "content-type": "application/json"},
        )
        assert r1.status_code == 200
        assert r2.status_code == 200

        conn = sqlite3.connect(db_path)
        count = conn.execute(
            "SELECT COUNT(*) FROM customers WHERE subscription_id = ?", (TEST_SUB_ID,)
        ).fetchone()[0]
        conn.close()
        assert count == 1, f"Expected 1 customer row, got {count} (duplicate insertion)"

    def test_unsigned_webhook_rejected(self, ace):
        """Webhook without valid signature returns 400."""
        client, _ = ace
        body = _subscription_created_payload(TEST_SUB_ID, TEST_CUST_ID)
        r = client.post(
            "/stripe/webhook",
            content=body,
            headers={"content-type": "application/json"},
        )
        assert r.status_code in (400, 401, 403), f"Expected 4xx, got {r.status_code}"
