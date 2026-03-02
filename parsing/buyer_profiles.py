"""
Per-buyer parsing hints. Passed to the LLM parser to improve accuracy.
Add a new profile whenever a new buyer source is configured.
"""

BUYER_PROFILES: dict[str, dict] = {
    "adm_windsor": {
        "name": "ADM Windsor",
        "known_commodities": ["soybeans", "corn", "srw_wheat", "canola"],
        "basis_unit": "CAD/BU",   # except canola which is CAD/MT
        "delivery_type": "delivered",
        "format_hints": (
            "HTML table with columns: Delivery, Start, End, Cash Price, Basis, "
            "Futures Month, Futures Price. CAD prices. Canola basis is in CAD/MT."
        ),
        "identifier_patterns": ["adm", "windsor"],
    },
    "g3_canada": {
        "name": "G3 Canada Limited",
        "known_commodities": ["soybeans"],
        "basis_unit": "CAD/BU",
        "delivery_type": "delivered",
        "format_hints": (
            "Spreadsheet/image with columns: Delivery, Option, CAD Basis, Futures, $/bu. "
            "Option column is futures month code (H26, K26, etc.)"
        ),
        "identifier_patterns": ["g3", "canada limited"],
    },
    "farm_market_news": {
        "name": "Farm Market News (OMAFRA)",
        "known_commodities": ["soybeans", "corn", "srw_wheat", "hrw_wheat", "swr_wheat"],
        "basis_unit": "CAD/BU",
        "delivery_type": "mixed",
        "format_hints": (
            "Multi-page PDF. Separate pages for corn, soybeans, wheat. Multiple locations per page. "
            "Futures in CBOT fractional format (e.g., 426'2s). "
            "Basis shown by location with spot/1mt/2mt/3mt columns. "
            "Exchange rate shown at top."
        ),
        "identifier_patterns": ["farm market news", "omafra"],
    },
    "great_lakes_grain": {
        "name": "Great Lakes Grain",
        "known_commodities": ["corn", "soybeans", "srw_wheat"],
        "basis_unit": "CAD/BU",
        "delivery_type": "delivered",
        "format_hints": (
            "Web printout PDF. Futures codes like @C6H, @S6H, @W6H. "
            "Clean table format. Location name in header."
        ),
        "identifier_patterns": ["great lakes", "greatlakesgrain", "dutton"],
    },
    "sarnia": {
        "name": "Sarnia Grain Buyer",
        "known_commodities": ["corn", "soybeans", "wheat_general"],
        "basis_unit": "CAD/BU",
        "delivery_type": "delivered",
        "destination": "Sarnia",
        "format_hints": (
            "Plain text email. FLAT CASH PRICES ONLY — NO basis provided. "
            "Prices are DELIVERED SARNIA. Format like '14.90 Feb 26' or '6.33 Mar/Apr 26'. "
            "May include market commentary before prices. "
            "May include an Excel/image attachment with more detailed data."
        ),
        "identifier_patterns": ["sarnia", "delivered sarnia"],
        "cash_price_only": True,  # Flag: must back-calculate basis at ingestion
    },
    "hamilton": {
        "name": "Hamilton Buyer",
        "known_commodities": ["soybeans"],
        "basis_unit": "USD/BU",   # NOTE: US basis — needs FX conversion
        "delivery_type": "delivered",
        "destination": "Hamilton",
        "format_hints": (
            "Spreadsheet image with columns: Month, CME Price, futures code (ZSEH26), "
            "US Basis, Exchange Rate, DX.Month, CAD Basis, CAD/Bu, CAD/MT. "
            "Both USD and CAD values present."
        ),
        "identifier_patterns": ["hamilton"],
    },
}


def get_profile_for_source(source_type: str, source_identifier: str, content: str = "") -> dict:
    """
    Identify the buyer profile for an incoming source.
    Matches by source_identifier (email/phone/URL) or content keywords.
    Returns the profile dict or an empty dict if unknown.
    """
    identifier_lower = (source_identifier or "").lower()
    content_lower = (content or "").lower()[:500]  # Only check first 500 chars

    for key, profile in BUYER_PROFILES.items():
        for pattern in profile.get("identifier_patterns", []):
            if pattern in identifier_lower or pattern in content_lower:
                return profile

    return {}
