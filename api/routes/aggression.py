"""Aggression parameter CRUD — manage Mapleview's margin adjustments."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from db.connection import get_client

router = APIRouter()


class AggressionUpdate(BaseModel):
    commodity_id: str
    delivery_month: str | None = None      # None = default for commodity
    handling_type: str = "brokered"        # "brokered" or "physical"
    adjustment_value: float                # CAD/BU — negative = take margin from best bid
    adjustment_unit: str = "CAD/BU"
    notes: str | None = None


@router.get("/")
async def list_aggression_params(active_only: bool = True):
    """Return the full aggression matrix with commodity names."""
    client = get_client()
    q = (
        client.table("aggression_params")
        .select("*, commodities(name, display_name)")
        .order("commodity_id")
    )
    if active_only:
        q = q.eq("active", True)
    return q.execute().data


@router.put("/")
async def upsert_aggression(params: AggressionUpdate):
    """
    Create or update an aggression parameter.
    Uses commodity_id + delivery_month + handling_type as the unique key.
    """
    client = get_client()
    data = params.model_dump(exclude_none=True)
    data["active"] = True
    result = client.table("aggression_params").upsert(
        data,
        on_conflict="commodity_id,delivery_month,handling_type",
    ).execute()
    return result.data[0]


@router.delete("/{param_id}", status_code=204)
async def deactivate_aggression_param(param_id: str):
    """Soft-delete an aggression parameter."""
    client = get_client()
    client.table("aggression_params").update({"active": False}).eq("id", param_id).execute()
