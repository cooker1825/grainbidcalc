"""Celery application configuration."""

from celery import Celery
from config.settings import REDIS_URL

app = Celery("grainbidcalc", broker=REDIS_URL, backend=REDIS_URL)
app.config_from_object("workers.beat_schedule")
app.autodiscover_tasks(["workers"])
