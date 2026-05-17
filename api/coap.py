"""
IntuiTek¹ — COAP (City Opportunity Analysis Pipeline)
One-time report or monthly subscription product.

Flow:
  POST /coap/checkout           → Stripe Checkout Session URL
  GET  /coap/form/{token}       → HTML intake form (city + state)
  POST /coap/submit/{token}     → validate payment, run pipeline, deliver email

Stripe products:
  Per-report:  prod_UWwjwJyJ6erjxB / price_1TXsq1BDuMBkXxIDm7oXAYIj  ($49 one-time)
  Monthly:     prod_UWwjJYFMGywsPV / price_1TXsqDBDuMBkXxID7mqaOg7E  ($149/mo)

DB table: coap_sessions (added via init_db)
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

log = logging.getLogger("ace.coap")

router = APIRouter(prefix="/coap", tags=["coap"])

# ── CONFIG ───────────────────────────────────────────────────
RESEND_API_KEY           = os.environ.get("RESEND_API_KEY", "")
ANTHROPIC_API_KEY        = os.environ.get("ANTHROPIC_API_KEY", "")
COAP_PRICE_PER_REPORT    = os.environ.get("COAP_PRICE_PER_REPORT", "price_1TXsq1BDuMBkXxIDm7oXAYIj")
COAP_PRICE_MONTHLY       = os.environ.get("COAP_PRICE_MONTHLY", "price_1TXsqDBDuMBkXxID7mqaOg7E")
ACE_BASE_URL             = os.environ.get("ACE_BASE_URL", "https://ace-license-server-production.up.railway.app")
CLAUDE_MODEL             = "claude-sonnet-4-6"

COAP_DIRECTIVE = """\
You are running the COAP v1.2 "Money Talks" City Opportunity Analysis Pipeline for IntuiTek¹ | Aegis Strategy Division.

MISSION: Produce a publication-ready briefing that selects, evidences, and financially models the highest-profit new-business concept for the given city. No social-good bias — pure return on investment.

You have been provided structured market data about the city. Your task:

1. MARKET LANDSCAPE ANALYSIS
   - Summarize demographics, income levels, economic health
   - Identify existing business saturation by category
   - Note underserved demand gaps

2. OPPORTUNITY IDENTIFICATION
   - List the top 5 business concept candidates
   - For each: state why the city's data supports this concept
   - Score each on: demand gap, capital intensity, barrier to entry, local competition, revenue potential

3. WINNING CONCEPT SELECTION
   - Select the single highest-ROI opportunity
   - Justify with specific data points from the provided market data
   - Estimate startup capital range (low/high)
   - Project Year 1 revenue range
   - Identify the 3 biggest risks

4. EXECUTION SUMMARY
   - First 90 days action plan (5–7 steps)
   - Key local resources or advantages to leverage

Format: Markdown with clear headers. Be specific — use the actual numbers from the data. This is a professional consulting deliverable.

CITY: {city}, {state}

MARKET DATA:
{market_data_json}
"""


# ── DATABASE ─────────────────────────────────────────────────
_DB_PATH = os.environ.get("ACE_DB_PATH", "/data/ace.db")


def _get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(_DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def ensure_coap_table():
    conn = _get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS coap_sessions (
            token TEXT PRIMARY KEY,
            email TEXT NOT NULL,
            tier TEXT NOT NULL DEFAULT 'per_report',
            stripe_session_id TEXT,
            city TEXT,
            state TEXT,
            status TEXT DEFAULT 'pending_payment',
            created_at INTEGER NOT NULL,
            completed_at INTEGER
        )
    """)
    conn.commit()
    conn.close()


def _verify_stripe_payment(session_id: str) -> Optional[str]:
    """Return customer email if session is paid, else None."""
    try:
        session = stripe.checkout.Session.retrieve(session_id, expand=["customer"])
        if session.payment_status in ("paid", "no_payment_required"):
            email = (session.customer_details.email
                     if session.customer_details else None)
            return email
        return None
    except stripe.error.StripeError as exc:
        log.error("Stripe session lookup failed: %s", exc)
        return None


# ── DATA COLLECTION ──────────────────────────────────────────

