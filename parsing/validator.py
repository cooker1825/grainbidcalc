"""
Validates parsed and normalized bid data. Flags anomalies for human review.
"""

from typing import Any

# Sanity bounds by commodity (CAD/BU)
PRICE_BOUNDS: dict[str, tuple[float, float]] = {
    "soybeans":      (8.0,  25.0),
    "corn":          (4.0,  12.0),
    "srw_wheat":     (4.0,  15.0),
    "hrw_wheat":     (4.0,  15.0),
    "swr_wheat":     (4.0,  15.0),
    "canola":        (400,  900),   # CAD/MT when not converted
    "wheat_general": (4.0,  15.0),
}


def validate_bids(bids: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Validate each bid. Adds a 'validation_issues' list to any bid with problems.
    Returns all bids (caller decides whether to store or flag for review).
    """
    validated = []
    for bid in bids:
        issues = []

        # Required fields
        for field in ("buyer_name", "commodity", "delivery_month", "source_type"):
            if not bid.get(field):
                issues.append(f"missing_field:{field}")

        # Must have either basis or cash price
        if bid.get("basis_value") is None and bid.get("cash_price") is None:
            issues.append("no_price_data")

        # Confidence check
        confidence = bid.get("confidence", 1.0)
        if confidence < 0.7:
            issues.append(f"low_confidence:{confidence:.2f}")

        # Price bounds check
        commodity = bid.get("commodity", "")
        basis = bid.get("basis_normalized_cad_bu") or bid.get("basis_value")
        bounds = PRICE_BOUNDS.get(commodity)
        if basis is not None and bounds:
            lo, hi = bounds
            # Basis can be negative — check the implied cash would be in range
            # (simple sanity check, not exact)
            if abs(basis) > (hi - lo):
                issues.append(f"basis_out_of_range:{basis}")

        bid["validation_issues"] = issues
        bid["needs_review"] = len(issues) > 0
        validated.append(bid)

    return validated
