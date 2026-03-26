#!/usr/bin/env python3
"""
ACE (Autonomous Customer Engine) License Server
Validates customer licenses, manages subscriptions, sends verification emails.
"""

import os
import json
import sqlite3
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any
import hashlib
import secrets

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import httpx
from cryptography.fernet import Fernet

# ============================================================================
# Configuration
# ============================================================================

DB_PATH = os.getenv("ACE_DB_PATH", "/data/ace.db")
RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
FERNET_KEY = os.getenv("FERNET_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# Ensure /data directory exists
Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)

# ============================================================================
# Logging
# ============================================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# ============================================================================
# Database Setup
# ============================================================================

def init_db() -> None:
    """Initialize SQLite database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Licenses table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS licenses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        license_key TEXT UNIQUE NOT NULL,
        customer_email TEXT NOT NULL,
        customer_name TEXT,
        product TEXT NOT NULL,
        expires_at TEXT NOT NULL,
        created_at TEXT NOT NULL,
        status TEXT DEFAULT 'active',
        validation_count INTEGER DEFAULT 0,
        last_validated_at TEXT,
        metadata TEXT
    )
    """)
    
    # Validation log
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS validation_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        license_key TEXT NOT NULL,
        validated_at TEXT NOT NULL,
        ip_address TEXT,
        user_agent TEXT,
        valid BOOLEAN NOT NULL,
        reason TEXT,
        FOREIGN KEY (license_key) REFERENCES licenses(license_key)
    )
    """)
    
    # Subscription log
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS subscriptions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        license_key TEXT NOT NULL,
        stripe_subscription_id TEXT,
        stripe_customer_id TEXT,
        status TEXT DEFAULT 'pending',
        plan TEXT,
        amount_cents INTEGER,
        currency TEXT DEFAULT 'usd',
        billing_cycle_start TEXT,
        billing_cycle_end TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT,
        FOREIGN KEY (license_key) REFERENCES licenses(license_key)
    )
    """)
    
    conn.commit()
    conn.close()
    logger.info(f"Database initialized: {DB_PATH}")


# ============================================================================
# Models
# ============================================================================

class LicenseResponse(BaseModel):
    valid: bool
    license_key: Optional[str] = None
    customer_email: Optional[str] = None
    product: Optional[str] = None
    expires_at: Optional[str] = None
    days_remaining: Optional[int] = None
    message: str = ""


class LicenseCreateRequest(BaseModel):
    customer_email: str
    customer_name: str
    product: str
    months: int = 12


class LicenseCreateResponse(BaseModel):
    license_key: str
    customer_email: str
    expires_at: str
    message: str


# ============================================================================
# License Operations
# ============================================================================

def generate_license_key(email: str) -> str:
    """Generate a license key."""
    # Format: ACE-XXXXXXXXXXXXXXXX-XXXXXXXX
    timestamp = datetime.utcnow().timestamp()
    random_part = secrets.token_hex(8).upper()
    checksum = hashlib.sha256(f"{email}{timestamp}{random_part}".encode()).hexdigest()[:8].upper()
    return f"ACE-{random_part}-{checksum}"


def get_license(license_key: str) -> Optional[Dict[str, Any]]:
    """Fetch license from database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute(
        "SELECT * FROM licenses WHERE license_key = ?",
        (license_key,)
    )
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        return None
    
    return {
        "id": row[0],
        "license_key": row[1],
        "customer_email": row[2],
        "customer_name": row[3],
        "product": row[4],
        "expires_at": row[5],
        "created_at": row[6],
        "status": row[7],
        "validation_count": row[8],
        "last_validated_at": row[9],
        "metadata": json.loads(row[10]) if row[10] else {},
    }


def validate_license(license_key: str) -> tuple[bool, str]:
    """
    Validate a license key.
    Returns (is_valid, message)
    """
    license_data = get_license(license_key)
    
    if not license_data:
        return False, "License not found"
    
    if license_data["status"] != "active":
        return False, f"License is {license_data['status']}"
    
    expires_at = datetime.fromisoformat(license_data["expires_at"])
    now = datetime.utcnow()
    
    if now > expires_at:
        return False, "License expired"
    
    # Update validation count and timestamp
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE licenses SET validation_count = validation_count + 1, last_validated_at = ? WHERE license_key = ?",
        (now.isoformat(), license_key)
    )
    conn.commit()
    conn.close()
    
    return True, "License valid"


def create_license(email: str, name: str, product: str, months: int = 12) -> Dict[str, Any]:
    """Create a new license."""
    license_key = generate_license_key(email)
    created_at = datetime.utcnow()
    expires_at = created_at + timedelta(days=30*months)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute(
        """
        INSERT INTO licenses (license_key, customer_email, customer_name, product, expires_at, created_at, status)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (license_key, email, name, product, expires_at.isoformat(), created_at.isoformat(), "active")
    )
    
    conn.commit()
    conn.close()
    
    logger.info(f"License created: {license_key} for {email}")
    
    return {
        "license_key": license_key,
        "customer_email": email,
        "expires_at": expires_at.isoformat(),
        "message": "License created successfully"
    }


