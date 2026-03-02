"""
Distribution engine. Queries farmer preferences and sends personalized messages.
See architecture.md Section 11.2 for full spec.
"""

from db.connection import get_client
from distribution.formatter import build_farmer_message
from distribution.sms_sender import send_sms
from distribution.email_sender import send_email


async def distribute_bids(
    trigger: str,
    commodities: list[str] | None = None,
    bid_types: list[str] | None = None,
) -> dict:
    """
    Send bid updates to all farmers with matching preferences.
    All prices sent are Mapleview's prices — never raw buyer bids or buyer names.
    """
    # TODO: Implement per architecture.md Section 11.2
    raise NotImplementedError
