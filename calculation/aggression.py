"""
Aggression parameter management.
Resolves Mapleview's margin adjustment for a given commodity/month/handling_type.

Priority chain (most specific wins):
  1. commodity + delivery_month + handling_type
  2. commodity + delivery_month + any handling (NULL)
  3. commodity + NULL month + handling_type
  4. commodity + NULL month + any handling
  5. Default: 0.0 (no adjustment)
"""

from db.connection import get_client


def get_aggression(
    commodity_id: str,
    delivery_month: str,
    handling_type: str = "brokered",
) -> float:
    """
    Resolve the aggression (margin) adjustment for a bid.
    Returns the adjustment value in CAD/BU (or CAD/MT for canola).
    """
    client = get_client()

    # Try most-specific first, fall back progressively
    candidates = [
        {"commodity_id": commodity_id, "delivery_month": delivery_month, "handling_type": handling_type},
        {"commodity_id": commodity_id, "delivery_month": delivery_month},
        {"commodity_id": commodity_id, "handling_type": handling_type},
        {"commodity_id": commodity_id},
    ]

    for query_params in candidates:
        q = client.table("aggression_params").select("adjustment_value").eq("active", True)
        for k, v in query_params.items():
            if k == "delivery_month":
                q = q.eq("delivery_month", v)
            elif k == "handling_type":
                q = q.eq("handling_type", v)
            elif k == "commodity_id":
                q = q.eq("commodity_id", v)

        result = q.limit(1).execute()
        if result.data:
            return float(result.data[0]["adjustment_value"])

    return 0.0
