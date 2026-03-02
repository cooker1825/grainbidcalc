"""Tests for pricing calculations. All math verified against known examples from architecture doc."""

import pytest
from calculation.price_calculator import (
    calculate_us_basis,
    back_calculate_basis_from_cash,
    calculate_full_pricing,
    calculate_tariff_adjusted_us_basis,
)


class TestUSBasis:
    def test_adm_windsor_example(self):
        """ADM Windsor: stored CAD Basis=4.33, Futures=11.375, FX=1.369 → US Basis≈+0.097"""
        us_basis = calculate_us_basis(
            cad_basis=4.33,
            futures_price_usd_bu=11.375,
            exchange_rate=1.369,
        )
        assert abs(us_basis - 0.097) < 0.005

    def test_strong_basis_signal(self):
        us_basis = calculate_us_basis(4.33, 11.375, 1.369)
        from calculation.price_calculator import interpret_us_basis
        result = interpret_us_basis(us_basis, "soybeans")
        assert result["signal"] in ("STRONG", "NORMAL")


class TestBackCalculation:
    def test_sarnia_example(self):
        """Sarnia email: Cash=14.90, Futures=11.41, FX=1.369 → CAD Basis=3.49, US Basis≈-0.526"""
        result = back_calculate_basis_from_cash(
            cash_price_cad=14.90,
            futures_price_usd=11.41,
            exchange_rate=1.369,
            timestamp="2026-02-20T14:30:00Z",
        )
        assert abs(result["cad_basis"] - 3.49) < 0.005
        assert abs(result["us_basis_at_ingestion"] - (-0.526)) < 0.01
        assert result["was_back_calculated"] is True
        assert result["source_cash_price"] == 14.90

    def test_positive_cad_but_negative_us(self):
        """Demonstrates CAD basis can look positive while US basis is negative (weak dollar illusion)."""
        result = back_calculate_basis_from_cash(14.90, 11.41, 1.369)
        assert result["cad_basis"] > 0
        assert result["us_basis_at_ingestion"] < 0


class TestTariffImpact:
    def test_25_percent_tariff(self):
        """25% tariff on $11.375 futures should make export deeply uneconomic."""
        result = calculate_tariff_adjusted_us_basis(
            us_basis=0.097,
            futures_price_usd=11.375,
            tariff_rate=0.25,
        )
        assert result["tariff_cost_usd_bu"] == pytest.approx(2.844, abs=0.01)
        assert result["export_adjusted_us_basis"] < -2.0
        assert result["export_viable"] is False
