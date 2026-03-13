"""
Ranks current basis bids for a commodity/delivery month.
Best bid = highest cash price (or highest US basis for analytics).

rank_by options:
  "cash_price"  — best price for the farmer (default for distribution)
  "cad_basis"   — highest CAD basis (includes FX effect)
  "us_basis"    — highest US basis (true competitiveness, best for Mapleview analysis)
"""

from calculation.price_calculator import calculate_full_pricing
from calculation.aggression import get_aggression
from calculation.futures_feed import get_latest_futures_price
from calculation.exchange_rate import get_latest_exchange_rate
from db.connection import get_client
from db.queries import get_current_bids


def rank_bids(
    commodity_id: str,
    delivery_month: str,
    handling_type: str = "brokered",
    rank_by: str = "cash_price",
) -> list[dict]:
    """
    Rank all current bids for a commodity/month and return sorted list (best first).
    """
    bids = get_current_bids(commodity_id, delivery_month)
    if not bids:
        return []

    futures_price = get_latest_futures_price(commodity_id, delivery_month)
    exchange_rate = get_latest_exchange_rate()
    aggression = get_aggression(commodity_id, delivery_month, handling_type)

    ranked = []
    for bid in bids:
        pricing = calculate_full_pricing(
            basis_cad_bu=float(bid["basis_normalized_cad_bu"] or bid["basis_value"]),
            futures_price_usd=futures_price,
            exchange_rate=exchange_rate,
            commodity=bid.get("commodity_name", ""),
            aggression=aggression,
        )
        ranked.append({**bid, **pricing})

    sort_key = {
        "cash_price": lambda b: b["mapleview_price_cad_bu"],
        "cad_basis":  lambda b: b["cad_basis"],
        "us_basis":   lambda b: b["us_basis"],
    }.get(rank_by, lambda b: b["mapleview_price_cad_bu"])

    ranked.sort(key=sort_key, reverse=True)

    for i, bid in enumerate(ranked):
        bid["rank"] = i + 1

    return ranked


def get_ranked_bids(commodity_id: str, delivery_month: str | None = None) -> list[dict]:
    """
    Return ranked bids for all (or one) delivery month(s) for a commodity.
    Skips months where futures price is unavailable.
    Field names are normalised for the sheet sync task.
    """
    if delivery_month:
        months = [delivery_month]
    else:
        client = get_client()
        rows = (
            client.table("basis_bids")
            .select("delivery_month")
            .eq("commodity_id", commodity_id)
            .eq("is_current", True)
            .execute()
            .data or []
        )
        months = sorted({r["delivery_month"] for r in rows})

    all_bids = []
    for month in months:
        try:
            ranked = rank_bids(commodity_id, month)
        except (ValueError, Exception):
            continue
        for bid in ranked:
            buyer = bid.get("buyers") or {}
            all_bids.append({
                "delivery_month":  bid.get("delivery_month", month),
                "rank":            bid.get("rank", ""),
                "buyer_name":      buyer.get("name", "") if isinstance(buyer, dict) else "",
                "destination":     bid.get("destination", ""),
                "bid_type":        bid.get("bid_type", ""),
                "cad_basis":       bid.get("cad_basis"),
                "us_basis":        bid.get("us_basis"),
                "live_cash":       bid.get("cash_price_cad_bu"),
                "mapleview_price": bid.get("mapleview_price_cad_bu"),
            })

    return all_bids
