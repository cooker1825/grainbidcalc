"""
Google Workspace API — outbound bid email distribution to farmers.
Sends from markets@mapleviewgrain.ca using a service account with domain-wide delegation.
"""

import base64
import logging
import os
from email.mime.text import MIMEText

from google.oauth2 import service_account
from googleapiclient.discovery import build

from config.settings import GOOGLE_SERVICE_ACCOUNT_JSON, GMAIL_TARGET_EMAIL

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/gmail.send"]

_service = None


def _get_gmail_service():
    global _service
    if _service is None:
        creds = service_account.Credentials.from_service_account_file(
            GOOGLE_SERVICE_ACCOUNT_JSON, scopes=SCOPES
        )
        # Impersonate the markets@ inbox so mail comes from that address
        delegated = creds.with_subject(GMAIL_TARGET_EMAIL)
        _service = build("gmail", "v1", credentials=delegated)
    return _service


async def send_email(to_address: str, subject: str, body: str) -> None:
    """
    Send a bid distribution email via Google Workspace (markets@mapleviewgrain.ca).
    """
    service = _get_gmail_service()

    mime = MIMEText(body, "plain")
    mime["to"] = to_address
    mime["from"] = GMAIL_TARGET_EMAIL
    mime["subject"] = subject

    raw = base64.urlsafe_b64encode(mime.as_bytes()).decode()

    service.users().messages().send(
        userId="me",
        body={"raw": raw},
    ).execute()

    logger.info("Email sent to %s — %s", to_address, subject)
