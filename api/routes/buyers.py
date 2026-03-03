"""Buyer CRUD endpoints."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from db.connection import get_client

router = APIRouter()


class BuyerCreate(BaseModel):
    name: str
    short_name: str
    source_type: str
    source_identifier: str | None = None
    location: str | None = None
    region: str | None = None
    notes: str | None = None


class BuyerUpdate(BaseModel):
    name: str | None = None
    source_identifier: str | None = None
    location: str | None = None
    region: str | None = None
    notes: str | None = None
    active: bool | None = None


@router.get("/")
async def list_buyers(active_only: bool = True):
    client = get_client()
    q = client.table("buyers").select("*").order("name")
    if active_only:
        q = q.eq("active", True)
    return q.execute().data


@router.get("/{buyer_id}")
async def get_buyer(buyer_id: str):
    client = get_client()
    result = client.table("buyers").select("*").eq("id", buyer_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Buyer not found")
    return result.data[0]


@router.post("/", status_code=201)
async def create_buyer(buyer: BuyerCreate):
    client = get_client()
    result = client.table("buyers").insert(buyer.model_dump(exclude_none=True)).execute()
    return result.data[0]


@router.put("/{buyer_id}")
async def update_buyer(buyer_id: str, updates: BuyerUpdate):
    client = get_client()
    data = updates.model_dump(exclude_none=True)
    if not data:
        raise HTTPException(status_code=400, detail="No fields to update")
    result = client.table("buyers").update(data).eq("id", buyer_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Buyer not found")
    return result.data[0]


@router.delete("/{buyer_id}", status_code=204)
async def deactivate_buyer(buyer_id: str):
    """Soft-delete: set active=False."""
    client = get_client()
    client.table("buyers").update({"active": False}).eq("id", buyer_id).execute()
