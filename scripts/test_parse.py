"""
Quick manual test: parse a bid sheet and print results.
Usage: python scripts/test_parse.py tests/sample_data/adm_windsor.txt email "ADM Windsor"
"""

import sys
import json
from pathlib import Path


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/test_parse.py <file_path> [source_type] [buyer_hint]")
        sys.exit(1)

    file_path = Path(sys.argv[1])
    source_type = sys.argv[2] if len(sys.argv) > 2 else "email"
    buyer_hint = sys.argv[3] if len(sys.argv) > 3 else ""

    content = None
    image_bytes = None
    media_type = "image/png"

    if file_path.suffix.lower() in (".png", ".jpg", ".jpeg"):
        image_bytes = file_path.read_bytes()
        media_type = f"image/{file_path.suffix.lstrip('.').lower()}"
    elif file_path.suffix.lower() == ".pdf":
        from ingestion.preprocessor import preprocess
        pieces = preprocess(None, [(file_path.name, file_path.read_bytes(), "application/pdf")])
        content = "\n\n".join(p.get("text", "") for p in pieces if p.get("text"))
    else:
        content = file_path.read_text()

    from parsing.llm_parser import parse_bid_sheet
    from parsing.normalizer import normalize_bids
    from parsing.validator import validate_bids

    print(f"\nParsing {file_path.name}...\n")
    bids = parse_bid_sheet(
        content=content,
        image_bytes=image_bytes,
        image_media_type=media_type,
        source_type=source_type,
        buyer_hint=buyer_hint,
    )

    normalized = normalize_bids(bids)
    validated = validate_bids(normalized)

    print(json.dumps(validated, indent=2, default=str))
    print(f"\n→ {len(validated)} bids parsed.")
    needs_review = [b for b in validated if b.get("needs_review")]
    if needs_review:
        print(f"⚠ {len(needs_review)} bid(s) need review.")


if __name__ == "__main__":
    main()
