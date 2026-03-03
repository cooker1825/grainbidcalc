"""
Distribution engine. Queries farmer preferences and sends personalized messages.
All prices sent are Mapleview's prices — never raw buyer bids or buyer names.
"""

import logging
from db.connection import get_client
from distribution.formatter import build_farmer_message
from distribution.sms_sender import send_sms
from distribution.email_sender import send_email

logger = logging.getLogger(__name__)


async def distribute_bids(
    trigger: str,
    commodities: list[str] | None = None,
    bid_types: list[str] | None = None,
) -> dict:
    """
    Send personalized bid updates to all farmers with matching preferences.

    For each farmer:
      1. Build a personalized message containing only their opted-in bid types,
         commodities, and destinations — at Mapleview's prices (after margin).
      2. Send via their preferred channel (sms, email, or both).
      3. Log the distribution event.

    End-buyer names are never included anywhere in this pipeline.
    """
    farmers = _get_farmers_for_distribution(commodities, bid_types)
    if not farmers:
        logger.info("No farmers matched for distribution (trigger=%s)", trigger)
        return {"trigger": trigger, "sent": 0, "skipped": 0, "errors": 0}

    sent = skipped = errors = 0

    for farmer in farmers:
        try:
            channel = farmer.get("preferred_channel", "sms")

            if channel in ("sms", "both"):
                message = build_farmer_message(
                    farmer_id=farmer["id"],
                    commodities=commodities,
                    bid_types=bid_types,
                    channel="sms",
                )
                if message and farmer.get("phone"):
                    send_sms(farmer["phone"], message)
                    logger.info("SMS sent to farmer %s (%s)", farmer["name"], farmer["phone"])
                    sent += 1
                else:
                    skipped += 1

            if channel in ("email", "both"):
                message = build_farmer_message(
                    farmer_id=farmer["id"],
                    commodities=commodities,
                    bid_types=bid_types,
                    channel="email",
                )
                if message and farmer.get("email"):
                    await send_email(
                        to_address=farmer["email"],
                        subject="Mapleview Grain — Daily Prices",
                        body=message,
                    )
                    logger.info("Email sent to farmer %s (%s)", farmer["name"], farmer["email"])
                    sent += 1
                else:
                    skipped += 1

        except Exception as e:
            logger.error("Failed to send to farmer %s: %s", farmer.get("name"), e)
            errors += 1

    _log_distribution(trigger, sent, commodities, bid_types)

    return {"trigger": trigger, "sent": sent, "skipped": skipped, "errors": errors}


def _get_farmers_for_distribution(
    commodities: list[str] | None,
    bid_types: list[str] | None,
) -> list[dict]:
    """Return all active farmers who have preferences matching the given commodities/bid_types."""
    client = get_client()

    # Get all active farmers who have at least one matching preference
    pref_q = (
        client.table("farmer_bid_preferences")
        .select("farmer_id")
        .eq("active", True)
    )
    if bid_types:
        pref_q = pref_q.in_("bid_type", bid_types)

    pref_result = pref_q.execute()
    if not pref_result.data:
        return []

    farmer_ids = list({row["farmer_id"] for row in pref_result.data})

    farmer_result = (
        client.table("farmer_contacts")
        .select("id, name, phone, email, preferred_channel")
        .in_("id", farmer_ids)
        .eq("active", True)
        .execute()
    )
    return farmer_result.data or []


def _log_distribution(
    trigger: str,
    recipient_count: int,
    commodities: list[str] | None,
    bid_types: list[str] | None,
) -> None:
    """Write a row to distribution_log."""
    client = get_client()
    channel = "sms"  # Could be mixed — simplified for log
    client.table("distribution_log").insert({
        "distribution_type": trigger.split(":")[0],
        "channel": channel,
        "bid_type": ",".join(bid_types) if bid_types else None,
        "recipient_count": recipient_count,
        "commodities": commodities,
        "triggered_by": trigger,
    }).execute()
