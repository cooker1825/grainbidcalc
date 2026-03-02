"""
Twilio SMS webhook handler.
Receives inbound SMS/MMS at POST /api/webhooks/sms.
Passes body + any MMS media through the ingestion router.
"""

from ingestion.router import process_incoming


async def handle_sms_webhook(from_number: str, body: str, media_urls: list[str] = None) -> dict:
    """Process an inbound Twilio SMS bid."""
    return await process_incoming(
        source_type="sms",
        source_identifier=from_number,
        text_content=body,
        attachments=[],  # TODO: download MMS media from media_urls
    )
