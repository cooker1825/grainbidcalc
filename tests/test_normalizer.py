"""Tests for the bid normalizer."""

import pytest
from parsing.normalizer import (
    normalize_futures_contract,
    parse_fractional_futures,
    normalize_basis_to_cad_bu,
    normalize_delivery_month,
)


class TestFuturesNormalization:
    def test_great_lakes_format(self):
        assert normalize_futures_contract("@C6H", "corn") == "ZCH26"
        assert normalize_futures_contract("@S6H", "soybeans") == "ZSH26"
        assert normalize_futures_contract("@W6N", "srw_wheat") == "ZWN26"

    def test_g3_short_format(self):
        assert normalize_futures_contract("H26", "soybeans") == "ZSH26"
        assert normalize_futures_contract("K26", "soybeans") == "ZSK26"

    def test_already_standard(self):
        assert normalize_futures_contract("ZSH26", "soybeans") == "ZSH26"
        assert normalize_futures_contract("ZCK26", "corn") == "ZCK26"


class TestFractionalFutures:
    def test_cbot_fractional(self):
        assert parse_fractional_futures("426'2s") == pytest.approx(4.2625, abs=0.0001)
        assert parse_fractional_futures("1134'0") == pytest.approx(11.3400, abs=0.0001)
        assert parse_fractional_futures("1137'4") == pytest.approx(11.375, abs=0.0001)

    def test_decimal_passthrough(self):
        assert parse_fractional_futures("11.375") == pytest.approx(11.375)


class TestUnitConversion:
    def test_cad_bu_passthrough(self):
        assert normalize_basis_to_cad_bu(4.33, "CAD/BU", "soybeans", 1.369) == 4.33

    def test_cad_mt_to_cad_bu(self):
        # 4.33 CAD/BU * 36.7437 bu/MT = 159.10 CAD/MT
        # So 159.10 CAD/MT / 36.7437 ≈ 4.33 CAD/BU
        result = normalize_basis_to_cad_bu(159.10, "CAD/MT", "soybeans", 1.369)
        assert abs(result - 4.33) < 0.02


class TestDeliveryMonthNormalization:
    def test_standard_format(self):
        assert normalize_delivery_month("Feb'26", "soybeans") == "2026-02"
        assert normalize_delivery_month("Oct'26", "soybeans") == "2026-10"

    def test_harvest_label(self):
        assert normalize_delivery_month("Harvest", "soybeans") == "2026-10"
        assert normalize_delivery_month("Harvest", "corn") == "2026-11"
