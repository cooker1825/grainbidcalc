"""
Integration tests for the LLM parser.
Run against real sample bid sheets in tests/sample_data/.
These tests require ANTHROPIC_API_KEY in environment.
"""

import pytest
import json
from pathlib import Path

SAMPLE_DATA = Path(__file__).parent / "sample_data"


@pytest.mark.integration
def test_parse_adm_windsor_email():
    """Parse a sample ADM Windsor email and verify structure."""
    sample = SAMPLE_DATA / "adm_windsor.txt"
    if not sample.exists():
        pytest.skip("No ADM Windsor sample data")

    from parsing.llm_parser import parse_bid_sheet
    bids = parse_bid_sheet(
        content=sample.read_text(),
        source_type="email",
        buyer_hint="ADM Windsor — HTML table format, CAD/BU",
    )
    assert len(bids) > 0
    for bid in bids:
        assert bid.get("commodity") in ("soybeans", "corn", "canola", "srw_wheat")
        assert bid.get("delivery_month") is not None
        assert bid.get("basis_value") is not None or bid.get("cash_price") is not None
        assert bid.get("confidence", 0) >= 0.7


@pytest.mark.integration
def test_parse_sarnia_cash_only():
    """Sarnia email: should return cash_price with null basis_value."""
    sample = SAMPLE_DATA / "sarnia_email.txt"
    if not sample.exists():
        pytest.skip("No Sarnia sample data")

    from parsing.llm_parser import parse_bid_sheet
    bids = parse_bid_sheet(
        content=sample.read_text(),
        source_type="email",
        buyer_hint="Sarnia — flat cash prices only, no basis",
    )
    assert len(bids) > 0
    for bid in bids:
        assert bid.get("basis_value") is None, "Sarnia should have no basis in raw parse"
        assert bid.get("cash_price") is not None
