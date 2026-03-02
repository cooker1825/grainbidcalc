"""Celery beat schedule — all periodic tasks."""

from celery.schedules import crontab

beat_schedule = {
    # Futures prices: every 5 min during market hours (Mon–Fri 8:30 AM–3 PM ET)
    "fetch-futures": {
        "task": "workers.tasks.task_fetch_futures",
        "schedule": crontab(minute="*/5", hour="8-15", day_of_week="1-5"),
    },
    # Exchange rate: every 30 min during market hours
    "fetch-exchange-rate": {
        "task": "workers.tasks.task_fetch_exchange_rate",
        "schedule": crontab(minute="*/30", hour="8-16", day_of_week="1-5"),
    },
    # Email polling: every 5 min
    "poll-email": {
        "task": "workers.tasks.task_poll_email",
        "schedule": crontab(minute="*/5"),
    },
    # Web scraping: every 30 min during market hours
    "scrape-web": {
        "task": "workers.tasks.task_scrape_web_sources",
        "schedule": crontab(minute="0,30", hour="8-16", day_of_week="1-5"),
    },
    # Scheduled distributions (ET times = UTC-4 in summer / UTC-5 in winter)
    "distribute-morning": {
        "task": "workers.tasks.task_distribute_scheduled",
        "schedule": crontab(hour="11", minute="0"),  # 7 AM ET
        "args": ("morning",),
    },
    "distribute-midday": {
        "task": "workers.tasks.task_distribute_scheduled",
        "schedule": crontab(hour="16", minute="0"),  # 12 PM ET
        "args": ("midday",),
    },
    "distribute-afternoon": {
        "task": "workers.tasks.task_distribute_scheduled",
        "schedule": crontab(hour="20", minute="0"),  # 4 PM ET
        "args": ("afternoon",),
    },
    # Daily US basis snapshot: 4:30 PM ET (after market close)
    "snapshot-us-basis": {
        "task": "workers.tasks.task_snapshot_us_basis",
        "schedule": crontab(hour="20", minute="30", day_of_week="1-5"),
    },
}

timezone = "UTC"
