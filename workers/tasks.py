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
    """Refresh futures prices from CQG."""
    from calculation.futures_feed import fetch_and_cache_futures_prices
    return fetch_and_cache_futures_prices()


@app.task
def task_fetch_exchange_rate():
    """Refresh USD/CAD exchange rate from Bank of Canada."""
    from calculation.exchange_rate import fetch_and_cache_exchange_rate
    return fetch_and_cache_exchange_rate()


@app.task
def task_snapshot_us_basis():
    """Daily end-of-day US basis snapshot for trend tracking."""
    # TODO: Implement daily US basis snapshot
    pass


@app.task
def task_distribute_scheduled(time_slot: str):
    """Run a scheduled distribution (morning/midday/afternoon)."""
    import asyncio
    from distribution.triggers import trigger_scheduled
    return asyncio.run(trigger_scheduled(time_slot))
