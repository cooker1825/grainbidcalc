"""
Scheduled web scrapers for buyers who publish bids online.
Runs every 30 minutes during market hours via Celery beat.
Uses httpx + BeautifulSoup. Playwright available for JS-rendered pages.
"""

import httpx
from bs4 import BeautifulSoup

from ingestion.router import process_incoming

SCRAPE_TARGETS = {
    "great_lakes_dutton": {
        "url": "https://cashbids.greatlakesgrain.com/popup/printCashbids.cfm?show=11&mid=25&cid=2601&sid=2&theLocation=88&cmid=all",
        "method": "html",
        "buyer_short_name": "great_lakes_grain",
    },
    "adm_windsor": {
        "url": "",  # TODO: Find ADM Windsor cash bid URL
        "method": "html",
        "buyer_short_name": "adm_windsor",
    },
}


async def scrape_target(key: str) -> dict:
    """Fetch and process a single scrape target."""
    target = SCRAPE_TARGETS[key]
    if not target["url"]:
        return {"status": "skipped", "reason": "URL not configured"}

    async with httpx.AsyncClient() as client:
        response = await client.get(target["url"], timeout=30)
        response.raise_for_status()
        html = response.text

    return await process_incoming(
        source_type="web_scrape",
        source_identifier=target["url"],
        text_content=html,
    )


async def scrape_all() -> list[dict]:
    """Scrape all configured targets."""
    results = []
    for key in SCRAPE_TARGETS:
        try:
            result = await scrape_target(key)
            results.append({"target": key, **result})
        except Exception as e:
            results.append({"target": key, "status": "error", "error": str(e)})
    return results