def _collect_market_data(city: str, state: str) -> dict:
    """Collect Census, BLS, and OSM data for the city."""
    data: dict = {"city": city, "state": state}

    # Census Reporter — ACS 5-year estimates
    try:
        census_url = (
            f"https://censusreporter.org/profiles/16000US{_fips_lookup(city, state)}.json"
        )
        # Use geocoding to get Census place FIPS via Nominatim
        geo_resp = httpx.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": f"{city}, {state}, USA", "format": "json", "limit": 1},
            headers={"User-Agent": "IntuiTek1-COAP/1.2 (kyle@intuitek.ai)"},
            timeout=15,
        )
        geo_data = geo_resp.json()
        if geo_data:
            data["lat"] = float(geo_data[0]["lat"])
            data["lon"] = float(geo_data[0]["lon"])
            data["display_name"] = geo_data[0].get("display_name", f"{city}, {state}")
    except Exception as exc:
        log.warning("Geocoding failed: %s", exc)

    # Census ACS via direct API
    try:
        census_resp = httpx.get(
            "https://api.census.gov/data/2022/acs/acs5",
            params={
                "get": "NAME,B01003_001E,B19013_001E,B17001_002E,B17001_001E,B25077_001E",
                "for": "place:*",
                "in": f"state:{_state_fips(state)}",
            },
            timeout=20,
        )
        rows = census_resp.json()
        # Match city name
        for row in rows[1:]:
            if city.lower() in row[0].lower():
                total_pop = int(row[1]) if row[1] and row[1] != "-666666666" else None
                median_income = int(row[2]) if row[2] and row[2] != "-666666666" else None
                poverty_count = int(row[3]) if row[3] and row[3] != "-666666666" else None
                total_for_poverty = int(row[4]) if row[4] and row[4] != "-666666666" else None
                median_home_value = int(row[5]) if row[5] and row[5] != "-666666666" else None

                data["census"] = {
                    "population": total_pop,
                    "median_household_income": median_income,
                    "poverty_rate_pct": round(poverty_count / total_for_poverty * 100, 1) if poverty_count and total_for_poverty else None,
                    "median_home_value": median_home_value,
                }
                break
    except Exception as exc:
        log.warning("Census ACS failed: %s", exc)

    # BLS LAUS — state unemployment
    try:
        state_code = _state_bls_code(state)
        bls_resp = httpx.get(
            f"https://api.bls.gov/publicAPI/v2/timeseries/data/LASST{state_code}0000000000003",
            timeout=15,
        )
        bls_data = bls_resp.json()
        series = bls_data.get("Results", {}).get("series", [])
        if series and series[0].get("data"):
            latest = series[0]["data"][0]
            data["bls"] = {
                "state_unemployment_pct": float(latest["value"]),
                "period": f"{latest['year']}-{latest['period']}",
            }
    except Exception as exc:
        log.warning("BLS LAUS failed: %s", exc)

    # OSM / Overpass — business category counts
    try:
        lat = data.get("lat")
        lon = data.get("lon")
        if lat and lon:
            radius_m = 10000  # 10 km
            categories = {
                "fast_food": 'amenity="fast_food"',
                "restaurant": 'amenity="restaurant"',
                "grocery": 'shop="supermarket"',
                "gas_station": 'amenity="fuel"',
                "auto_repair": 'shop="car_repair"',
                "car_wash": 'amenity="car_wash"',
                "hotel": 'tourism="hotel"',
                "motel": 'tourism="motel"',
                "pharmacy": 'amenity="pharmacy"',
                "bank": 'amenity="bank"',
                "gym": 'leisure="fitness_centre"',
                "laundromat": 'shop="laundry"',
                "hardware": 'shop="hardware"',
                "clothing": 'shop="clothes"',
                "salon": 'shop="hairdresser"',
                "dentist": 'amenity="dentist"',
                "child_care": 'amenity="childcare"',
                "brewery_bar": 'amenity="bar"',
            }
            osm_counts = {}
            for name, tag in categories.items():
                query = (
                    f"[out:json][timeout:25];"
                    f"node[{tag}](around:{radius_m},{lat},{lon});"
                    f"out count;"
                )
                r = httpx.post(
                    "https://overpass-api.de/api/interpreter",
                    data={"data": query},
                    timeout=30,
                )
                result = r.json()
                count = result.get("elements", [{}])[0].get("tags", {}).get("nodes", 0)
                osm_counts[name] = int(count)
                time.sleep(0.3)  # be polite to Overpass
            data["osm_business_counts"] = osm_counts
    except Exception as exc:
        log.warning("OSM/Overpass failed: %s", exc)

    return data


