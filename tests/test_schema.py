"""
ACE schema integrity tests — AUDITOR-discipline acceptance gate.

These tests cover the C1/C2 P0 blockers identified in the pre-traffic audit:
  C1: webhook_log and license_checks tables absent from init_db()
  C2: customers table missing 12 columns required by application code

Run before any Railway deploy:
  cd ~/intuitek/github_work/intuitek-ace
  pip install pytest
  pytest tests/test_schema.py -v

All tests use a temporary SQLite file — no Railway volume, no network required.
"""

import os
import sqlite3
import tempfile
import uuid

import pytest


# ── Fixtures ─────────────────────────────────────────────────

@pytest.fixture()
def fresh_db(tmp_path, monkeypatch):
    """Patch DB_PATH to a temp file, run init_db() + migrate_schema(), yield conn."""
    db_file = str(tmp_path / "test_ace.db")
    monkeypatch.setenv("ACE_DB_PATH", db_file)

    # Re-import to pick up the patched env var
    import importlib
    import ace_server
    importlib.reload(ace_server)
    ace_server.init_db()
    ace_server.migrate_schema()

    conn = sqlite3.connect(db_file)
    conn.row_factory = sqlite3.Row
    yield conn
    conn.close()


@pytest.fixture()
def legacy_db(tmp_path, monkeypatch):
    """Simulate the deployed Railway DB: customers with OLD (6-column) schema, no webhook_log/license_checks."""
    db_file = str(tmp_path / "legacy_ace.db")
    monkeypatch.setenv("ACE_DB_PATH", db_file)

    conn = sqlite3.connect(db_file)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""
        CREATE TABLE customers (
            id TEXT PRIMARY KEY,
            email TEXT UNIQUE NOT NULL,
            name TEXT,
            stripe_customer_id TEXT UNIQUE,
            status TEXT DEFAULT 'active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE provision_log (
            id TEXT PRIMARY KEY,
            customer_id TEXT NOT NULL,
            step TEXT,
            status TEXT,
            detail TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

    import importlib
    import ace_server
    importlib.reload(ace_server)
    ace_server.migrate_schema()

    conn2 = sqlite3.connect(db_file)
    conn2.row_factory = sqlite3.Row
    yield conn2
    conn2.close()


# ── C1: missing tables ────────────────────────────────────────

class TestC1MissingTables:
    def test_webhook_log_exists_on_fresh_volume(self, fresh_db):
        row = fresh_db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='webhook_log'"
        ).fetchone()
        assert row is not None, "C1: webhook_log table absent from fresh init_db()"

    def test_license_checks_exists_on_fresh_volume(self, fresh_db):
        row = fresh_db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='license_checks'"
        ).fetchone()
        assert row is not None, "C1: license_checks table absent from fresh init_db()"

    def test_webhook_log_insert_succeeds(self, fresh_db):
        event_id = f"evt_{uuid.uuid4()}"
        fresh_db.execute(
            "INSERT OR IGNORE INTO webhook_log (event_id, event_type) VALUES (?, ?)",
            (event_id, "customer.subscription.created"),
        )
        row = fresh_db.execute(
            "SELECT event_id, processed FROM webhook_log WHERE event_id = ?", (event_id,)
        ).fetchone()
        assert row is not None
        assert row["processed"] == 0

    def test_license_checks_insert_succeeds(self, fresh_db):
        fresh_db.execute(
            "INSERT INTO license_checks (license_key, result, source_ip, stripe_status) VALUES (?, ?, ?, ?)",
            (str(uuid.uuid4()), "valid", "127.0.0.1", "active"),
        )
        count = fresh_db.execute("SELECT COUNT(*) as c FROM license_checks").fetchone()["c"]
        assert count == 1

    def test_webhook_log_exists_after_migration_of_legacy_db(self, legacy_db):
        row = legacy_db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='webhook_log'"
        ).fetchone()
        assert row is not None, "C1: migrate_schema() did not add webhook_log to legacy DB"

    def test_license_checks_exists_after_migration_of_legacy_db(self, legacy_db):
        row = legacy_db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='license_checks'"
        ).fetchone()
        assert row is not None, "C1: migrate_schema() did not add license_checks to legacy DB"


# ── C2: customers column reconciliation ──────────────────────

REQUIRED_CUSTOMERS_COLS = {
    "id", "email", "name",
    "subscription_id", "customer_stripe_id", "license_key",
    "intake_token", "intake_token_exp",
    "api_key_enc", "api_key_hash",
    "agent_name", "use_case",
    "status", "intake_at", "provisioned_at", "cancelled_at",
    "created_at",
}


