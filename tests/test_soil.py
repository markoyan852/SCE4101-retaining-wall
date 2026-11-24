"""Tests for soil parameters and Rankine coefficients."""
from __future__ import annotations

import math

import pytest

from core import GAMMA_W, Soil, rankine_ka, rankine_kp


class TestFactoring:
    def test_fill_matches_workbook(self, fill):
        """phi' = 32 deg, c' = 2 kPa, factor 1.2 -> 27.5071 deg, 1.6667 kPa."""
        phi_d, c_d = fill.factored(1.2)
        assert phi_d == pytest.approx(27.507095501, abs=1e-9)
        assert c_d == pytest.approx(1.666666667, abs=1e-9)

    def test_cdg_matches_workbook(self, cdg):
        """phi' = 35 deg, c' = 5 kPa, factor 1.2 -> 30.2638 deg, 4.1667 kPa."""
        phi_d, c_d = cdg.factored(1.2)
        assert phi_d == pytest.approx(30.263830014, abs=1e-9)
        assert c_d == pytest.approx(4.166666667, abs=1e-9)

    def test_factor_applies_to_tangent_not_angle(self, fill):
        """GEOGUIDE factors tan(phi'), so phi_d != phi'/1.2."""
        phi_d, _ = fill.factored(1.2)
        assert phi_d != pytest.approx(fill.phi_prime / 1.2)
        assert math.tan(math.radians(phi_d)) == pytest.approx(
            math.tan(math.radians(fill.phi_prime)) / 1.2)

    def test_unit_factor_returns_characteristic_values(self, fill):
        phi_d, c_d = fill.factored(1.0)
        assert phi_d == pytest.approx(fill.phi_prime)
        assert c_d == pytest.approx(fill.c_prime)

    def test_zero_factor_rejected(self, fill):
        with pytest.raises(ValueError):
            fill.factored(0.0)


class TestCoefficients:
    def test_ka_matches_workbook(self):
        assert rankine_ka(32.0) == pytest.approx(0.307258524522, abs=1e-12)

    def test_kp_matches_workbook(self):
        assert rankine_kp(32.0) == pytest.approx(3.254588303300, abs=1e-12)

    def test_ka_times_kp_is_one(self):
        for phi in (0.0, 20.0, 32.0, 45.0):
            assert rankine_ka(phi) * rankine_kp(phi) == pytest.approx(1.0)

    def test_factored_coefficients_match_workbook(self):
        """Ka and Kp at the factored angle 27.5071 deg (workbook sheet Parameter)."""
        phi_d = 27.507095501035042
        assert rankine_ka(phi_d) == pytest.approx(0.368121510288, abs=1e-12)
        assert rankine_kp(phi_d) == pytest.approx(2.716494342367, abs=1e-12)

    def test_phi_zero_gives_unit_coefficients(self):
        assert rankine_ka(0.0) == pytest.approx(1.0)
        assert rankine_kp(0.0) == pytest.approx(1.0)

    def test_kp_infinite_at_ninety_degrees(self):
        with pytest.raises(ValueError):
            rankine_kp(90.0)


class TestSubmergedWeight:
    def test_gamma_sub(self, fill):
        assert fill.gamma_sub == pytest.approx(fill.gamma - GAMMA_W)

    def test_gamma_sub_positive_for_realistic_soil(self, fill):
        assert fill.gamma_sub > 0


class TestValidation:
    def test_valid_soil_has_no_problems(self, fill, cdg):
        assert fill.validate() == []
        assert cdg.validate() == []

    @pytest.mark.parametrize("phi", [-5.0, 50.0])
    def test_phi_out_of_range_reported(self, phi):
        problems = Soil("X", 18.0, 2.0, phi).validate()
        assert any("phi'" in p for p in problems)

    def test_negative_cohesion_reported(self):
        problems = Soil("X", 18.0, -1.0, 30.0).validate()
        assert any("c'" in p for p in problems)

    def test_gamma_below_water_reported(self):
        problems = Soil("X", 9.0, 0.0, 30.0).validate()
        assert any("gamma" in p for p in problems)
