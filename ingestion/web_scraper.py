"""
Scheduled web scrapers for buyers who publish bids online.
Runs every 30 minutes during market hours via Celery beat.

Two types of scrapers:
  1. LLM-based (SCRAPE_TARGETS): fetches HTML → sends to process_incoming() → LLM parses
  2. Structured (STRUCTURED_SCRAPERS): fetches data → extracts structured bids → bypasses LLM
"""

import logging
from datetime import date, datetime, timezone

import httpx

from ingestion.router import process_incoming
from parsing.normalizer import normalize_bids
from parsing.validator import validate_bids
from calculation.exchange_rate import get_latest_exchange_rate
from db.queries import insert_bid, upsert_bid, mark_previous_bids_stale, log_ingestion, resolve_buyer_id, resolve_commodity_id
from data.onedrive_writer import write_bids_to_onedrive, write_bids_to_elevator_onedrive

logger = logging.getLogger(__name__)

# --- LLM-based scrapers (raw HTML → LLM parser) ---
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
    """Fetch and process a single LLM-based scrape target."""
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


# --- Structured scrapers (JSON/API → bypass LLM) ---
STRUCTURED_SCRAPERS = {
    "dg_global": {
        "module": "ingestion.scrapers.dg_global",
        "source_url": "https://dgglobal.ca/cash-bids",
        "workbook": "elevator",
    },
    "hdc": {
        "module": "ingestion.scrapers.hdc",
        "source_url": "https://hensallco-op.ca/Cash-Bids.htm",
        "workbook": "elevator",
    },
    "bushel_ingredion": {
        "module": "ingestion.scrapers.bushel",
        "source_url": "https://portal.bushelpowered.com/ingredion/cash-bids",
        "workbook": "delivered",
    },
}


async def _run_structured_scraper(key: str) -> dict:
    """
    Run a structured scraper and push bids through normalize → validate → store → XLSX.

    Bypasses the LLM parser since these scrapers return clean, structured data.
    """
    config = STRUCTURED_SCRAPERS[key]
    start_time = datetime.now(timezone.utc)

    # Dynamic import of scraper module
    import importlib
    mod = importlib.import_module(config["module"])
    raw_bids = await mod.scrape()

    if not raw_bids:
        return {"target": key, "status": "empty", "parsed": 0, "stored": 0}

    # Normalize
    exchange_rate = get_latest_exchange_rate()
    normalized = normalize_bids(raw_bids, exchange_rate=exchange_rate)

    # Resolve buyer/commodity IDs
    for bid in normalized:
        if not bid.get("buyer_id"):
            bid["buyer_id"] = resolve_buyer_id(bid.get("buyer_name", ""))
        if not bid.get("commodity_id"):
            bid["commodity_id"] = resolve_commodity_id(bid.get("commodity", ""))

    # Validate
    validated = validate_bids(normalized)

    # Store
    stored_count = 0
    for bid in validated:
        if bid.get("basis_value") is None:
            continue
        try:
            if bid.get("buyer_id") and bid.get("commodity_id"):
                mark_previous_bids_stale(
                    bid["buyer_id"], bid["commodity_id"],
                    bid.get("delivery_month", ""), bid.get("bid_type", "delivered"),
                )
            upsert_bid({
                "buyer_id": bid.get("buyer_id"),
                "commodity_id": bid.get("commodity_id"),
                "delivery_month": bid.get("delivery_month"),
                "delivery_label": bid.get("delivery_label"),
                "basis_value": bid.get("basis_value"),
                "basis_unit": bid.get("basis_unit", "CAD/BU"),
                "basis_normalized_cad_bu": bid.get("basis_normalized_cad_bu"),
                "futures_contract": bid.get("futures_contract_normalized"),
                "bid_type": bid.get("bid_type", "delivered"),
                "destination": bid.get("destination"),
                "source_type": "web_scrape",
                "confidence": bid.get("confidence"),
                "bid_date": date.today().isoformat(),
            })
            stored_count += 1
        except Exception as e:
            bid["storage_error"] = str(e)
            logger.warning("Failed to store %s bid: %s", key, e)

    # Write to SharePoint XLSX (elevator or delivered workbook)
    xlsx_bids = [
        b for b in validated
        if b.get("basis_value") is not None and not b.get("storage_error")
    ]
    if xlsx_bids:
        try:
            writer_fn = (write_bids_to_elevator_onedrive
                         if config.get("workbook") == "elevator"
                         else write_bids_to_onedrive)
            od_results = writer_fn(xlsx_bids)
            od_written = sum(1 for r in od_results if r.get("success"))
            logger.info("%s OneDrive (%s): wrote %d/%d bids",
                        key, config.get("workbook", "delivered"), od_written, len(xlsx_bids))
        except Exception as e:
            logger.warning("%s OneDrive write failed: %s", key, e)

    # Log
    elapsed_ms = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)
    log_ingestion({
        "source_type": "web_scrape",
        "source_identifier": config["source_url"],
        "parsed_bids_count": stored_count,
        "status": "parsed" if stored_count > 0 else "empty",
        "processing_time_ms": elapsed_ms,
    })

    return {
        "target": key,
        "status": "ok",
        "parsed": len(raw_bids),
        "stored": stored_count,
    }


async def scrape_all() -> list[dict]:
    """Scrape all configured targets (both LLM-based and structured)."""
    results = []

    # LLM-based scrapers
    for key in SCRAPE_TARGETS:
        try:
            result = await scrape_target(key)
            results.append({"target": key, **result})
        except Exception as e:
            results.append({"target": key, "status": "error", "error": str(e)})

    # Structured scrapers (no LLM cost)
    for key in STRUCTURED_SCRAPERS:
        try:
            result = await _run_structured_scraper(key)
            results.append(result)
        except Exception as e:
            logger.warning("Structured scraper %s failed: %s", key, e)
            results.append({"target": key, "status": "error", "error": str(e)})

    return results
