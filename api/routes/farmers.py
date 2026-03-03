"""Farmer contacts and bid preference endpoints."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from db.connection import get_client

router = APIRouter()


class FarmerCreate(BaseModel):
    name: str
    farm_name: str | None = None
    phone: str | None = None
    email: str | None = None
    region: str | None = None
    location: str | None = None
    preferred_channel: str = "sms"   # "sms", "email", "both"
    notes: str | None = None


class FarmerUpdate(BaseModel):
    name: str | None = None
    farm_name: str | None = None
    phone: str | None = None
    email: str | None = None
    preferred_channel: str | None = None
    active: bool | None = None
    notes: str | None = None


class PreferenceCreate(BaseModel):
    commodity_id: str
    bid_type: str                    # "elevator", "delivered", "fob"
    destination: str | None = None   # None = all destinations
    fob_origin: str | None = None
    delivery_months: list[str] | None = None  # None = all months


# ─── Farmer CRUD ──────────────────────────────────────────────────────────────

@router.get("/")
async def list_farmers(active_only: bool = True):
    client = get_client()
    q = client.table("farmer_contacts").select("*").order("name")
    if active_only:
        q = q.eq("active", True)
    return q.execute().data


@router.get("/{farmer_id}")
async def get_farmer(farmer_id: str):
    client = get_client()
    result = client.table("farmer_contacts").select("*").eq("id", farmer_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Farmer not found")
    return result.data[0]


@router.post("/", status_code=201)
async def create_farmer(farmer: FarmerCreate):
    client = get_client()
    result = client.table("farmer_contacts").insert(farmer.model_dump(exclude_none=True)).execute()
    return result.data[0]


@router.put("/{farmer_id}")
async def update_farmer(farmer_id: str, updates: FarmerUpdate):
    client = get_client()
    data = updates.model_dump(exclude_none=True)
    if not data:
        raise HTTPException(status_code=400, detail="No fields to update")
    result = client.table("farmer_contacts").update(data).eq("id", farmer_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Farmer not found")
    return result.data[0]


@router.delete("/{farmer_id}", status_code=204)
async def deactivate_farmer(farmer_id: str):
    client = get_client()
    client.table("farmer_contacts").update({"active": False}).eq("id", farmer_id).execute()


# ─── Preferences ──────────────────────────────────────────────────────────────

@router.get("/{farmer_id}/preferences")
async def get_farmer_preferences(farmer_id: str):
    client = get_client()
    result = (
        client.table("farmer_bid_preferences")
        .select("*, commodities(name, display_name)")
        .eq("farmer_id", farmer_id)
        .eq("active", True)
        .execute()
    )
    return result.data


@router.post("/{farmer_id}/preferences", status_code=201)
async def add_preference(farmer_id: str, pref: PreferenceCreate):
    client = get_client()
    data = pref.model_dump(exclude_none=True)
    data["farmer_id"] = farmer_id
    result = client.table("farmer_bid_preferences").upsert(
        data,
        on_conflict="farmer_id,commodity_id,bid_type,destination",
    ).execute()
    return result.data[0]


@router.delete("/{farmer_id}/preferences/{pref_id}", status_code=204)
async def remove_preference(farmer_id: str, pref_id: str):
    client = get_client()
    client.table("farmer_bid_preferences").update({"active": False}).eq(
        "id", pref_id
    ).eq("farmer_id", farmer_id).execute()


@router.put("/{farmer_id}/preferences")
async def replace_all_preferences(farmer_id: str, prefs: list[PreferenceCreate]):
    """
    Bulk-replace all preferences for a farmer (used by the checkbox UI).
    Deactivates existing preferences and inserts the new set.
    """
    client = get_client()

    # Deactivate all current
    client.table("farmer_bid_preferences").update({"active": False}).eq(
        "farmer_id", farmer_id
    ).execute()

    # Insert new set
    if not prefs:
        return []

    rows = [{"farmer_id": farmer_id, **p.model_dump(exclude_none=True)} for p in prefs]
    result = client.table("farmer_bid_preferences").insert(rows).execute()
    return result.data
