"""
Scraper for DG Global cash bids (https://dgglobal.ca/cash-bids).

Bid data is embedded as JSON in the :desktop_bids attribute of a <cash-bids>
Vue component. No JavaScript rendering needed — plain HTTP GET.

Commodities:
  - Corn (Wet #2)     → corn
  - Soybeans (Crush)   → soybeans
  - Wheat (SRW #2)     → srw_wheat

Basis is CAD/BU. Destinations: Staples, Shetland, Princeton, Talbotville, Becher.
"""

import html
import json
import logging
import re

import httpx

logger = logging.getLogger(__name__)

URL = "https://dgglobal.ca/cash-bids"

# Map DG Global commodity names to our internal names
_COMMODITY_MAP = {
    "corn": "corn",
    "wet": "corn",
    "soybeans": "soybeans",
    "soybean": "soybeans",
    "crush": "soybeans",
    "wheat": "srw_wheat",
    "srw": "srw_wheat",
}


def _map_commodity(raw: str) -> str | None:
    """Map DG Global commodity string (e.g. 'Wet - # 2') to internal name."""
    lower = raw.lower()
    for key, val in _COMMODITY_MAP.items():
        if key in lower:
            return val
    return None


async def scrape() -> list[dict]:
    """
    Fetch and parse DG Global cash bids.

    Returns list of bid dicts ready for normalize → validate → store.
    """
    async with httpx.AsyncClient() as client:
        resp = await client.get(URL, timeout=30, follow_redirects=True)
        resp.raise_for_status()

    # Extract JSON from :desktop_bids attribute
    match = re.search(r':desktop_bids="([^"]*)"', resp.text)
    if not match:
        logger.warning("DG Global: could not find :desktop_bids in page")
        return []

    raw_json = html.unescape(match.group(1))
    try:
        sections = json.loads(raw_json)
    except json.JSONDecodeError as e:
        logger.warning("DG Global: failed to parse JSON: %s", e)
        return []

    bids = []
    for section in sections:
        offers = section.get("offers", [])
        for offer in offers:
            commodity = _map_commodity(offer.get("commodity", ""))
            if not commodity:
                continue

            basis_str = offer.get("basisPrice")
            delivery_raw = offer.get("deliveryPeriodRaw")  # "2026-03"
            delivery_label = offer.get("deliveryPeriod", "")  # "Mar 2026"
            destination = offer.get("destination", "")

            if basis_str is None or delivery_raw is None:
                continue

            # Only keep Talbotville bids
            if destination.lower().strip() != "talbotville":
                continue

            try:
                basis_value = float(basis_str)
            except (ValueError, TypeError):
                continue

            bids.append({
                "buyer_name": "DG Global",
                "commodity": commodity,
                "delivery_month": delivery_raw,
                "delivery_label": delivery_label,
                "basis_value": basis_value,
                "basis_unit": "CAD/BU",
                "destination": destination,
                "confidence": 0.99,
            })

    logger.info("DG Global: scraped %d bids", len(bids))
    return bids
