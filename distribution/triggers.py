"""
Distribution trigger logic.

Three trigger types:
  scheduled  — Celery beat: 7 AM, 12 PM, 4 PM ET
  on_demand  — Jeff hits a button on the dashboard
  threshold  — New bid is X cents better than previous best, or futures moved X cents
"""

from distribution.engine import distribute_bids


async def trigger_scheduled(time_slot: str) -> dict:
    """Run a scheduled distribution (morning/midday/afternoon)."""
    return await distribute_bids(trigger=f"scheduled:{time_slot}")


async def trigger_on_demand(
    commodities: list[str] | None = None,
    bid_types: list[str] | None = None,
    triggered_by: str = "user:jeff",
) -> dict:
    """Manually trigger distribution from the dashboard."""
    return await distribute_bids(
        trigger=f"on_demand:{triggered_by}",
        commodities=commodities,
        bid_types=bid_types,
    )
