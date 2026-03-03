"""
Builds personalized bid messages for each farmer.

CRITICAL RULES:
- All prices shown are MAPLEVIEW's prices (after aggression applied).
- End-buyer names (ADM, Ingredion, etc.) are NEVER included in any output.
- Delivery locations are towns/cities only (Windsor, Hamilton, London).

Three bid types presented to the farmer:
  elevator  — "Deliver to Mapleview, we pay you $X"
  delivered — "Deliver to [town], we pay you $X"
  fob       — "We pick up from your farm, we pay you $X"
"""

from datetime import date
from db.connection import get_client
from calculation.ranking import rank_bids
from calculation.exchange_rate import get_latest_exchange_rate


def build_farmer_message(
    farmer_id: str,
    commodities: list[str] | None = None,
    bid_types: list[str] | None = None,
    channel: str = "sms",
) -> str:
    """
    Build a personalized bid message for a specific farmer.
    Only includes bid types, commodities, and destinations the farmer opted into.
    Returns empty string if no matching bids are available.
    """
    prefs = _get_farmer_preferences(farmer_id, commodities, bid_types)
    if not prefs:
        return ""

    sections = _build_sections(prefs)
    if not any([sections.get("elevator"), sections.get("delivered"), sections.get("fob")]):
        return ""

    today = date.today().strftime("%b %-d, %Y")
    if channel == "sms":
        return _format_sms(sections, today)
    return _format_email(sections, today)


# ─── Internal helpers ─────────────────────────────────────────────────────────

def _get_farmer_preferences(
    farmer_id: str,
    commodities: list[str] | None,
    bid_types: list[str] | None,
) -> list[dict]:
    """Load farmer's active bid preferences from the database."""
    client = get_client()
    q = (
        client.table("farmer_bid_preferences")
        .select("*, commodities(id, name, display_name)")
        .eq("farmer_id", farmer_id)
        .eq("active", True)
    )
    if bid_types:
        q = q.in_("bid_type", bid_types)
    result = q.execute()
    prefs = result.data or []

    if commodities:
        prefs = [p for p in prefs if p["commodities"]["name"] in commodities]

    return prefs


def _build_sections(prefs: list[dict]) -> dict:
    """
    Build a dict of bid type → price lines from live ranked bids.
    Returns only sections that have live prices available.
    """
    sections: dict = {"elevator": [], "delivered": {}, "fob": []}

    try:
        get_latest_exchange_rate()  # Verify exchange rate is available
    except ValueError:
        return sections

    for pref in prefs:
        commodity = pref["commodities"]
        bid_type = pref["bid_type"]
        destination = pref.get("destination")
        delivery_months = pref.get("delivery_months")

        target_month = _nearest_delivery_month(delivery_months)
        ranked = rank_bids(commodity_id=commodity["id"], delivery_month=target_month)
        if not ranked:
            continue

        best = ranked[0]
        price = best.get("mapleview_price_cad_bu")
        if not price:
            continue

        month_label = _format_month(best.get("delivery_month", ""))
        commodity_label = commodity["display_name"]
        price_str = f"${price:.2f}/bu"

        if bid_type == "elevator":
            sections["elevator"].append(f"{commodity_label:<12} {month_label:<8} {price_str}")

        elif bid_type == "delivered":
            dest = destination or best.get("destination", "")
            if not dest:
                continue
            if dest not in sections["delivered"]:
                sections["delivered"][dest] = []
            sections["delivered"][dest].append(
                f"  {commodity_label:<12} {month_label:<8} {price_str}"
            )

        elif bid_type == "fob":
            sections["fob"].append(f"{commodity_label:<12} {month_label:<8} {price_str}")

    return sections


def _format_sms(sections: dict, today: str) -> str:
    """
    Format sections into a compact SMS message.

    Example output:
        MAPLEVIEW GRAIN — Mar 3, 2026

        ELEVATOR (Deliver to Mapleview)
        Soybeans     Oct'26   $14.45/bu
        Corn         Nov'26   $6.05/bu

        DELIVERED
          → Windsor
          Soybeans     Oct'26   $14.78/bu
          → Hamilton
          Soybeans     Oct'26   $14.64/bu

        FOB (We pick up)
        Soybeans     Oct'26   $14.20/bu

        Call/text to lock in pricing
        Mapleview Grain
    """
    lines = [f"MAPLEVIEW GRAIN — {today}", ""]

    if sections.get("elevator"):
        lines.append("ELEVATOR (Deliver to Mapleview)")
        lines.extend(sections["elevator"])
        lines.append("")

    if sections.get("delivered"):
        lines.append("DELIVERED")
        for dest, dest_lines in sections["delivered"].items():
            lines.append(f"  → {dest}")
            lines.extend(dest_lines)
        lines.append("")

    if sections.get("fob"):
        lines.append("FOB (We pick up)")
        lines.extend(sections["fob"])
        lines.append("")

    lines.append("Call/text to lock in pricing")
    lines.append("Mapleview Grain")

    return "\n".join(lines)


def _format_email(sections: dict, today: str) -> str:
    """Format sections as plain-text email body."""
    lines = [
        f"Mapleview Grain — Daily Prices — {today}",
        "=" * 50,
        "",
    ]

    if sections.get("elevator"):
        lines.append("ELEVATOR BIDS (Deliver to Mapleview Grain)")
        lines.append("-" * 40)
        lines.extend(sections["elevator"])
        lines.append("")

    if sections.get("delivered"):
        lines.append("DELIVERED BIDS")
        lines.append("-" * 40)
        for dest, dest_lines in sections["delivered"].items():
            lines.append(f"{dest}:")
            lines.extend(dest_lines)
            lines.append("")

    if sections.get("fob"):
        lines.append("FOB BIDS (We Arrange Pickup)")
        lines.append("-" * 40)
        lines.extend(sections["fob"])
        lines.append("")

    lines.extend([
        "=" * 50,
        "To lock in pricing, reply to this email or call/text.",
        "Prices subject to change without notice.",
        "",
        "Mapleview Grain",
    ])

    return "\n".join(lines)


def _nearest_delivery_month(months: list[str] | None) -> str:
    """Return the nearest upcoming delivery month from a preference list."""
    today = date.today()
    if not months:
        # Default to nearest harvest month
        if today.month <= 10:
            return f"{today.year}-10"
        return f"{today.year + 1}-10"

    today_str = today.strftime("%Y-%m")
    future = [m for m in sorted(months) if m >= today_str]
    return future[0] if future else months[0]


def _format_month(iso_month: str) -> str:
    """Convert '2026-10' → "Oct'26"."""
    month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                   "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    try:
        year, month = iso_month.split("-")
        return f"{month_names[int(month) - 1]}'{year[2:]}"
    except (ValueError, IndexError, AttributeError):
        return iso_month
