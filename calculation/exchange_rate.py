"""
USD/CAD exchange rate feed.
Primary: Bank of Canada API (free, daily).
Fallback: Latest cached rate from database.
"""

import httpx
from db.connection import get_client


BOC_API_URL = "https://www.bankofcanada.ca/valet/observations/FXUSDCAD/json?recent=1"


def get_latest_exchange_rate() -> float:
    """
    Get the most recent USD/CAD rate. Returns cached DB value.
    Call fetch_and_cache_exchange_rate() to refresh from Bank of Canada.
    """
    client = get_client()
    result = (
        client.table("exchange_rates")
        .select("rate")
        .order("fetched_at", desc=True)
        .limit(1)
        .execute()
    )
    if result.data:
        return float(result.data[0]["rate"])
    raise ValueError("No exchange rate cached. Run fetch_and_cache_exchange_rate() first.")


def fetch_and_cache_exchange_rate() -> float:
    """
    Fetch USD/CAD rate from Bank of Canada API and cache it.
    Called by Celery beat task every 30 minutes during market hours.
    """
    response = httpx.get(BOC_API_URL, timeout=10)
    response.raise_for_status()
    data = response.json()
    obs = data["observations"][-1]
    rate = float(obs["FXUSDCAD"]["v"])

    client = get_client()
    client.table("exchange_rates").insert({"pair": "USD/CAD", "rate": rate}).execute()

    return rate
