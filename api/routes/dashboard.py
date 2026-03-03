"""Admin dashboard routes — ranked bids, US basis heatmap, aggression, farmer prefs."""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from db.connection import get_client
from calculation.ranking import rank_bids
from calculation.exchange_rate import get_latest_exchange_rate
from calculation.futures_feed import get_latest_futures_price

router = APIRouter()
templates = Jinja2Templates(directory="dashboard/templates")


@router.get("/", response_class=HTMLResponse)
async def dashboard_home(request: Request):
    """Main dashboard: ranked bids grid for all active commodities."""
    client = get_client()
    commodities = client.table("commodities").select("*").execute().data or []

    # Build ranked bids table for each commodity × nearest delivery month
    from datetime import date
    delivery_month = f"{date.today().year}-10"  # Default to harvest

    bid_tables = {}
    for commodity in commodities:
        try:
            ranked = rank_bids(
                commodity_id=commodity["id"],
                delivery_month=delivery_month,
            )
            if ranked:
                bid_tables[commodity["display_name"]] = ranked
        except Exception:
            pass

    try:
        exchange_rate = get_latest_exchange_rate()
    except ValueError:
        exchange_rate = None

    return templates.TemplateResponse("index.html", {
        "request": request,
        "bid_tables": bid_tables,
        "delivery_month": delivery_month,
        "exchange_rate": exchange_rate,
    })


@router.get("/us-basis", response_class=HTMLResponse)
async def us_basis_view(request: Request):
    """US Basis heatmap — the operator's analytical edge."""
    client = get_client()
    commodities = client.table("commodities").select("*").execute().data or []
    buyers = client.table("buyers").select("id, name").eq("active", True).execute().data or []

    return templates.TemplateResponse("us_basis.html", {
        "request": request,
        "commodities": commodities,
        "buyers": buyers,
    })


@router.get("/ingestion", response_class=HTMLResponse)
async def ingestion_log_view(request: Request):
    """Ingestion log — view parsing results and errors."""
    client = get_client()
    logs = (
        client.table("ingestion_log")
        .select("*")
        .order("created_at", desc=True)
        .limit(100)
        .execute()
        .data or []
    )
    return templates.TemplateResponse("ingestion_log.html", {
        "request": request,
        "logs": logs,
    })
