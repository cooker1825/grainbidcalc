"""
CQG API integration for live futures prices.
Falls back to most recent cached price from the database if the API is unavailable.
"""

# TODO: Implement CQG API client when credentials are available.
# For now, returns the latest cached price from futures_prices table.

from db.connection import get_client


def get_latest_futures_price(commodity_id: str, delivery_month: str) -> float:
    """
    Get the most recent futures price for a commodity/month contract.
    Raises ValueError if no price is cached.
    """
    # TODO: Map commodity_id + delivery_month → contract code, then query CQG live.
    # For now: return latest from DB cache.
    client = get_client()
    result = (
        client.table("futures_prices")
        .select("price")
        .order("fetched_at", desc=True)
        .limit(1)
        .execute()
    )
    if result.data:
        return float(result.data[0]["price"])
    raise ValueError("No futures price available. Run the futures feed first.")


def fetch_and_cache_futures_prices() -> list[dict]:
    """
    Fetch latest futures prices from CQG and store in futures_prices table.
    Called by Celery beat task every 5 minutes during market hours.
    """
    # TODO: Implement CQG API integration
    raise NotImplementedError("CQG API integration not yet implemented")
