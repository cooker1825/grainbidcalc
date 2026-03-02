"""Application configuration loaded from .env."""

import os
from dotenv import load_dotenv

load_dotenv()

# Supabase
SUPABASE_URL: str = os.environ["SUPABASE_URL"]
SUPABASE_KEY: str = os.environ["SUPABASE_KEY"]

# Claude API
ANTHROPIC_API_KEY: str = os.environ["ANTHROPIC_API_KEY"]

# Twilio
TWILIO_ACCOUNT_SID: str = os.environ.get("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN: str = os.environ.get("TWILIO_AUTH_TOKEN", "")
TWILIO_PHONE_NUMBER: str = os.environ.get("TWILIO_PHONE_NUMBER", "")

# Google
GOOGLE_SERVICE_ACCOUNT_JSON: str = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "")
GMAIL_TARGET_EMAIL: str = os.environ.get("GMAIL_TARGET_EMAIL", "markets@mapleviewgrain.ca")

# Redis / Celery
REDIS_URL: str = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

# App
APP_HOST: str = os.environ.get("APP_HOST", "0.0.0.0")
APP_PORT: int = int(os.environ.get("APP_PORT", "8000"))
APP_ENV: str = os.environ.get("APP_ENV", "development")
SECRET_KEY: str = os.environ.get("SECRET_KEY", "change-me")
