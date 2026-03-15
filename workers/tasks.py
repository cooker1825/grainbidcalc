"""Celery async tasks."""

from workers.celery_app import app


@app.task
def task_poll_email():
    """Poll Gmail inbox for new bid emails."""
    import asyncio
    from ingestion.email_listener import poll_email_inbox
    return asyncio.run(poll_email_inbox())


@app.task
def task_scrape_web_sources():
    """Scrape all configured web bid sources."""
    import asyncio
    from ingestion.web_scraper import scrape_all
    return asyncio.run(scrape_all())


@app.task
def task_fetch_futures():
    """Read futures prices from XLSX and cache in DB."""
    from calculation.futures_feed import fetch_and_cache_futures_prices
    return fetch_and_cache_futures_prices()


@app.task
def task_fetch_exchange_rate():
    """Refresh USD/CAD exchange rate from Bank of Canada."""
    from calculation.exchange_rate import fetch_and_cache_exchange_rate
    return fetch_and_cache_exchange_rate()


@app.task
def task_snapshot_us_basis():
    """
    Daily end-of-day US basis snapshot for trend tracking.
    Captures current US basis for every active bid and writes to us_basis_history.
    Run at 4:30 PM ET after market close.
    """
    from datetime import date
    from calculation.price_calculator import calculate_us_basis
    from calculation.exchange_rate import get_latest_exchange_rate
    from calculation.futures_feed import get_latest_futures_price
    from db.connection import get_client

    client = get_client()
    today = date.today().isoformat()

    # Get all current bids
    bids = (
        client.table("basis_bids")
        .select("id, buyer_id, commodity_id, delivery_month, basis_value, futures_contract")
        .eq("is_current", True)
        .execute()
        .data or []
    )

    try:
        exchange_rate = get_latest_exchange_rate()
    except ValueError:
        return {"error": "No exchange rate available for snapshot"}

    rows = []
    for bid in bids:
        if bid.get("basis_value") is None:
            continue
        try:
            futures_price = get_latest_futures_price(bid["commodity_id"], bid["delivery_month"])
            us_basis = calculate_us_basis(
                cad_basis=float(bid["basis_value"]),
                futures_price_usd_bu=futures_price,
                exchange_rate=exchange_rate,
            )
            rows.append({
                "buyer_id": bid["buyer_id"],
                "commodity_id": bid["commodity_id"],
                "delivery_month": bid["delivery_month"],
                "us_basis": us_basis,
                "cad_basis": float(bid["basis_value"]),
                "exchange_rate": exchange_rate,
                "futures_price": futures_price,
                "snapshot_date": today,
            })
        except Exception:
            continue

    if rows:
        client.table("us_basis_history").upsert(
            rows,
            on_conflict="buyer_id,commodity_id,delivery_month,snapshot_date",
        ).execute()

    return {"snapshots_written": len(rows), "date": today}


@app.task
def task_distribute_scheduled(time_slot: str):
    """Run a scheduled distribution (morning/midday/afternoon)."""
    import asyncio
    from distribution.triggers import trigger_scheduled
    return asyncio.run(trigger_scheduled(time_slot))


@app.task
def task_check_bushel_token():
    """Check Bushel session token expiry and email Jeff if within 2 days."""
    import json
    import asyncio
    from datetime import datetime, timezone, timedelta
    from pathlib import Path

    token_file = Path("/opt/grainbidcalc/data/bushel_token.json")
    if not token_file.exists():
        return {"status": "no_token_file"}

    try:
        data = json.loads(token_file.read_text())
    except (json.JSONDecodeError, OSError):
        return {"status": "unreadable"}

    expires_str = data.get("expires")
    if not expires_str:
        return {"status": "no_expiry_field"}

    # Parse ISO expiry: "2026-04-12T19:34:53.054Z"
    expires = datetime.fromisoformat(expires_str.replace("Z", "+00:00"))
    now = datetime.now(timezone.utc)
    remaining = expires - now

    if remaining.total_seconds() <= 0:
        subject = "URGENT: Bushel session EXPIRED"
        body = (
            f"The Bushel/Ingredion session token expired on {expires_str}.\n"
            "Ingredion bids are NOT being scraped.\n\n"
            "Re-login now:\n"
            "  ssh root@159.89.127.66\n"
            "  cd /opt/grainbidcalc\n"
            "  PYTHONPATH=/opt/grainbidcalc venv/bin/python -m ingestion.scrapers.bushel_login\n"
        )
    elif remaining < timedelta(days=2):
        days_left = remaining.total_seconds() / 86400
        subject = f"Bushel session expires in {days_left:.1f} days"
        body = (
            f"The Bushel/Ingredion session token expires on {expires_str} "
            f"({days_left:.1f} days from now).\n\n"
            "Please re-login before it expires to keep Ingredion bids flowing:\n"
            "  ssh root@159.89.127.66\n"
            "  cd /opt/grainbidcalc\n"
            "  PYTHONPATH=/opt/grainbidcalc venv/bin/python -m ingestion.scrapers.bushel_login\n"
        )
    else:
        days_left = remaining.total_seconds() / 86400
        return {"status": "ok", "days_remaining": round(days_left, 1)}

    # Send the warning email
    from distribution.email_sender import send_email
    asyncio.run(send_email(
        to_address="jeff@mapleviewfarms.ca",
        subject=subject,
        body=body,
    ))
    return {"status": "notified", "subject": subject}


