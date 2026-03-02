"""Common database queries."""

from db.connection import get_client


def get_current_bids(commodity_id: str, delivery_month: str) -> list[dict]:
    """Return all current (non-expired) bids for a commodity/month."""
    client = get_client()
    result = (
        client.table("basis_bids")
        .select("*, buyers(name, short_name), commodities(name, display_name)")
        .eq("commodity_id", commodity_id)
        .eq("delivery_month", delivery_month)
        .eq("is_current", True)
        .order("basis_normalized_cad_bu", desc=True)
        .execute()
    )
    return result.data or []


def mark_previous_bids_stale(buyer_id: str, commodity_id: str, delivery_month: str, bid_type: str):
    """Mark prior bids for this buyer/commodity/month/type as not current."""
    client = get_client()
    client.table("basis_bids").update({"is_current": False}).eq(
        "buyer_id", buyer_id
    ).eq("commodity_id", commodity_id).eq("delivery_month", delivery_month).eq(
        "bid_type", bid_type
    ).eq("is_current", True).execute()


def insert_bid(bid: dict) -> dict:
    """Insert a new basis_bid row. Returns the inserted record."""
    client = get_client()
    result = client.table("basis_bids").insert(bid).execute()
    return result.data[0]


def log_ingestion(record: dict) -> None:
    """Append a row to ingestion_log."""
    client = get_client()
    client.table("ingestion_log").insert(record).execute()