# ============================================================================
# Email Operations (Resend)
# ============================================================================

async def send_verification_email(email: str, license_key: str) -> bool:
    """Send license via email using Resend API."""
    if not RESEND_API_KEY:
        logger.warning("RESEND_API_KEY not configured, skipping email")
        return False
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.resend.com/emails",
                headers={
                    "Authorization": f"Bearer {RESEND_API_KEY}",
                },
                json={
                    "from": "noreply@intuitek.ai",
                    "to": email,
                    "subject": "Your IntuiTek¹ License Key",
                    "html": f"""
                    <h2>Welcome to IntuiTek¹</h2>
                    <p>Your license key is:</p>
                    <code style="background: #f5f5f5; padding: 10px; display: block; font-size: 14px;">
                        {license_key}
                    </code>
                    <p>Keep this safe. You'll need it to activate your IntuiTek¹ product.</p>
                    <p><a href="https://intuitek.ai">Learn more →</a></p>
                    """
                }
            )
            
            if response.status_code == 200:
                logger.info(f"License email sent to {email}")
                return True
            else:
                logger.error(f"Resend API error: {response.text}")
                return False
    
    except Exception as e:
        logger.error(f"Failed to send email: {e}")
        return False


# ============================================================================
# FastAPI Application
# ============================================================================

app = FastAPI(title="ACE License Server", version="1.0.0")


@app.on_event("startup")
async def startup_event():
    """Initialize database on startup."""
    init_db()
    logger.info("ACE License Server started")


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return JSONResponse({"status": "ok", "service": "ACE License Server"})


@app.get("/validate")
async def validate_endpoint(license_key: str = Query(...)) -> LicenseResponse:
    """
    Validate a license key.
    Usage: GET /validate?license_key=ACE-XXXXXXXX-XXXXXXXX
    """
    valid, reason = validate_license(license_key)
    
    if not valid:
        return LicenseResponse(valid=False, message=reason)
    
    license_data = get_license(license_key)
    expires_at = datetime.fromisoformat(license_data["expires_at"])
    days_remaining = (expires_at - datetime.utcnow()).days
    
    return LicenseResponse(
        valid=True,
        license_key=license_key,
        customer_email=license_data["customer_email"],
        product=license_data["product"],
        expires_at=license_data["expires_at"],
        days_remaining=max(0, days_remaining),
        message="License is valid"
    )


@app.post("/create")
async def create_endpoint(req: LicenseCreateRequest) -> LicenseCreateResponse:
    """
    Create a new license.
    POST /create with JSON body:
    {
        "customer_email": "user@example.com",
        "customer_name": "John Doe",
        "product": "agent-pro",
        "months": 12
    }
    """
    result = create_license(req.customer_email, req.customer_name, req.product, req.months)
    
    # Attempt to send verification email
    await send_verification_email(req.customer_email, result["license_key"])
    
    return LicenseCreateResponse(**result)


@app.get("/status/{license_key}")
async def status_endpoint(license_key: str) -> Dict[str, Any]:
    """Get detailed status of a license."""
    license_data = get_license(license_key)
    
    if not license_data:
        raise HTTPException(status_code=404, detail="License not found")
    
    expires_at = datetime.fromisoformat(license_data["expires_at"])
    days_remaining = (expires_at - datetime.utcnow()).days
    
    return {
        "license_key": license_key,
        "customer_email": license_data["customer_email"],
        "customer_name": license_data["customer_name"],
        "product": license_data["product"],
        "status": license_data["status"],
        "created_at": license_data["created_at"],
        "expires_at": license_data["expires_at"],
        "days_remaining": max(0, days_remaining),
        "validation_count": license_data["validation_count"],
        "last_validated_at": license_data["last_validated_at"]
    }


# ============================================================================
# Main
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    
    port = int(os.getenv("PORT", "8000"))
    host = os.getenv("HOST", "0.0.0.0")
    
    logger.info(f"Starting ACE License Server on {host}:{port}")
    uvicorn.run(app, host=host, port=port)
