"""
Builds personalized bid messages for each farmer.

CRITICAL: All prices shown are MAPLEVIEW's prices (after aggression applied).
End-buyer names (ADM, Ingredion, etc.) are NEVER included.
Delivery locations are towns/cities only (Windsor, Hamilton, London).

Three bid types:
  elevator  — "Deliver to Mapleview, we pay you $X"
  delivered — "Deliver to [town], we pay you $X"
  fob       — "We pick up from your farm, we pay you $X"
"""

from db.connection import get_client
from calculation.ranking import rank_bids


def build_farmer_message(
    farmer_id: str,
    commodities: list[str] | None = None,
    bid_types: list[str] | None = None,
) -> str:
    """
    Build a personalized SMS/email message for a farmer based on their preferences.
    Returns formatted text. End-buyer names are never included.
    """
    # TODO: Load farmer preferences and build personalized message
    # See architecture.md Section 11 for formatting spec and example output
    raise NotImplementedError


def format_sms_message(sections: dict) -> str:
    """Format bid sections into a compact SMS string."""
    # TODO: Format per architecture.md Section 11.1
    raise NotImplementedError


def format_email_message(sections: dict) -> str:
    """Format bid sections into a detailed HTML/text email."""
    raise NotImplementedError
