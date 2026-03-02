"""Bid endpoints — list current bids, ranked bids, manual entry."""

from fastapi import APIRouter, Query
from calculation.ranking import rank_bids
from db.queries import get_current_bids

router = APIRouter()


@router.get("/ranked")
async def get_ranked_bids(
    commodity_id: str = Query(...),
    delivery_month: str = Query(...),
    rank_by: str = Query("cash_price"),
    handling_type: str = Query("brokered"),
):
    return rank_bids(commodity_id, delivery_month, handling_type, rank_by)


@router.get("/")
async def list_bids(commodity_id: str = Query(None), delivery_month: str = Query(None)):
    if commodity_id and delivery_month:
        return get_current_bids(commodity_id, delivery_month)
    return []
