"""
Central ingestion router. Receives raw content from any source and:
  1. Identifies the buyer
  2. Preprocesses content (extract text from PDFs, prepare images)
  3. Calls the LLM parser with buyer-specific hints
  4. Normalizes and validates parsed bids
  5. CRITICAL: Back-calculates basis for cash-price-only sources (must use LIVE futures/FX)
  6. Stores bids in the database
  7. Logs the ingestion
"""

import json
from datetime import date, datetime, timezone

from parsing.llm_parser import parse_bid_sheet
from parsing.normalizer import normalize_bids
from parsing.validator import validate_bids
from parsing.buyer_profiles import get_profile_for_source
from calculation.price_calculator import back_calculate_basis_from_cash
from calculation.futures_feed import get_latest_futures_price
from calculation.exchange_rate import get_latest_exchange_rate
from db.queries import insert_bid, mark_previous_bids_stale, log_ingestion
from ingestion.preprocessor import preprocess


async def process_incoming(
    source_type: str,
    source_identifier: str,
    text_content: str | None = None,
    attachments: list | None = None,
) -> dict:
    """
    Main entry point for all inbound bid content.

    source_type: "email", "sms", "web_scrape", "manual"
    source_identifier: email address, phone number, or URL
    text_content: plain text or HTML body
    attachments: list of (filename, bytes, content_type) tuples
    """
    start_time = datetime.now(timezone.utc)

    # 1. Identify buyer and get profile hints
    profile = get_profile_for_source(source_type, source_identifier, text_content or "")

    # 2. Preprocess: extract text from PDFs, prepare image bytes
    content_pieces = preprocess(text_content, attachments or [])

    # 3. Parse each content piece through the LLM
    all_bids = []
    for piece in content_pieces:
        bids = parse_bid_sheet(
            content=piece.get("text"),
            image_bytes=piece.get("image"),
            image_media_type=piece.get("media_type", "image/png"),
            source_type=source_type,
            buyer_hint=json.dumps(profile),
            date_hint=date.today().isoformat(),
        )
        all_bids.extend(bids)

    # 4. Normalize
    exchange_rate = get_latest_exchange_rate()
    normalized = normalize_bids(all_bids, exchange_rate=exchange_rate)

    # 5. CRITICAL: Back-calculate basis for cash-price-only bids RIGHT NOW
    #    (futures and FX must be captured at this exact moment)
    for bid in normalized:
        if bid.get("basis_value") is None and bid.get("cash_price") is not None:
            commodity_id = bid.get("commodity_id", "")
            delivery_month = bid.get("delivery_month", "")
            try:
                live_futures = get_latest_futures_price(commodity_id, delivery_month)
            except ValueError:
                # No futures cached — flag for manual review
                bid["validation_issues"] = bid.get("validation_issues", [])
                bid["validation_issues"].append("no_futures_for_back_calc")
                bid["needs_review"] = True
                continue

            result = back_calculate_basis_from_cash(
                cash_price_cad=float(bid["cash_price"]),
                futures_price_usd=live_futures,
                exchange_rate=exchange_rate,
            )
            bid.update(result)
            bid["basis_value"] = result["cad_basis"]
            bid["basis_unit"] = "CAD/BU"
            bid["basis_normalized_cad_bu"] = result["cad_basis"]

    # 6. Validate
    validated = validate_bids(normalized)

    # 7. Store valid bids
    stored_count = 0
    for bid in validated:
        if bid.get("basis_value") is None:
            continue  # Skip bids we couldn't resolve
        try:
            # Mark previous bid for this buyer/commodity/month/type as stale
            if bid.get("buyer_id") and bid.get("commodity_id"):
                mark_previous_bids_stale(
                    bid["buyer_id"], bid["commodity_id"],
                    bid.get("delivery_month", ""), bid.get("bid_type", "delivered")
                )
            insert_bid({
                "buyer_id": bid.get("buyer_id"),
                "commodity_id": bid.get("commodity_id"),
                "delivery_month": bid.get("delivery_month"),
                "delivery_label": bid.get("delivery_label"),
                "basis_value": bid.get("basis_value"),
                "basis_unit": bid.get("basis_unit", "CAD/BU"),
                "basis_normalized_cad_bu": bid.get("basis_normalized_cad_bu"),
                "us_basis_at_ingestion": bid.get("us_basis_at_ingestion"),
                "was_back_calculated": bid.get("was_back_calculated", False),
                "source_cash_price": bid.get("source_cash_price"),
                "back_calc_futures": bid.get("back_calc_futures"),
                "back_calc_fx_rate": bid.get("back_calc_fx_rate"),
                "back_calc_timestamp": bid.get("back_calc_timestamp"),
                "futures_contract": bid.get("futures_contract_normalized"),
                "futures_contract_raw": bid.get("futures_contract_raw"),
                "bid_type": bid.get("bid_type", "delivered"),
                "destination": bid.get("destination"),
                "source_type": source_type,
                "raw_text": bid.get("raw_text"),
                "confidence": bid.get("confidence"),
                "bid_date": date.today().isoformat(),
            })
            stored_count += 1
        except Exception as e:
            bid["storage_error"] = str(e)

    # 8. Log
    elapsed_ms = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)
    log_ingestion({
        "source_type": source_type,
        "source_identifier": source_identifier,
        "raw_content": text_content,
        "parsed_bids_count": stored_count,
        "status": "parsed" if stored_count > 0 else "failed",
        "processing_time_ms": elapsed_ms,
    })

    return {
        "source_type": source_type,
        "parsed": len(all_bids),
        "stored": stored_count,
        "needs_review": [b for b in validated if b.get("needs_review")],
    }