def _fips_lookup(city: str, state: str) -> str:
    return ""


def _state_fips(state: str) -> str:
    FIPS = {
        "AL": "01", "AK": "02", "AZ": "04", "AR": "05", "CA": "06",
        "CO": "08", "CT": "09", "DE": "10", "FL": "12", "GA": "13",
        "HI": "15", "ID": "16", "IL": "17", "IN": "18", "IA": "19",
        "KS": "20", "KY": "21", "LA": "22", "ME": "23", "MD": "24",
        "MA": "25", "MI": "26", "MN": "27", "MS": "28", "MO": "29",
        "MT": "30", "NE": "31", "NV": "32", "NH": "33", "NJ": "34",
        "NM": "35", "NY": "36", "NC": "37", "ND": "38", "OH": "39",
        "OK": "40", "OR": "41", "PA": "42", "RI": "44", "SC": "45",
        "SD": "46", "TN": "47", "TX": "48", "UT": "49", "VT": "50",
        "VA": "51", "WA": "53", "WV": "54", "WI": "55", "WY": "56",
        "DC": "11",
    }
    return FIPS.get(state.upper(), "29")


def _state_bls_code(state: str) -> str:
    CODES = {
        "AL": "01", "AK": "02", "AZ": "04", "AR": "05", "CA": "06",
        "CO": "08", "CT": "09", "DE": "10", "FL": "12", "GA": "13",
        "HI": "15", "ID": "16", "IL": "17", "IN": "18", "IA": "19",
        "KS": "20", "KY": "21", "LA": "22", "ME": "23", "MD": "24",
        "MA": "25", "MI": "26", "MN": "27", "MS": "28", "MO": "29",
        "MT": "30", "NE": "31", "NV": "32", "NH": "33", "NJ": "34",
        "NM": "35", "NY": "36", "NC": "37", "ND": "38", "OH": "39",
        "OK": "40", "OR": "41", "PA": "42", "RI": "44", "SC": "45",
        "SD": "46", "TN": "47", "TX": "48", "UT": "49", "VT": "50",
        "VA": "51", "WA": "53", "WV": "54", "WI": "55", "WY": "56",
        "DC": "11",
    }
    return CODES.get(state.upper(), "29")


# ── CLAUDE ANALYSIS ──────────────────────────────────────────

def _run_coap_analysis(city: str, state: str, market_data: dict) -> str:
    """Call Claude Sonnet via Anthropic API to generate the COAP report."""
    import json
    prompt = COAP_DIRECTIVE.format(
        city=city,
        state=state,
        market_data_json=json.dumps(market_data, indent=2),
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
            "max_tokens": 4096,
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=180,
    )
    resp.raise_for_status()
    data = resp.json()
    return data["content"][0]["text"]


# ── EMAIL DELIVERY ───────────────────────────────────────────

