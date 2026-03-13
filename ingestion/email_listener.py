"""
IMAP email listener for markets@mapleviewgrain.ca.
Polls for new unread messages in INBOX, processes each through the ingestion router,
then marks them as seen (read).

Works with any IMAP server (HostPapa, cPanel, etc.) — no OAuth or Google Cloud needed.
Polling interval: every 5 minutes via Celery beat.
"""

import email
import imaplib
import logging
import ssl
from email.header import decode_header
from email.message import Message

from config.settings import IMAP_HOST, IMAP_PORT, IMAP_USER, IMAP_PASSWORD
from ingestion.router import process_incoming

logger = logging.getLogger(__name__)


def _decode_header_value(value: str) -> str:
    parts = decode_header(value or "")
    decoded = []
    for part, charset in parts:
        if isinstance(part, bytes):
            decoded.append(part.decode(charset or "utf-8", errors="replace"))
        else:
            decoded.append(part)
    return "".join(decoded)


def _extract_parts(msg: Message) -> tuple[str, list]:
    """Walk the email MIME tree and extract text body and attachments."""
    body = ""
    attachments = []

    for part in msg.walk():
        content_type = part.get_content_type()
        disposition = part.get("Content-Disposition", "")
        filename = part.get_filename()

        if filename:
            # It's an attachment
            payload = part.get_payload(decode=True)
            if payload:
                attachments.append((filename, payload, content_type))
        elif content_type == "text/plain" and "attachment" not in disposition:
            payload = part.get_payload(decode=True)
            if payload:
                charset = part.get_content_charset() or "utf-8"
                body += payload.decode(charset, errors="replace")
        elif content_type == "text/html" and not body and "attachment" not in disposition:
            # Fall back to HTML if no plain text
            payload = part.get_payload(decode=True)
            if payload:
                charset = part.get_content_charset() or "utf-8"
                body += payload.decode(charset, errors="replace")

    return body, attachments


def _connect() -> imaplib.IMAP4_SSL:
    ctx = ssl.create_default_context()
    conn = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT, ssl_context=ctx)
    conn.login(IMAP_USER, IMAP_PASSWORD)
    return conn


async def poll_email_inbox() -> dict:
    """
    Check INBOX for unread messages, process each through the ingestion router,
    then mark as read. Called every 5 minutes by Celery beat.
    """
    if not IMAP_PASSWORD:
        logger.warning("IMAP_PASSWORD not set — skipping email poll")
        return {"processed": 0, "errors": 0, "skipped": "no_credentials"}

    try:
        conn = _connect()
    except Exception as e:
        logger.error("IMAP connection failed: %s", e)
        return {"processed": 0, "errors": 1, "error": str(e)}

    processed = errors = 0

    try:
        conn.select("INBOX")
        # Search for unread (UNSEEN) messages
        status, data = conn.search(None, "UNSEEN")
        if status != "OK":
            return {"processed": 0, "errors": 0}

        msg_ids = data[0].split()
        if not msg_ids:
            logger.info("Email poll: no new messages.")
            return {"processed": 0, "errors": 0}

        logger.info("Email poll: found %d unread message(s).", len(msg_ids))

        for msg_id in msg_ids:
            try:
                status, raw = conn.fetch(msg_id, "(RFC822)")
                if status != "OK" or not raw or not raw[0]:
                    continue

                raw_bytes = raw[0][1]
                msg = email.message_from_bytes(raw_bytes)

                sender = _decode_header_value(msg.get("From", ""))
                subject = _decode_header_value(msg.get("Subject", ""))
                body, attachments = _extract_parts(msg)

                logger.info("Processing email from %s: %s", sender, subject)

                result = await process_incoming(
                    source_type="email",
                    source_identifier=sender,
                    text_content=body,
                    attachments=attachments,
                )

                # Mark as read
                conn.store(msg_id, "+FLAGS", "\\Seen")

                logger.info("Processed email %s → %d bids stored",
                            msg_id.decode(), result.get("stored", 0))
                processed += 1

            except Exception as e:
                logger.error("Failed to process email %s: %s", msg_id, e)
                errors += 1

    finally:
        try:
            conn.logout()
        except Exception:
            pass

    return {"processed": processed, "errors": errors}


async def test_connection() -> dict:
    """Test IMAP credentials. Returns inbox message count."""
    conn = _connect()
    conn.select("INBOX")
    status, data = conn.search(None, "ALL")
    total = len(data[0].split()) if status == "OK" and data[0] else 0
    status2, data2 = conn.search(None, "UNSEEN")
    unread = len(data2[0].split()) if status2 == "OK" and data2[0] else 0
    conn.logout()
    return {"total": total, "unread": unread, "host": IMAP_HOST, "user": IMAP_USER}
