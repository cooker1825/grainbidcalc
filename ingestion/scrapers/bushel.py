"""
Scraper for Ingredion cash bids via Bushel aggregator API.

Ingredion uses the Bushel platform for bid management. The bids are served by
the aggregator endpoint, which requires a Keycloak Bearer token. Tokens are
refreshed via the NextAuth session cookie stored in data/bushel_token.json.

API: POST https://api.bushelpowered.com/api/markets/aggregator/bids/v1/GetBidsList
Auth: Bearer token + App-Company: ingredion header
Token refresh: via Playwright headless call to portal session endpoint

Ontario locations of interest: London, Cardinal
Commodities: CEY Dent (corn), NGM CEY (non-GMO corn)
Basis unit: USD/BU (derived from bid/futures relationship)
"""

import json
import logging
import re
import time
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

TOKEN_FILE = Path(__file__).resolve().parent.parent.parent / "data" / "bushel_token.json"
AGGREGATOR_URL = "https://api.bushelpowered.com/api/markets/aggregator/bids/v1/GetBidsList"

# Ontario locations — London only for Ingredion tab
_TARGET_LOCATIONS = {"london"}

# Map Bushel commodity names to our internal names
_COMMODITY_MAP = {
    "cey dent": "corn",
    "ngm cey": "corn",  # Non-GMO corn — still corn for our purposes
    "yellow #2 corn": "corn",
    "corn": "corn",
}

# CME month code → month number
_MONTH_CODES = {
    "F": "01", "G": "02", "H": "03", "J": "04", "K": "05", "M": "06",
    "N": "07", "Q": "08", "U": "09", "V": "10", "X": "11", "Z": "12",
}


