"""
LLM-based bid sheet parser using Claude API.
Handles any format: HTML tables, PDFs, images, plain text, SMS.
"""

import json
import base64
from datetime import date
from typing import Any

import anthropic

from parsing.prompt_templates import SYSTEM_PROMPT, EXTRACTION_PROMPT
from config.settings import ANTHROPIC_API_KEY

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


def parse_bid_sheet(
    content: str | None = None,
    image_bytes: bytes | None = None,
    image_media_type: str = "image/png",
    source_type: str = "email",
    buyer_hint: str = "",
    date_hint: str = "",
) -> list[dict[str, Any]]:
    """
    Parse any bid sheet format into structured bid data using Claude.

    Args:
        content: Text content (email body, PDF text, HTML, etc.)
        image_bytes: Raw image bytes (screenshot, scanned PDF page)
        image_media_type: MIME type of the image
        source_type: "email", "sms", "web_scrape", "manual"
        buyer_hint: JSON string of buyer profile hints
        date_hint: Date string for context (e.g., "2026-02-20")

    Returns:
        List of extracted bid dicts. basis_value may be None for cash-price-only sources.
    """
    if not date_hint:
        date_hint = date.today().isoformat()

    messages_content: list[dict] = []

    # Add image first if provided (for screenshots, scanned PDF pages)
    if image_bytes:
        messages_content.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": image_media_type,
                "data": base64.b64encode(image_bytes).decode(),
            },
        })

    # Add text prompt
    text_content = content or "[See attached image]"
    messages_content.append({
        "type": "text",
        "text": EXTRACTION_PROMPT.format(
            source_type=source_type,
            buyer_hint=buyer_hint,
            date_hint=date_hint,
            content=text_content,
        ),
    })

    response = client.beta.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=16000,
        betas=["output-128k-2025-02-19"],
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": messages_content}],
    )

    raw_text = response.content[0].text

    # Extract JSON array — find first [ and last ]
    start = raw_text.find("[")
    if start == -1:
        raise ValueError(f"No JSON array found in parser response: {raw_text[:200]}")

    end = raw_text.rfind("]")
    if end == -1:
        # Response was truncated (hit token limit) — recover by keeping complete objects
        last_brace = raw_text.rfind("}")
        if last_brace == -1:
            raise ValueError(f"Parser response has no complete objects: {raw_text[:200]}")
        clean = raw_text[start:last_brace + 1] + "]"
    else:
        clean = raw_text[start:end + 1]

    bids = json.loads(clean)
    return bids