def _deliver_report(email: str, city: str, state: str, report_md: str):
    """Email the COAP report via Resend as styled HTML."""
    # Convert minimal markdown to HTML (headers + paragraphs)
    import re
    lines = report_md.split("\n")
    html_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("### "):
            html_lines.append(f"<h3>{stripped[4:]}</h3>")
        elif stripped.startswith("## "):
            html_lines.append(f"<h2>{stripped[3:]}</h2>")
        elif stripped.startswith("# "):
            html_lines.append(f"<h1>{stripped[2:]}</h1>")
        elif stripped.startswith("- "):
            html_lines.append(f"<li>{stripped[2:]}</li>")
        elif stripped:
            html_lines.append(f"<p>{stripped}</p>")
        else:
            html_lines.append("<br>")

    body_html = f"""
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  body {{ font-family: Georgia, serif; max-width: 700px; margin: 0 auto; padding: 24px; color: #222; }}
  h1 {{ font-size: 1.6em; border-bottom: 2px solid #222; padding-bottom: 8px; }}
  h2 {{ font-size: 1.3em; margin-top: 28px; color: #1a1a1a; }}
  h3 {{ font-size: 1.1em; color: #333; }}
  p {{ line-height: 1.7; }}
  li {{ margin-bottom: 4px; line-height: 1.6; }}
  .footer {{ margin-top: 40px; padding-top: 16px; border-top: 1px solid #ddd; font-size: 0.85em; color: #666; }}
</style>
</head>
<body>
<h1>COAP Report: {city}, {state}</h1>
<p><em>IntuiTek¹ | Aegis Strategy Division &mdash; COAP v1.2 &ldquo;Money Talks&rdquo;</em></p>
{"".join(html_lines)}
<div class="footer">
  <p>Generated by Aegis &mdash; IntuiTek¹ City Opportunity Analysis Pipeline<br>
  © W. Kyle Million (K¹) / IntuiTek¹ &mdash; <a href="https://intuitek.ai">intuitek.ai</a></p>
</div>
</body>
</html>
"""

    resp = httpx.post(
        "https://api.resend.com/emails",
        headers={
            "Authorization": f"Bearer {RESEND_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "from": "Aegis <aegis@intuitek.ai>",
            "to": [email],
            "subject": f"Your COAP Report: {city}, {state} — Market Opportunity Analysis",
            "html": body_html,
        },
        timeout=30,
    )
    resp.raise_for_status()
    log.info("COAP report delivered to %s for %s, %s", email, city, state)


# ── ROUTES ───────────────────────────────────────────────────

class CheckoutRequest(BaseModel):
    email: EmailStr
    tier: str = "per_report"  # "per_report" or "monthly"


@router.post("/checkout")
async def coap_checkout(body: CheckoutRequest):
    """Create Stripe Checkout Session for COAP — per-report or monthly."""
    ensure_coap_table()

    tier = body.tier.lower()
    if tier not in ("per_report", "monthly"):
        raise HTTPException(status_code=400, detail="tier must be 'per_report' or 'monthly'")

    price_id = COAP_PRICE_PER_REPORT if tier == "per_report" else COAP_PRICE_MONTHLY
    mode = "payment" if tier == "per_report" else "subscription"
    token = str(uuid.uuid4())

    try:
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            mode=mode,
            line_items=[{"price": price_id, "quantity": 1}],
            customer_email=body.email,
            success_url=f"{ACE_BASE_URL}/coap/form/{token}",
            cancel_url=f"{ACE_BASE_URL}/",
            metadata={"coap_token": token, "tier": tier},
        )
    except stripe.error.StripeError as exc:
        log.error("Stripe checkout creation failed: %s", exc)
        raise HTTPException(status_code=502, detail="Payment session creation failed")

    conn = _get_db()
    conn.execute(
        """INSERT INTO coap_sessions (token, email, tier, stripe_session_id, status, created_at)
           VALUES (?, ?, ?, ?, 'pending_payment', ?)""",
        (token, body.email, tier, session.id, int(time.time())),
    )
    conn.commit()
    conn.close()

    return {"checkout_url": session.url}


@router.get("/form/{token}", response_class=HTMLResponse)
async def coap_form(token: str):
    """Show city/state intake form after payment."""
    ensure_coap_table()
    conn = _get_db()
    row = conn.execute(
        "SELECT token, email, tier, stripe_session_id, status FROM coap_sessions WHERE token = ?",
        (token,),
    ).fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="Session not found")

    if row["status"] == "delivered":
        return HTMLResponse(content=_done_page(row["email"]))

    # Verify payment
    paid_email = _verify_stripe_payment(row["stripe_session_id"])
    if not paid_email:
        return HTMLResponse(content=_payment_pending_page())

    return HTMLResponse(content=_intake_form_html(token, row["email"], row["tier"]))


