"""FastAPI application entry point."""

from fastapi import FastAPI
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

from api.routes import bids, buyers, aggression, distribution, farmers, dashboard, webhooks

app = FastAPI(title="GrainBidCalc", version="0.1.0")

app.mount("/static", StaticFiles(directory="dashboard/static"), name="static")

app.include_router(bids.router,         prefix="/api/bids",         tags=["bids"])
app.include_router(buyers.router,       prefix="/api/buyers",       tags=["buyers"])
app.include_router(aggression.router,   prefix="/api/aggression",   tags=["aggression"])
app.include_router(distribution.router, prefix="/api/distribution", tags=["distribution"])
app.include_router(farmers.router,      prefix="/api/farmers",      tags=["farmers"])
app.include_router(dashboard.router,    prefix="",                  tags=["dashboard"])
app.include_router(webhooks.router,     prefix="/api/webhooks",     tags=["webhooks"])


@app.get("/health")
async def health():
    return {"status": "ok"}
