"""Scheduled distribution time slots. Configured via Celery beat."""

DISTRIBUTION_SCHEDULE = {
    "morning":   "7:00 AM ET",
    "midday":    "12:00 PM ET",
    "afternoon": "4:00 PM ET",
}
