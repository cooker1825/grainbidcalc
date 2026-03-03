"""
Gmail API listener for markets@mapleviewgrain.ca.
Polls for new unread messages, processes each through the ingestion router,
then labels them as processed or errored.

Polling interval: every 5 minutes via Celery beat.
Auth: service account with domain-wide delegation (same pattern as grainbot).
"""

import base64
import logging
import time

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from config.settings import GOOGLE_SERVICE_ACCOUNT_JSON, GMAIL_TARGET_EMAIL
from ingestion.router import process_incoming

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.modify",
]

PROCESSED_LABEL = "GrainBidCalc/Processed"
ERROR_LABEL = "GrainBidCalc/Error"
MAX_RESULTS = 20
RETRY_COUNT = 3
RETRY_DELAY = 2

_service = None


def _get_service():
    global _service
    if _service is None:
        creds = service_account.Credentials.from_service_account_file(
            GOOGLE_SERVICE_ACCOUNT_JSON, scopes=SCOPES
        )
        delegated = creds.with_subject(GMAIL_TARGET_EMAIL)
        _service = build("gmail", "v1", credentials=delegated)
    return _service


def _retry(func, *args, **kwargs):
    """Call a Gmail API function with exponential backoff retry."""
    for attempt in range(RETRY_COUNT):
        try:
            return func(*args, **kwargs)
        except HttpError as e:
            if attempt == RETRY_COUNT - 1:
                raise
            wait = RETRY_DELAY * (2 ** attempt)
            logger.warning("Gmail API error (attempt %d/%d), retrying in %ds: %s",
                           attempt + 1, RETRY_COUNT, wait, e)
            time.sleep(wait)


def _get_or_create_label(service, label_name: str) -> str:
    result = _retry(service.users().labels().list(userId="me").execute)
    for label in result.get("labels", []):
        if label["name"] == label_name:
            return label["id"]
    created = _retry(
        service.users().labels().create(
            userId="me",
            body={"name": label_name, "labelListVisibility": "labelShow",
                  "messageListVisibility": "show"},
        ).execute
    )
    return created["id"]


def _apply_label(service, message_id: str, label_name: str):
    label_id = _get_or_create_label(service, label_name)
    _retry(
        service.users().messages().modify(
            userId="me", id=message_id,
            body={"addLabelIds": [label_id]},
        ).execute
    )


def _fetch_unprocessed_messages(service) -> list[dict]:
    processed_slug = PROCESSED_LABEL.replace("/", "-")
    error_slug = ERROR_LABEL.replace("/", "-")
    query = f"in:inbox -label:{processed_slug} -label:{error_slug} newer_than:7d"

    messages = []
    page_token = None
    while True:
        kwargs = {"userId": "me", "q": query, "maxResults": MAX_RESULTS}
        if page_token:
            kwargs["pageToken"] = page_token
        result = _retry(service.users().messages().list(**kwargs).execute)
        messages.extend(result.get("messages", []))
        page_token = result.get("nextPageToken")
        if not page_token:
            break
    return messages


def _extract_message(service, message_id: str) -> dict:
    msg = _retry(
        service.users().messages().get(userId="me", id=message_id, format="full").execute
    )
    headers = {h["name"].lower(): h["value"]
               for h in msg.get("payload", {}).get("headers", [])}

    body_text = body_html = ""
    attachments = []

    def _walk(payload):
        nonlocal body_text, body_html
        mime = payload.get("mimeType", "")
        body = payload.get("body", {})
        parts = payload.get("parts", [])
        filename = payload.get("filename", "")

        if filename and body.get("attachmentId"):
            att_data = _retry(
                service.users().messages().attachments().get(
                    userId="me", messageId=message_id, id=body["attachmentId"]
                ).execute
            )
            file_bytes = base64.urlsafe_b64decode(att_data["data"])
            attachments.append((filename, file_bytes, mime))
        elif not parts:
            data = body.get("data", "")
            if data:
                decoded = base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
                if mime == "text/plain":
                    body_text += decoded
                elif mime == "text/html":
                    body_html += decoded
        else:
            for part in parts:
                _walk(part)

    _walk(msg.get("payload", {}))
    return {
        "message_id": message_id,
        "sender": headers.get("from", ""),
        "subject": headers.get("subject", ""),
        "body": body_text or body_html,
        "attachments": attachments,
    }


async def poll_email_inbox() -> dict:
    """
    Check markets@mapleviewgrain.ca for new unread bid emails.
    Processes each through the ingestion router, then labels it.
    Called every 5 minutes by Celery beat.
    """
    service = _get_service()
    stubs = _fetch_unprocessed_messages(service)

    if not stubs:
        logger.info("Email poll: no new messages.")
        return {"processed": 0, "errors": 0}

    logger.info("Email poll: found %d new message(s).", len(stubs))
    processed = errors = 0

    for stub in stubs:
        message_id = stub["id"]
        try:
            msg = _extract_message(service, message_id)
            result = await process_incoming(
                source_type="email",
                source_identifier=msg["sender"],
                text_content=msg["body"],
                attachments=msg["attachments"],
            )
            _apply_label(service, message_id, PROCESSED_LABEL)
            logger.info("Processed email %s → %d bids stored",
                        message_id, result.get("stored", 0))
            processed += 1
        except Exception as e:
            logger.error("Failed to process email %s: %s", message_id, e)
            try:
                _apply_label(service, message_id, ERROR_LABEL)
            except Exception:
                pass
            errors += 1

    return {"processed": processed, "errors": errors}