@router.post("/submit/{token}", response_class=HTMLResponse)
async def coap_submit(token: str, request: Request):
    """Accept form POST, validate payment, run COAP pipeline, deliver email report."""
    ensure_coap_table()
    conn = _get_db()
    row = conn.execute(
        "SELECT token, email, tier, stripe_session_id, status FROM coap_sessions WHERE token = ?",
        (token,),
    ).fetchone()

    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Session not found")

    if row["status"] == "delivered":
        conn.close()
        return HTMLResponse(content=_done_page(row["email"]))

    paid_email = _verify_stripe_payment(row["stripe_session_id"])
    if not paid_email:
        conn.close()
        raise HTTPException(status_code=402, detail="Payment not confirmed")

    form = await request.form()
    city = str(form.get("city", "")).strip().title()
    state = str(form.get("state", "")).strip().upper()[:2]

    if not city or not state:
        conn.close()
        raise HTTPException(status_code=400, detail="city and state are required")

    # Mark in-progress to prevent double-submission
    conn.execute(
        "UPDATE coap_sessions SET status='generating', city=?, state=? WHERE token=?",
        (city, state, token),
    )
    conn.commit()
    conn.close()

    try:
        market_data = _collect_market_data(city, state)
        report_md = _run_coap_analysis(city, state, market_data)
        _deliver_report(paid_email, city, state, report_md)

        conn2 = _get_db()
        conn2.execute(
            "UPDATE coap_sessions SET status='delivered', completed_at=? WHERE token=?",
            (int(time.time()), token),
        )
        conn2.commit()
        conn2.close()

        log.info("COAP complete: %s, %s → %s", city, state, paid_email)

    except Exception as exc:
        log.error("COAP generation failed for token %s: %s", token, exc)
        conn3 = _get_db()
        conn3.execute(
            "UPDATE coap_sessions SET status='error' WHERE token=?",
            (token,),
        )
        conn3.commit()
        conn3.close()
        raise HTTPException(status_code=500, detail="Report generation failed — we've been notified")

    return HTMLResponse(content=_done_page(paid_email))


# ── HTML TEMPLATES ───────────────────────────────────────────

def _intake_form_html(token: str, email: str, tier: str) -> str:
    tier_label = "Monthly Subscription" if tier == "monthly" else "Per Report"
    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>COAP — City Analysis Request</title>
<style>
  body {{ font-family: system-ui, sans-serif; max-width: 500px; margin: 60px auto; padding: 24px; color: #111; }}
  h1 {{ font-size: 1.4em; }}
  label {{ display: block; margin-top: 16px; font-weight: 600; font-size: 0.9em; }}
  input {{ width: 100%; padding: 10px; margin-top: 6px; border: 1px solid #ccc; border-radius: 4px; font-size: 1em; box-sizing: border-box; }}
  button {{ margin-top: 24px; width: 100%; padding: 14px; background: #000; color: #fff; border: none; border-radius: 4px; font-size: 1em; cursor: pointer; }}
  .note {{ font-size: 0.82em; color: #666; margin-top: 8px; }}
  .tier {{ font-size: 0.85em; color: #444; margin-bottom: 20px; }}
</style>
</head>
<body>
<h1>City Opportunity Analysis</h1>
<p class="tier">Plan: {tier_label} &mdash; Delivering to: {email}</p>
<p>Enter the U.S. city you want analyzed. We'll collect live Census, BLS, and business data, then generate your opportunity report.</p>
<form method="POST" action="/coap/submit/{token}">
  <label>City *</label>
  <input type="text" name="city" placeholder="e.g. Doniphan" required>
  <label>State (2-letter code) *</label>
  <input type="text" name="state" placeholder="e.g. MO" maxlength="2" required>
  <button type="submit">Generate My Report</button>
  <p class="note">Report arrives in your inbox within 10 minutes. Data sources: U.S. Census ACS, BLS LAUS, OpenStreetMap.</p>
</form>
</body>
</html>"""


def _payment_pending_page() -> str:
    return """<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>Payment Pending</title></head>
<body style="font-family:system-ui;max-width:500px;margin:60px auto;padding:24px">
<h2>Payment Confirming</h2>
<p>Your payment is still being confirmed by Stripe. Please wait 30 seconds and refresh this page.</p>
<p><a href="javascript:location.reload()">Refresh</a></p>
</body>
</html>"""


def _done_page(email: str) -> str:
    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>Report On Its Way</title></head>
<body style="font-family:system-ui;max-width:500px;margin:60px auto;padding:24px">
<h2>Your report is on its way.</h2>
<p>Check <strong>{email}</strong> — your City Opportunity Analysis will arrive within 10 minutes.</p>
<p>Built by Aegis &mdash; <a href="https://intuitek.ai">IntuiTek¹</a></p>
</body>
</html>"""
