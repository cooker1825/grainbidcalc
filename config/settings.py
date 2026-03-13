"""Application configuration loaded from .env."""

import os
from dotenv import load_dotenv

load_dotenv()

# Supabase
SUPABASE_URL: str = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY: str = os.environ.get("SUPABASE_KEY", "")

# Claude API
ANTHROPIC_API_KEY: str = os.environ.get("ANTHROPIC_API_KEY", "")

# Twilio
TWILIO_ACCOUNT_SID: str = os.environ.get("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN: str = os.environ.get("TWILIO_AUTH_TOKEN", "")
TWILIO_PHONE_NUMBER: str = os.environ.get("TWILIO_PHONE_NUMBER", "")

# Google
GOOGLE_SERVICE_ACCOUNT_JSON: str = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "")
GMAIL_TARGET_EMAIL: str = os.environ.get("GMAIL_TARGET_EMAIL", "markets@mapleviewgrain.ca")

# Email (IMAP) — HostPapa or any IMAP provider
IMAP_HOST: str = os.environ.get("IMAP_HOST", "mapleviewgrain.ca")
IMAP_PORT: int = int(os.environ.get("IMAP_PORT", "993"))
IMAP_USER: str = os.environ.get("IMAP_USER", "markets@mapleviewgrain.ca")
IMAP_PASSWORD: str = os.environ.get("IMAP_PASSWORD", "")

# Redis / Celery
REDIS_URL: str = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

# Google Sheets
SHEETS_ID: str = os.environ.get("SHEETS_ID", "")
SHEETS_WEBAPP_URL: str = os.environ.get("SHEETS_WEBAPP_URL", "")
SHEETS_OAUTH_CLIENT_JSON: str = os.environ.get("SHEETS_OAUTH_CLIENT_JSON", "credentials/oauth-client.json")
SHEETS_TOKEN_JSON: str = os.environ.get("SHEETS_TOKEN_JSON", "credentials/sheets-token.json")

# XLSX Futures
XLSX_FUTURES_PATH: str = os.environ.get(
    "XLSX_FUTURES_PATH",
    os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "grainbidcalculatorCOPY.xlsx"),
)

# App
APP_HOST: str = os.environ.get("APP_HOST", "0.0.0.0")
APP_PORT: int = int(os.environ.get("APP_PORT", "8000"))
APP_ENV: str = os.environ.get("APP_ENV", "development")
SECRET_KEY: str = os.environ.get("SECRET_KEY", "change-me")
