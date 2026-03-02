"""
Preprocesses raw content into text and image pieces for the LLM parser.
Handles: plain text, HTML, PDFs (text extraction + scanned page → image), attachments.
"""

import io
from typing import Any

import pdfplumber
from PIL import Image
from pdf2image import convert_from_bytes


def preprocess(
    text_content: str | None,
    attachments: list[tuple[str, bytes, str]],
) -> list[dict[str, Any]]:
    """
    Returns a list of content pieces, each a dict with optional 'text' and 'image' keys.
    attachments: list of (filename, bytes, content_type)
    """
    pieces = []

    # Plain text / HTML body
    if text_content and text_content.strip():
        pieces.append({"text": text_content})

    # Process attachments
    for filename, file_bytes, content_type in attachments:
        if content_type == "application/pdf" or filename.lower().endswith(".pdf"):
            pieces.extend(_process_pdf(file_bytes))
        elif content_type.startswith("image/"):
            pieces.append({"image": file_bytes, "media_type": content_type})
        elif "spreadsheet" in content_type or filename.lower().endswith((".xlsx", ".xls")):
            # TODO: Excel parsing — extract as text for now
            pieces.append({"text": f"[Excel attachment: {filename} — manual review needed]"})

    return pieces


def _process_pdf(pdf_bytes: bytes) -> list[dict]:
    """Extract text from PDF pages. Convert low-text pages to images for vision."""
    pieces = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for i, page in enumerate(pdf.pages):
            text = page.extract_text() or ""
            if len(text.strip()) > 50:
                pieces.append({"text": text})
            else:
                # Scanned page — convert to image for Claude vision
                images = convert_from_bytes(pdf_bytes, first_page=i + 1, last_page=i + 1)
                if images:
                    img_bytes = io.BytesIO()
                    images[0].save(img_bytes, format="PNG")
                    pieces.append({"image": img_bytes.getvalue(), "media_type": "image/png"})
    return pieces
