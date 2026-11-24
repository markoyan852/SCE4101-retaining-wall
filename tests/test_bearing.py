"""Tests for the bearing capacity module."""
from __future__ import annotations

import math

import pytest

from core import bearing_capacity
from core.bearing import (bearing_factors, inclination_factors, shape_factors,
                          ultimate_bearing_capacity)


class TestBearingFactors:
    def test_match_workbook(self, cdg):
        """Factored CDG angle 30.2638 deg -> Nq 18.96, Nc 30.78, Ngamma 23.30."""
        phi_d, _ = cdg.factored(1.2)
        nq, nc, ngamma = bearing_factors(phi_d)
        assert nq == pytest.approx(18.96, abs=5e-3)
        assert nc == pytest.approx(30.78, abs=5e-3)
        assert ngamma == pytest.approx(23.30, abs=5e-3)

    @pytest.mark.parametrize("phi", [10.0, 25.0, 30.263830014, 35.0, 45.0])
    def test_identities_hold(self, phi):
        nq, nc, ngamma = bearing_factors(phi)
        tan_phi = math.tan(math.radians(phi))
        assert nc == pytest.approx((nq - 1.0) / tan_phi)
        assert ngamma == pytest.approx(2.0 * (nq + 1.0) * tan_phi)

    def test_increase_with_friction_angle(self):
        values = [bearing_factors(phi) for phi in (20.0, 30.0, 40.0)]
        for earlier, later in zip(values, values[1:]):
            assert later[0] > earlier[0]
            assert later[1] > earlier[1]
            assert later[2] > earlier[2]

    def test_phi_zero_returns_undrained_limits(self):
        nq, nc, ngamma = bearing_factors(0.0)
        assert nq == pytest.approx(1.0)
        assert nc == pytest.approx(5.14)
        assert ngamma == pytest.approx(0.0)


class TestShapeFactors:
    def test_match_workbook(self, cdg):
        phi_d, _ = cdg.factored(1.2)
        nq, nc, _ = bearing_factors(phi_d)
        sc, sq, sg = shape_factors(phi_d, nq, nc, 1.0, 6.615090371689877)
        assert sc == pytest.approx(1.093118, abs=1e-5)
        assert sq == pytest.approx(1.088208, abs=1e-5)
        assert sg == pytest.approx(0.939532, abs=1e-5)

    def test_strip_footing_tends_to_unity(self, cdg):
        phi_d, _ = cdg.factored(1.2)
        nq, nc, _ = bearing_factors(phi_d)
        sc, sq, sg = shape_factors(phi_d, nq, nc, 1.0, 1e9)
        assert sc == pytest.approx(1.0, abs=1e-6)
        assert sq == pytest.approx(1.0, abs=1e-6)
        assert sg == pytest.approx(1.0, abs=1e-6)


class TestInclinationFactors:
    def test_matches_workbook_m(self, cdg):
        """m = (2 + B'/L') / (1 + B'/L') = 1.86868 (workbook I102)."""
        phi_d, c_d = cdg.factored(1.2)
        nq, nc, _ = bearing_factors(phi_d)
        inc = inclination_factors(394.867, 744.0, c_d, phi_d, 1.0,
                                  6.615090371689877, nq, nc)
        assert inc["m"] == pytest.approx(1.8686817948060557, abs=1e-9)
        assert 0.0 < inc["Ki"] < 1.0
        assert inc["ig"] < inc["iq"]
        assert inc["ic"] < inc["iq"]

    def test_no_horizontal_load_gives_unit_factors(self, cdg):
        phi_d, c_d = cdg.factored(1.2)
        nq, nc, _ = bearing_factors(phi_d)
        inc = inclination_factors(0.0, 744.0, c_d, phi_d, 1.0, 6.0, nq, nc)
        assert inc["Ki"] == 0.0
        assert inc["iq"] == pytest.approx(1.0)
        assert inc["ig"] == pytest.approx(1.0)

    def test_horizontal_load_capped_at_one(self, cdg):
        phi_d, c_d = cdg.factored(1.2)
        nq, nc, _ = bearing_factors(phi_d)
        inc = inclination_factors(1e6, 744.0, c_d, phi_d, 1.0, 6.0, nq, nc)
        assert inc["Ki"] == pytest.approx(1.0)
        assert inc["iq"] == pytest.approx(0.0)


class TestUltimateCapacity:
    def test_is_sum_of_three_terms(self, cdg):
        phi_d, c_d = cdg.factored(1.2)
        q_ult, d = ultimate_bearing_capacity(phi_d, c_d, 18.0, 9.19, 1.0,
                                             6.615090371689877, 1.5, 394.867, 744.0)
        terms = (d["c_term"]
                 + d["q_surcharge"] * d["Nq"] * d["sq"] * d["iq"]
                 + 0.5 * 9.19 * 1.0 * d["Ngamma"] * d["sg"] * d["ig"])
        assert q_ult == pytest.approx(terms)
        assert q_ult > 0

    def test_omitting_cohesion_removes_exactly_the_c_term(self, cdg):
        phi_d, c_d = cdg.factored(1.2)
        args = (phi_d, c_d, 18.0, 9.19, 1.0, 6.615090371689877, 1.5,
                394.867, 744.0)
        q_with, detail = ultimate_bearing_capacity(*args, include_cohesion=True)
        q_without, _ = ultimate_bearing_capacity(*args, include_cohesion=False)
        assert q_with - q_without == pytest.approx(detail["c_term"])
        assert q_with > q_without

    def test_deeper_foundation_increases_capacity(self, cdg):
        phi_d, c_d = cdg.factored(1.2)
        shallow, _ = ultimate_bearing_capacity(phi_d, c_d, 18.0, 9.19, 1.0, 6.0,
                                               1.0, 300.0, 700.0)
        deep, _ = ultimate_bearing_capacity(phi_d, c_d, 18.0, 9.19, 1.0, 6.0,
                                            2.0, 300.0, 700.0)
        assert deep > shallow

    def test_lower_unit_weight_reduces_capacity(self, cdg):
        phi_d, c_d = cdg.factored(1.2)
        heavy, _ = ultimate_bearing_capacity(phi_d, c_d, 18.0, 18.0, 1.0, 6.0,
                                             1.5, 300.0, 700.0)
        light, _ = ultimate_bearing_capacity(phi_d, c_d, 18.0, 8.19, 1.0, 6.0,
                                             1.5, 300.0, 700.0)
        assert heavy > light

    def test_zero_friction_soil_does_not_crash(self):
        q_ult, d = ultimate_bearing_capacity(0.0, 50.0, 18.0, 18.0, 1.0, 6.0,
                                             1.5, 10.0, 400.0)
        assert q_ult > 0
        assert d["Nq"] == pytest.approx(1.0)

    def test_soil_wrapper_uses_the_partial_factor(self, cdg):
        q_ult, d = bearing_capacity(
            cdg, 18.0, 9.19, 1.0, 6.615090371689877, 1.5, 394.867, 744.0,
            factor=1.2)
        assert q_ult > 0
        assert d["Nq"] == pytest.approx(18.96, abs=5e-3)
