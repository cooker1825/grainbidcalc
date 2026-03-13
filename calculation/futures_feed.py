"""
Futures price feed.

Priority order for get_latest_futures_price():
  1. SharePoint XLSX (CQG live via Excel Desktop) — prices already in USD/BU
  2. Database cache (futures_prices table)
  3. Raises ValueError if neither source has a price
"""

import logging

from config.contracts import CONTRACT_PREFIXES, MONTH_CODES
from db.connection import get_client

logger = logging.getLogger(__name__)

# Reverse lookup: month_number -> month_code  e.g. "03" -> "H"
_MONTH_NUM_TO_CODE = {v: k for k, v in MONTH_CODES.items()}

# CBOT grain contracts are quoted in cents/bushel — divide by 100 to get USD/BU.
# ICE canola (RS) is quoted in CAD/MT — no conversion needed.
_CENTS_PER_BUSHEL_PREFIXES = {"ZS", "ZC", "ZW", "KE"}


def _to_usd_bu(contract: str, raw_price: float) -> float:
    """Convert exchange-native price to USD/BU (or CAD/MT for canola)."""
    prefix = contract[:2]
    if prefix in _CENTS_PER_BUSHEL_PREFIXES:
        return raw_price / 100.0
    return raw_price  # canola: already CAD/MT


def _delivery_month_to_contract(commodity_name: str, delivery_month: str) -> str | None:
    """
    Convert commodity name + delivery_month (YYYY-MM) to a contract code.
    Example: ("soybeans", "2026-03") -> "ZSH26"
    """
    prefix = CONTRACT_PREFIXES.get(commodity_name)
    if not prefix:
        return None
    try:
        year_str  = delivery_month[2:4]   # "2026-03" -> "26"
        month_num = delivery_month[5:7]   # "2026-03" -> "03"
    except (IndexError, ValueError):
        return None
    month_code = _MONTH_NUM_TO_CODE.get(month_num)
    if not month_code:
        return None
    return f"{prefix}{month_code}{year_str}"


def _commodity_name_from_id(commodity_id: str) -> str | None:
    """Look up commodity name (e.g. 'soybeans') from its UUID."""
    try:
        result = (
            get_client()
            .table("commodities")
            .select("name")
            .eq("id", commodity_id)
            .maybe_single()
            .execute()
        )
        return result.data["name"] if result.data else None
    except Exception:
        return None


def get_latest_futures_price(commodity_id: str, delivery_month: str) -> float:
    """
    Get the most recent futures price for a commodity/delivery month.

    Tries Google Sheets first (user-entered), then falls back to DB cache.
    Raises ValueError if no price is available from either source.
    """
    # --- Source 1: SharePoint XLSX (CQG live, prices already in USD/BU) ---
    try:
        commodity_name = _commodity_name_from_id(commodity_id)
        if commodity_name:
            contract = _delivery_month_to_contract(commodity_name, delivery_month)
            if contract:
                from data.onedrive_reader import read_futures_prices
                prices = read_futures_prices()
                if contract in prices:
                    price = prices[contract]  # already USD/BU, no conversion
                    logger.debug("Futures %s from SharePoint: %.4f", contract, price)
                    return price
    except Exception as e:
        logger.warning("SharePoint futures lookup failed, falling back to DB: %s", e)

    # --- Source 2: DB cache ---
    result = (
        get_client()
        .table("futures_prices")
        .select("price")
        .order("fetched_at", desc=True)
        .limit(1)
        .execute()
    )
    if result.data:
        return float(result.data[0]["price"])

    raise ValueError(
        "No futures price available. "
        "Ensure CQG is running in Excel on the SharePoint file, or seed the DB manually."
    )


def fetch_and_cache_futures_prices() -> dict:
    """
    Read futures prices from SharePoint XLSX and cache in futures_prices table.
    Called by Celery beat task every 5 minutes during market hours.
    """
    from data.onedrive_reader import read_futures_prices

    prices = read_futures_prices()
    if not prices:
        return {"error": "No prices read from XLSX"}

    rows = [
        {"contract": contract, "price": price, "source": "xlsx"}
        for contract, price in prices.items()
    ]
    if rows:
        get_client().table("futures_prices").insert(rows).execute()

    return {"cached": len(rows)}
