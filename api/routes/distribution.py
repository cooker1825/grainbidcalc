"""Distribution endpoints — trigger sends, view logs."""

from fastapi import APIRouter
from distribution.triggers import trigger_on_demand

router = APIRouter()


@router.post("/trigger")
async def trigger_distribution(commodities: list[str] = None, bid_types: list[str] = None):
    return await trigger_on_demand(commodities=commodities, bid_types=bid_types)
