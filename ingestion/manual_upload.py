"""API endpoint handler for manual PDF/image/text upload."""

from ingestion.router import process_incoming


async def handle_manual_upload(
    file_bytes: bytes,
    filename: str,
    content_type: str,
    buyer_name: str = "",
) -> dict:
    """Process a manually uploaded bid file."""
    return await process_incoming(
        source_type="manual",
        source_identifier=buyer_name or "manual_upload",
        attachments=[(filename, file_bytes, content_type)],
    )