class TestC2CustomersSchema:
    def test_all_required_columns_present_on_fresh_volume(self, fresh_db):
        cols = {
            row[1]
            for row in fresh_db.execute("PRAGMA table_info(customers)").fetchall()
        }
        missing = REQUIRED_CUSTOMERS_COLS - cols
        assert not missing, f"C2: customers missing columns on fresh init: {missing}"

    def test_all_required_columns_present_after_migration(self, legacy_db):
        cols = {
            row[1]
            for row in legacy_db.execute("PRAGMA table_info(customers)").fetchall()
        }
        missing = REQUIRED_CUSTOMERS_COLS - cols
        assert not missing, f"C2: customers missing columns after migration: {missing}"

    def test_subscription_created_insert_executes(self, fresh_db):
        customer_id = str(uuid.uuid4())
        license_key = str(uuid.uuid4())
        intake_token = str(uuid.uuid4())
        fresh_db.execute(
            """
            INSERT INTO customers
              (id, email, subscription_id, customer_stripe_id, license_key,
               intake_token, intake_token_exp, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'awaiting_intake')
            """,
            (customer_id, "test@example.com", f"sub_{uuid.uuid4()}",
             "cus_test123", license_key, intake_token, 9999999999),
        )
        row = fresh_db.execute(
            "SELECT status, license_key FROM customers WHERE id = ?", (customer_id,)
        ).fetchone()
        assert row is not None
        assert row["status"] == "awaiting_intake"
        assert row["license_key"] == license_key

    def test_intake_submit_update_executes(self, fresh_db):
        import time
        customer_id = str(uuid.uuid4())
        fresh_db.execute(
            """
            INSERT INTO customers
              (id, email, subscription_id, customer_stripe_id, license_key,
               intake_token, intake_token_exp, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'awaiting_intake')
            """,
            (customer_id, "intake@example.com", f"sub_{uuid.uuid4()}",
             "cus_intake", str(uuid.uuid4()), str(uuid.uuid4()), 9999999999),
        )
        fresh_db.execute(
            """
            UPDATE customers SET
              name = ?, agent_name = ?, use_case = ?,
              api_key_enc = ?, api_key_hash = ?,
              status = 'intake_received', intake_at = ?
            WHERE id = ?
            """,
            ("Alice", "MyAgent", "Test use case",
             "encrypted_key", "hash_of_key",
             int(time.time()), customer_id),
        )
        row = fresh_db.execute(
            "SELECT status, agent_name FROM customers WHERE id = ?", (customer_id,)
        ).fetchone()
        assert row["status"] == "intake_received"
        assert row["agent_name"] == "MyAgent"

    def test_license_validation_select_executes(self, fresh_db):
        customer_id = str(uuid.uuid4())
        license_key = str(uuid.uuid4())
        sub_id = f"sub_{uuid.uuid4()}"
        fresh_db.execute(
            """
            INSERT INTO customers
              (id, email, subscription_id, customer_stripe_id, license_key,
               intake_token, intake_token_exp, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'provisioned')
            """,
            (customer_id, "valid@example.com", sub_id,
             "cus_valid", license_key, str(uuid.uuid4()), 9999999999),
        )
        row = fresh_db.execute(
            "SELECT id, subscription_id, status FROM customers WHERE license_key = ?",
            (license_key,),
        ).fetchone()
        assert row is not None
        assert row["subscription_id"] == sub_id


# ── Migration idempotency ─────────────────────────────────────

class TestMigrationIdempotency:
    def test_migrate_schema_twice_is_safe(self, fresh_db, monkeypatch, tmp_path):
        """Running migrate_schema() a second time must not raise."""
        import ace_server
        ace_server.migrate_schema()  # second call — should be a no-op

    def test_webhook_log_idempotency_pattern(self, fresh_db):
        event_id = f"evt_{uuid.uuid4()}"
        for _ in range(2):
            fresh_db.execute(
                "INSERT OR IGNORE INTO webhook_log (event_id, event_type) VALUES (?, ?)",
                (event_id, "customer.subscription.created"),
            )
        count = fresh_db.execute(
            "SELECT COUNT(*) as c FROM webhook_log WHERE event_id = ?", (event_id,)
        ).fetchone()["c"]
        assert count == 1, "Idempotency: duplicate webhook_log insert produced more than one row"
