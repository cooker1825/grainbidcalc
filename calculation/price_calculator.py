"""
Core pricing math for GrainBidCalc.

Three basis values tracked for every bid:

  CAD Basis   = CAD Cash Price − USD Futures Price        (simple subtraction, no FX)
                → What the buyer publishes. FX is embedded in this number.
                → Stored as the durable data point.

  US Basis    = (CAD Cash Price ÷ FX Rate) − USD Futures  (strips out currency)
                → True local demand vs US market. Always calculated live.
                → Strong US Basis = buyer urgently needs grain.

  Mapleview   = CAD Basis + Aggression Adjustment
  Basis         → What Mapleview markets to farmers.

  Live Cash   = USD Futures + Stored CAD Basis            (calculated on the fly)
  Price         → NEVER stored. Always recalculated with live futures.
"""

from datetime import datetime, timezone
from parsing.normalizer import BUSHELS_PER_TONNE


def calculate_us_basis(
    cad_basis: float,
    futures_price_usd_bu: float,
    exchange_rate: float,
) -> float:
    """
    US Basis = (CAD Cash Price ÷ FX Rate) − USD Futures

    Since CAD Cash = USD Futures + CAD Basis:
        US Basis = ((USD Futures + CAD Basis) / FX Rate) - USD Futures

    Example (ADM Windsor, stored CAD Basis = 4.33):
        Live Futures (ZSH26): 11.375
        Live FX: 1.369
        CAD Cash = 11.375 + 4.33 = 15.705
        US Cash  = 15.705 / 1.369 = 11.472
        US Basis = 11.472 - 11.375 = +0.097 USD/BU
    """
    cad_cash = futures_price_usd_bu + cad_basis
    us_cash = cad_cash / exchange_rate
    us_basis = us_cash - futures_price_usd_bu
    return round(us_basis, 4)


def back_calculate_basis_from_cash(
    cash_price_cad: float,
    futures_price_usd: float,
    exchange_rate: float,
    timestamp: str | None = None,
) -> dict:
    """
    Back-calculate basis from a cash-price-only source (e.g., Sarnia email).

    CRITICAL: Must be called at the EXACT MOMENT the bid is ingested, using
    live futures and FX. The result is stored; the cash price is not.

    CAD Basis = CAD Cash Price − USD Futures Price  (simple subtraction)
    US Basis  = (CAD Cash Price ÷ FX Rate) − USD Futures Price

    Example (Sarnia, Soybeans Feb'26):
        Cash: 14.90 CAD/BU
        Futures at ingestion (ZSH26): 11.41 USD/BU
        FX at ingestion: 1.369

        CAD Basis = 14.90 - 11.41 = 3.49 CAD/BU
        US Cash   = 14.90 / 1.369 = 10.884 USD/BU
        US Basis  = 10.884 - 11.41 = -0.526 USD/BU

    Note: The CAD Basis of 3.49 looks positive. But the US Basis of -0.526
    reveals the buyer is paying 52.6 cents BELOW Chicago in real USD terms.
    The positive CAD basis is the weak Canadian dollar flattering the number.
    """
    if not timestamp:
        timestamp = datetime.now(timezone.utc).isoformat()

    cad_basis = cash_price_cad - futures_price_usd
    us_cash = cash_price_cad / exchange_rate
    us_basis = us_cash - futures_price_usd

    return {
        "cad_basis": round(cad_basis, 4),
        "us_basis_at_ingestion": round(us_basis, 4),
        "was_back_calculated": True,
        "source_cash_price": cash_price_cad,
        "back_calc_futures": futures_price_usd,
        "back_calc_fx_rate": exchange_rate,
        "back_calc_timestamp": timestamp,
    }


