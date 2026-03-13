"""
Scraper for Hensall District Co-op cash bids via DTN API.

HDC uses a DTN widget on their web page. The underlying API is directly
accessible with the public API key embedded in their page source.

API: https://api.dtn.com/markets/sites/{siteId}/cash-bids
Site ID: e0010801

Commodities: #2 Yellow Corn, Soybeans, Soft Red Wheat, Hard Red Wheat,
             Hard Red Spring Wheat, Soft White Wheat

IMPORTANT: DTN returns prices in USD/BU. The basis_unit is set accordingly
so the normalizer converts to CAD/BU using the current exchange rate.
"""

import logging

import httpx

logger = logging.getLogger(__name__)

_API_URL = "https://api.dtn.com/markets/sites/e0010801/cash-bids"
_API_KEY = "XTyJHKfc0BlMM4zBa0bvUOL6GGYKDq22"
_REFERER = "https://hensallco-op.ca/Cash-Bids.htm"

# Map DTN commodity names to our internal names
_COMMODITY_MAP = {
    "#2 yellow corn": "corn",
    "corn": "corn",
    "soybeans": "soybeans",
    "soybean": "soybeans",
    "soft red wheat": "srw_wheat",
    "hard red wheat": "hrw_wheat",
    "hard red winter wheat": "hrw_wheat",
    "hard red spring wheat": "hrw_wheat",
    "soft white wheat": "swr_wheat",
}


def _map_commodity(raw: str) -> str | None:
    """Map DTN commodity display name to internal name."""
    lower = raw.lower().strip()
    for key, val in _COMMODITY_MAP.items():
        if key in lower:
            return val
    return None


def _parse_delivery_month(record: dict) -> str | None:
    """
    Extract YYYY-MM delivery month from DTN record.

    Prefers deliveryPeriod.start (ISO datetime), falls back to contractMonthCode (YYYYMMDD).
    """
    period = record.get("deliveryPeriod", {})
    start = period.get("start", "")
    if start and len(start) >= 7:
        return start[:7]  # "2026-04-01T05:00:00Z" → "2026-04"

    code = record.get("contractMonthCode", "")
    if code and len(code) >= 6:
        return f"{code[:4]}-{code[4:6]}"  # "20260430" → "2026-04"

    return None


async def scrape() -> list[dict]:
    """
    Fetch and parse HDC cash bids from DTN API.

    Returns list of bid dicts ready for normalize → validate → store.
    """
    headers = {
        "apikey": _API_KEY,
        "Referer": _REFERER,
        "Origin": "https://hensallco-op.ca",
    }

    async with httpx.AsyncClient() as client:
        resp = await client.get(_API_URL, headers=headers, timeout=30)
        resp.raise_for_status()

    records = resp.json()
    if not isinstance(records, list):
        logger.warning("HDC/DTN: unexpected response format")
        return []

    bids = []
    for record in records:
        commodity_name = record.get("commodityDisplayName", "")
        commodity = _map_commodity(commodity_name)
        if not commodity:
            continue

        delivery_month = _parse_delivery_month(record)
        if not delivery_month:
            continue

        # DTN provides primaryPrice with per-bushel breakdown
        primary = record.get("primaryPrice", {})
        basis_price = primary.get("basisPrice")
        if basis_price is None:
            basis_price = record.get("basisPrice")
        if basis_price is None:
            continue

        try:
            basis_value = float(basis_price)
        except (ValueError, TypeError):
            continue

        delivery_label = record.get("contractDeliveryLabel", "")
        location = record.get("location", {})
        destination = location.get("name", "Hensall")

        bids.append({
            "buyer_name": "Hensall District Co-op",
            "commodity": commodity,
            "delivery_month": delivery_month,
            "delivery_label": delivery_label,
            "basis_value": basis_value,
            "basis_unit": "USD/BU",
            "destination": destination,
            "confidence": 0.99,
        })

    logger.info("HDC: scraped %d bids from DTN API", len(bids))
    return bids
