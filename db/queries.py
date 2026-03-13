"""Common database queries."""

import re
from db.connection import get_client


def _norm(s: str) -> str:
    """Strip non-alphanumeric chars and lowercase for fuzzy matching."""
    return re.sub(r'[^a-z0-9]', '', s.lower())

# In-process caches so we don't hammer the DB on every bid
_buyer_cache: dict[str, str] = {}      # name/short_name -> id
_commodity_cache: dict[str, str] = {}  # name -> id


def resolve_buyer_id(buyer_name: str) -> str | None:
    """
    Resolve a buyer name (fuzzy) to a buyer UUID.
    Matches on name or short_name, case-insensitive substring.
    """
    if not buyer_name:
        return None
    key = buyer_name.lower()
    if key in _buyer_cache:
        return _buyer_cache[key]

    client = get_client()
    rows = client.table("buyers").select("id, name, short_name").eq("active", True).execute().data or []
    norm_key = _norm(buyer_name)
    for row in rows:
        n = row["name"].lower()
        s = row["short_name"].lower()
        # Standard substring checks
        if (buyer_name.lower() in n or n in buyer_name.lower() or
                buyer_name.lower() in s or s in buyer_name.lower()):
            _buyer_cache[key] = row["id"]
            return row["id"]
        # Normalized checks (strips spaces, dashes, underscores)
        norm_n = _norm(n)
        norm_s = _norm(s)
        if (norm_key in norm_n or norm_n in norm_key or
                norm_key in norm_s or norm_s in norm_key):
            _buyer_cache[key] = row["id"]
            return row["id"]
    return None


def resolve_commodity_id(commodity_name: str) -> str | None:
    """Resolve commodity name (e.g. 'soybeans') to a commodity UUID."""
    if not commodity_name:
        return None
    key = commodity_name.lower()
    if key in _commodity_cache:
        return _commodity_cache[key]

    client = get_client()
    result = (
        client.table("commodities").select("id")
        .eq("name", key)
        .maybe_single()
        .execute()
    )
    if result and result.data:
        _commodity_cache[key] = result.data["id"]
        return result.data["id"]
    return None


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


def upsert_bid(bid: dict) -> dict:
    """Insert or update a bid (same buyer/commodity/month/type/dest/date = update)."""
    client = get_client()
    result = client.table("basis_bids").upsert(
        bid,
        on_conflict="buyer_id,commodity_id,delivery_month,bid_type,destination,bid_date",
    ).execute()
    return result.data[0]


def log_ingestion(record: dict) -> None:
    """Append a row to ingestion_log."""
    client = get_client()
    client.table("ingestion_log").insert(record).execute()