def _load_tokens() -> dict:
    """Load saved token data from disk."""
    if not TOKEN_FILE.exists():
        return {}
    try:
        return json.loads(TOKEN_FILE.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def _save_tokens(data: dict) -> None:
    """Save token data to disk."""
    data["saved_at"] = time.time()
    TOKEN_FILE.write_text(json.dumps(data, indent=2))


def _refresh_access_token(tokens: dict) -> str | None:
    """
    Use stored session cookies to get a fresh access token.

    Runs Playwright in a subprocess to avoid conflict with the asyncio event loop.
    Returns the new access token, or None if refresh fails.
    Updates the token file with rotated session cookies.
    """
    if not tokens.get("session_cookies") and not tokens.get("session_cookie_name"):
        logger.warning("Bushel: no session cookies stored, cannot refresh")
        return None

    try:
        import subprocess
        result = subprocess.run(
            ["/opt/grainbidcalc/venv/bin/python", "-c", """
import json, sys
sys.path.insert(0, "/opt/grainbidcalc")
from ingestion.scrapers.bushel_login import refresh_session
tokens = json.loads(sys.stdin.read())
result = refresh_session(tokens)
if result:
    print(json.dumps(result))
else:
    print("{}")
"""],
            input=json.dumps(tokens),
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            logger.error("Bushel: refresh subprocess error: %s", result.stderr)
            return None

        data = json.loads(result.stdout.strip())
        if data.get("access_token"):
            _save_tokens(data)
            logger.info("Bushel: session refreshed, new access token obtained")
            return data["access_token"]
        else:
            logger.warning("Bushel: session refresh failed (cookie may be expired)")
            return None
    except Exception as e:
        logger.error("Bushel: session refresh error: %s", e)
        return None


def _get_access_token() -> str | None:
    """
    Get a valid access token. Tries stored token first, refreshes if needed.
    """
    tokens = _load_tokens()
    access_token = tokens.get("access_token")

    if access_token:
        # Check if the JWT is expired by decoding the payload
        try:
            import base64
            payload_b64 = access_token.split(".")[1]
            # Add padding
            payload_b64 += "=" * (4 - len(payload_b64) % 4)
            payload = json.loads(base64.urlsafe_b64decode(payload_b64))
            exp = payload.get("exp", 0)
            if time.time() < exp - 30:  # 30s buffer
                return access_token
        except Exception:
            pass  # Can't decode — try refresh

    # Token expired or missing — refresh via session cookie
    logger.info("Bushel: access token expired, refreshing via session...")
    return _refresh_access_token(tokens)


def _parse_delivery_month(description: str, futures_symbol: str) -> str | None:
    """
    Parse delivery month from bid description or futures symbol.

    Descriptions like "Aug 2026", "Sep 2026", "LH Oct 25", "Nov 2026 Wet",
    "Jan 2027", "Apr-Jun 2026".

    Falls back to futures symbol like "ZCN26" → 2026-07.
    """
    # Try description first: "Aug 2026", "Sep 2026", "Nov 2026 Wet"
    month_names = {
        "jan": "01", "feb": "02", "mar": "03", "apr": "04", "may": "05", "jun": "06",
        "jul": "07", "aug": "08", "sep": "09", "sept": "09", "oct": "10", "nov": "11", "dec": "12",
    }

    desc_lower = description.lower().strip()

    # Handle "LH Oct 25" → "Oct 25" → October 2025
    desc_lower = re.sub(r'^[fl]h\s+', '', desc_lower)

    # Match "Month YYYY" or "Month YY"
    m = re.match(r'(\w{3,4})\s+(\d{4})', desc_lower)
    if m:
        month_str = m.group(1)[:3]
        year = m.group(2)
        month_num = month_names.get(month_str)
        if month_num:
            return f"{year}-{month_num}"

    m = re.match(r'(\w{3,4})\s+(\d{2})(?:\s|$)', desc_lower)
    if m:
        month_str = m.group(1)[:3]
        year_short = m.group(2)
        year = f"20{year_short}"
        month_num = month_names.get(month_str)
        if month_num:
            return f"{year}-{month_num}"

    # Handle range descriptions like "Apr-Jun 2026" → take start month
    m = re.match(r'(\w{3})[/-](\w{3})\s+(\d{4})', desc_lower)
    if m:
        month_str = m.group(1)[:3]
        year = m.group(3)
        month_num = month_names.get(month_str)
        if month_num:
            return f"{year}-{month_num}"

    # Handle "Aug/Sept 2026" style
    m = re.match(r'(\w{3,4})/(\w{3,4})\s+(\d{4})', desc_lower)
    if m:
        month_str = m.group(1)[:3]
        year = m.group(3)
        month_num = month_names.get(month_str)
        if month_num:
            return f"{year}-{month_num}"

    # Handle "April-Jun 2027" (full month name)
    m = re.match(r'(\w+?)[/-]', desc_lower)
    if m:
        month_str = m.group(1)[:3]
        month_num = month_names.get(month_str)
        # Find year
        year_m = re.search(r'(\d{4})', desc_lower)
        if month_num and year_m:
            return f"{year_m.group(1)}-{month_num}"

    # Fall back to futures symbol: ZCN26 → July 2026
    if futures_symbol and len(futures_symbol) >= 4:
        symbol = futures_symbol.upper()
        # Standard: ZCN26
        m2 = re.match(r'[A-Z]{2}([FGHJKMNQUVXZ])(\d{2})', symbol)
        if m2:
            month_code = m2.group(1)
            year_short = m2.group(2)
            month_num = _MONTH_CODES.get(month_code)
            if month_num:
                return f"20{year_short}-{month_num}"

    return None


def _map_commodity(name: str) -> str | None:
    """Map Bushel commodity name to internal name."""
    lower = name.lower().strip()
    for key, val in _COMMODITY_MAP.items():
        if key in lower:
            return val
    return None


async def scrape() -> list[dict]:
    """
    Fetch and parse Ingredion cash bids from Bushel aggregator API.

    Filters to Ontario locations (London, Cardinal) only.
    Returns list of bid dicts ready for normalize → validate → store.
    """
    access_token = _get_access_token()
    if not access_token:
        logger.error("Bushel: no valid access token available. Run bushel_login.py first.")
        return []

    headers = {
        "accept": "*/*",
        "app-company": "ingredion",
        "authorization": f"Bearer {access_token}",
        "content-type": "application/json",
        "origin": "https://portal.bushelpowered.com",
        "referer": "https://portal.bushelpowered.com/",
    }

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            AGGREGATOR_URL,
            headers=headers,
            json={"locationSourceIds": None},
            timeout=30,
        )

        if resp.status_code == 401:
            logger.warning("Bushel: 401 — token expired, attempting refresh...")
            tokens = _load_tokens()
            new_token = _refresh_access_token(tokens)
            if new_token:
                headers["authorization"] = f"Bearer {new_token}"
                resp = await client.post(
                    AGGREGATOR_URL,
                    headers=headers,
                    json={"locationSourceIds": None},
                    timeout=30,
                )
            else:
                logger.error("Bushel: refresh failed, cannot fetch bids")
                return []

        resp.raise_for_status()

    data = resp.json()
    locations = data.get("locations", [])

    bids = []
    for loc in locations:
        loc_name = loc.get("name", "")
        if loc_name.lower() not in _TARGET_LOCATIONS:
            continue

        for group in loc.get("groups", []):
            commodity_name = group.get("displayName", "")
            commodity = _map_commodity(commodity_name)
            if not commodity:
                logger.debug("Bushel: skipping unknown commodity %r at %s", commodity_name, loc_name)
                continue

            for bid in group.get("bids", []):
                description = bid.get("description", "")
                basis_str = bid.get("basisPrice")
                futures_symbol = bid.get("futuresSymbol", "")

                if basis_str is None:
                    continue

                try:
                    basis_value = float(basis_str)
                except (ValueError, TypeError):
                    continue

                delivery_month = _parse_delivery_month(description, futures_symbol)
                if not delivery_month:
                    logger.debug("Bushel: could not parse delivery month from %r / %s", description, futures_symbol)
                    continue

                bids.append({
                    "buyer_name": "Ingredion",
                    "commodity": commodity,
                    "delivery_month": delivery_month,
                    "delivery_label": description,
                    "basis_value": basis_value,
                    "basis_unit": "USD/BU",
                    "destination": loc_name,
                    "confidence": 0.99,
                })

    logger.info("Bushel/Ingredion: scraped %d bids from %d locations",
                len(bids), sum(1 for l in locations if l.get("name", "").lower() in _TARGET_LOCATIONS))
    return bids
