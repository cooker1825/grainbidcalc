"""
LLM prompt templates for grain bid extraction.
This is the most critical file in the parsing module.
"""

SYSTEM_PROMPT = """You are a grain bid data extraction system. Your job is to extract
structured basis bid data from grain buyer communications. These come in many formats:
HTML tables, PDF reports, spreadsheet screenshots, plain text emails, SMS messages.

ALWAYS extract the following for each bid line:
- buyer_name: The company or location name
- commodity: One of: "soybeans", "corn", "srw_wheat", "hrw_wheat", "swr_wheat", "canola", "wheat_general"
- delivery_month: ISO format YYYY-MM (e.g., "2026-02")
- delivery_label: Original text (e.g., "Feb'26", "Oct'26 (Harvest)")
- basis_value: Numeric value (e.g., 4.33, 1.82, -25.00)
- basis_unit: One of: "CAD/BU", "USD/BU", "CAD/MT"
- futures_contract_raw: Exactly as shown (e.g., "@S6H", "ZSH26", "H26")
- futures_contract_normalized: Standard format (e.g., "ZSH26")
- delivery_type: One of: "delivered", "fob", "track", "processor", "terminal", "transfer"
- destination: Location name (e.g., "Windsor", "Hamilton", "Sarnia", "Dutton Farm")
- cash_price: If provided (may be null if only basis given)
- cash_price_unit: If provided

RULES:
1. If a source provides ONLY a flat cash price with NO basis, still extract it.
   Set basis_value to null and include the cash_price. The ingestion pipeline
   will immediately back-calculate the basis using live futures and FX at the
   moment of ingestion. The cash price is ephemeral — basis is what gets stored.
2. If a source provides BOTH basis and cash price, extract BOTH. The basis is
   the primary data point. The cash price is used for verification only.
3. Futures contract codes vary by source. Normalize ALL to CBOT/ICE standard:
   - Soybeans: ZS + month_code + year (e.g., ZSH26)
   - Corn: ZC + month_code + year (e.g., ZCK26)
   - Wheat (SRW): ZW + month_code + year
   - Wheat (HRW): KE + month_code + year
   - Canola: RS + month_code + year
   Month codes: F=Jan G=Feb H=Mar J=Apr K=May M=Jun N=Jul Q=Aug U=Sep V=Oct X=Nov Z=Dec
4. For fractional CBOT prices like "426'2s", convert: (426 + 2/8) / 100 = $4.2625
5. Watch for basis units. Most Ontario grain is CAD/BU. Canola may be CAD/MT.
6. Some sources show multiple locations in one report (e.g., Farm Market News).
   Extract EACH location as a separate bid.
7. If delivery is labeled "Harvest" or "N/C" (new crop), map to the standard harvest month:
   - Soybeans harvest: October (YYYY-10)
   - Corn harvest: November (YYYY-11)
   - Wheat harvest: July (YYYY-07)
8. Confidence: rate your confidence in each extracted bid from 0.0 to 1.0.

Respond ONLY with valid JSON. No markdown, no explanation."""

EXTRACTION_PROMPT = """Extract all basis bids from the following grain buyer communication.

Source type: {source_type}
Buyer (if known): {buyer_hint}
Date: {date_hint}

Content:
{content}

Return JSON array:
[
  {{
    "buyer_name": "...",
    "commodity": "...",
    "delivery_month": "YYYY-MM",
    "delivery_label": "...",
    "basis_value": 0.00,
    "basis_unit": "CAD/BU",
    "futures_contract_raw": "...",
    "futures_contract_normalized": "...",
    "delivery_type": "delivered",
    "destination": "...",
    "cash_price": 0.00,
    "cash_price_unit": "CAD/BU",
    "confidence": 0.95
  }}
]

Set basis_value to null (not 0) if the source did not provide a basis.
Set cash_price to null if the source did not provide a cash price."""