def calculate_full_pricing(
    basis_cad_bu: float,
    futures_price_usd: float,
    exchange_rate: float,
    commodity: str,
    aggression: float = 0.0,
) -> dict:
    """
    Calculate all pricing components for a single bid.

    basis_cad_bu: stored CAD basis (durable — from database)
    futures_price_usd: LIVE futures price from CQG
    exchange_rate: LIVE USD/CAD rate
    aggression: Mapleview's margin adjustment (CAD/BU)

    Returns cash prices, both basis values, and Mapleview's price.
    """
    # All cash prices are LIVE (basis is stored, futures+FX are live)
    cash_price_cad = futures_price_usd + basis_cad_bu
    mapleview_price = cash_price_cad + aggression

    # US Basis: convert live cash to USD, subtract live futures
    cash_price_usd = cash_price_cad / exchange_rate
    us_basis = cash_price_usd - futures_price_usd

    bu_per_mt = BUSHELS_PER_TONNE.get(commodity, 36.7437)

    return {
        # Farmer-facing prices (Mapleview's prices, after margin)
        "mapleview_price_cad_bu": round(mapleview_price, 4),
        "mapleview_price_cad_mt": round(mapleview_price * bu_per_mt, 2),

        # Buyer's raw cash price (internal — never shown to farmers)
        "cash_price_cad_bu": round(cash_price_cad, 4),
        "cash_price_cad_mt": round(cash_price_cad * bu_per_mt, 2),

        # Basis values
        "cad_basis": basis_cad_bu,
        "us_basis": round(us_basis, 4),
        "us_basis_signal": interpret_us_basis(us_basis, commodity)["signal"],
        "mapleview_basis": round(basis_cad_bu + aggression, 4),

        # Calculation components (for dashboard display / audit)
        "components": {
            "futures_usd": futures_price_usd,
            "exchange_rate": exchange_rate,
            "aggression": aggression,
        },
    }


def interpret_us_basis(us_basis: float, commodity: str) -> dict:
    """
    Contextualise a US basis value. Thresholds are calibrated per commodity.
    Adjust these as you accumulate historical data.
    """
    thresholds = {
        "soybeans":      {"strong": 0.50, "normal_low": -0.50, "weak": -1.00},
        "corn":          {"strong": 0.20, "normal_low": -0.20, "weak": -0.50},
        "srw_wheat":     {"strong": 0.30, "normal_low": -0.30, "weak": -0.60},
        "hrw_wheat":     {"strong": 0.30, "normal_low": -0.30, "weak": -0.60},
        "canola":        {"strong": 20.0, "normal_low": -20.0, "weak": -40.0},  # CAD/MT
    }

    t = thresholds.get(commodity, thresholds["corn"])

    if us_basis >= t["strong"]:
        signal = "STRONG"
        interpretation = "Buyer is paying above US market. High local demand or urgent need."
    elif us_basis >= t["normal_low"]:
        signal = "NORMAL"
        interpretation = "Basis is within typical range."
    elif us_basis >= t["weak"]:
        signal = "WEAK"
        interpretation = "Buyer is paying below US market. Low urgency or oversupplied."
    else:
        signal = "VERY_WEAK"
        interpretation = "Significantly below US market. May reflect tariff impact or major oversupply."

    return {"us_basis": us_basis, "signal": signal, "interpretation": interpretation}


def calculate_tariff_adjusted_us_basis(
    us_basis: float,
    futures_price_usd: float,
    tariff_rate: float = 0.25,
) -> dict:
    """
    Calculate the tariff-adjusted US basis for export scenarios.

    With a 25% tariff on Canadian grain entering the US:
        Export-adjusted US Basis = US Basis - (Futures × Tariff Rate)

    Example:
        US Basis: +0.09 USD/BU
        Futures: 11.375 USD/BU
        Tariff: 25%
        Tariff cost: 11.375 × 0.25 = 2.844 USD/BU
        Export-adjusted: 0.09 - 2.844 = -2.754 USD/BU  (deeply uneconomic)
    """
    tariff_cost = futures_price_usd * tariff_rate
    adjusted = us_basis - tariff_cost
    return {
        "us_basis": us_basis,
        "tariff_rate": tariff_rate,
        "tariff_cost_usd_bu": round(tariff_cost, 4),
        "export_adjusted_us_basis": round(adjusted, 4),
        "export_viable": adjusted > -0.50,
    }
