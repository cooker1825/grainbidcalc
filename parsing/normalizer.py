"""
Normalizes parsed bid data: units, futures contract codes, delivery months.
"""

from typing import Any

# CAD/BU conversion factors (bushels per tonne)
BUSHELS_PER_TONNE: dict[str, float] = {
    "soybeans":  36.7437,
    "corn":      39.3680,
    "srw_wheat": 36.7437,
    "hrw_wheat": 36.7437,
    "swr_wheat": 36.7437,
    "canola":    44.0920,
    "wheat_general": 36.7437,
}

# Standard commodity → futures prefix mapping
FUTURES_PREFIX: dict[str, str] = {
    "soybeans":      "ZS",
    "corn":          "ZC",
    "srw_wheat":     "ZW",
    "hrw_wheat":     "KE",
    "swr_wheat":     "ZW",
    "wheat_general": "ZW",
    "canola":        "RS",
}

# Harvest month by commodity
HARVEST_MONTHS: dict[str, str] = {
    "soybeans":      "10",
    "corn":          "11",
    "srw_wheat":     "07",
    "hrw_wheat":     "07",
    "swr_wheat":     "07",
    "wheat_general": "07",
    "canola":        "08",
}


def normalize_basis_to_cad_bu(
    basis_value: float,
    basis_unit: str,
    commodity: str,
    exchange_rate: float,
) -> float:
    """
    Convert any basis to CAD/BU for apples-to-apples ranking.

    CAD Basis = CAD Cash - USD Futures (simple subtraction).
    The basis unit tells us what currency/unit the basis is expressed in.
    """
    if basis_unit == "CAD/BU":
        return basis_value

    if basis_unit == "USD/BU":
        # Approximate conversion — flag for review if encountered
        return basis_value * exchange_rate

    if basis_unit == "CAD/MT":
        bu_per_mt = BUSHELS_PER_TONNE.get(commodity)
        if not bu_per_mt:
            raise ValueError(f"No conversion factor for commodity: {commodity}")
        return basis_value / bu_per_mt

    raise ValueError(f"Unknown basis unit: {basis_unit}")


def normalize_futures_contract(raw: str, commodity: str) -> str:
    """
    Normalize any futures contract code to standard CBOT/ICE format.

    Examples:
        @C6H   → ZCH26  (Great Lakes format)
        H26    → ZSH26  (G3 format, needs commodity context)
        ZSEH26 → ZSH26  (some sources add exchange code)
        ZSH26  → ZSH26  (already standard)
    """
    raw = raw.strip()

    # Great Lakes format: @C6H → ZCH26
    if raw.startswith("@") and len(raw) == 4:
        commodity_map = {"C": "ZC", "S": "ZS", "W": "ZW"}
        c = raw[1]
        year = raw[2]
        month = raw[3]
        prefix = commodity_map.get(c, "??")
        return f"{prefix}{month}2{year}"

    # Short format: H26 → needs commodity prefix
    if len(raw) == 3 and raw[0].isalpha() and raw[1:].isdigit():
        prefix = FUTURES_PREFIX.get(commodity, "??")
        return f"{prefix}{raw}"

    # Exchange-prefixed: ZSEH26 → ZSH26
    if len(raw) == 6 and raw[:3] in ("ZSE", "ZCE", "ZWE", "KEE"):
        return raw[:2] + raw[3:]

    return raw.upper()


def parse_fractional_futures(raw: str) -> float:
    """
    Convert CBOT fractional notation to decimal.

    Examples:
        "426'2s" → 4.2625   (426 + 2/8 = 426.25 cents = $4.2625/bu)
        "1134'0" → 11.3400
        "11.375" → 11.375   (already decimal, pass through)
    """
    clean = raw.replace("s", "").replace("S", "").strip()
    if "'" in clean:
        whole, frac = clean.split("'")
        cents = int(whole)
        eighths = int(frac)
        return (cents + eighths / 8) / 100
    return float(clean)


def normalize_delivery_month(label: str, commodity: str, year_hint: int = 2026) -> str:
    """
    Normalize a delivery label to ISO YYYY-MM format.

    Examples:
        "Feb'26"        → "2026-02"
        "Oct'26 (Harvest)" → "2026-10"
        "Harvest"       → commodity-specific harvest month
        "N/C 27"        → commodity harvest month for 2027
    """
    label_lower = label.lower().strip()

    month_map = {
        "jan": "01", "feb": "02", "mar": "03", "apr": "04",
        "may": "05", "jun": "06", "jul": "07", "aug": "08",
        "sep": "09", "oct": "10", "nov": "11", "dec": "12",
    }

    # Handle harvest / new crop labels
    if "harvest" in label_lower or "n/c" in label_lower:
        harvest_month = HARVEST_MONTHS.get(commodity, "10")
        # Extract year if present
        for part in label.split():
            if part.isdigit() and len(part) == 2:
                return f"20{part}-{harvest_month}"
            if part.isdigit() and len(part) == 4:
                return f"{part}-{harvest_month}"
        return f"{year_hint}-{harvest_month}"

    # Try to extract month name and year
    parts = label.replace("'", " ").split()
    found_month = None
    found_year = None

    for part in parts:
        p = part.lower().rstrip(".,")
        if p[:3] in month_map:
            found_month = month_map[p[:3]]
        if p.isdigit():
            if len(p) == 2:
                found_year = f"20{p}"
            elif len(p) == 4:
                found_year = p

    if found_month and found_year:
        return f"{found_year}-{found_month}"

    # Fall back: return as-is with a note
    return label


def normalize_bids(bids: list[dict[str, Any]], exchange_rate: float = 1.37) -> list[dict[str, Any]]:
    """
    Run all normalization steps on a list of parsed bids.
    exchange_rate is used only for USD/BU → CAD/BU conversion (rare).
    """
    normalized = []
    for bid in bids:
        bid = dict(bid)

        # Normalize futures contract
        if bid.get("futures_contract_raw") and not bid.get("futures_contract_normalized"):
            bid["futures_contract_normalized"] = normalize_futures_contract(
                bid["futures_contract_raw"], bid.get("commodity", "")
            )

        # Normalize delivery month
        if bid.get("delivery_label") and not bid.get("delivery_month"):
            bid["delivery_month"] = normalize_delivery_month(
                bid["delivery_label"], bid.get("commodity", "")
            )

        # Normalize basis to CAD/BU for ranking
        if bid.get("basis_value") is not None:
            bid["basis_normalized_cad_bu"] = normalize_basis_to_cad_bu(
                bid["basis_value"],
                bid.get("basis_unit", "CAD/BU"),
                bid.get("commodity", ""),
                exchange_rate,
            )

        normalized.append(bid)
    return normalized
