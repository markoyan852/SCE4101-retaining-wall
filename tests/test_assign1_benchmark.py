"""Benchmark against the tutorial workbook.

Reference: ``Reference/Geo Assignment 1 calculation.xlsx`` (sheets ``Parameter``,
``Calculation L=7`` and ``Q2``).  The workbook is the team's hand calculation for
the same wall, so it is the natural benchmark for the app.

Two kinds of comparison are made here:

1. **Exact** -- coefficients and self-weights are closed-form values that the
   workbook reports to many digits, and the app must reproduce them.  These are
   hard assertions with a tight tolerance.
2. **Method agreement** -- the workbook's pressure blocks contain internal
   inconsistencies (it uses 5.5 m for part of a 6 m band, mixes two different
   force columns, and leaves out the key band for the earth pressure).  The app
   integrates the same theory exactly, so the results agree to a few per cent
   but not to the last digit.  The reasons are written up in
   ``docs/validation_notes.md``; the tolerances below are the documented bands.

If a value outside a band is produced, either the app regressed or the
validation notes are out of date -- both are worth investigating before the
report is written.
"""
from __future__ import annotations

import pytest

from core import Soil, WallGeometry, check_results, run_analysis

# --- workbook anchors (sheet "Calculation L=7" unless stated) ---------------
EXCEL = {
    "ka": 0.368121510287691,        # Parameter D60 / Calculation M4
    "kp": 2.7164943423667065,       # Parameter F60 / Calculation M22
    "nq": 18.96, "nc": 30.78, "ngamma": 23.30,   # Calculation C109-C111
    "sum_w": 744.0,                 # Calculation H53
    "sum_w_moment": 3373.5,         # Calculation W53
    "sum_active": 397.9003661603447,   # Calculation J36 (earth + water)
    "sum_passive": 40.18579749447082,  # Calculation J43 (earth + water)
    "fos_sliding": 1.2653447462480252,  # Calculation D64
    "m_overturn": 932.7792804786011,    # Calculation D68
    "m_resist": 3393.5928987472353,     # Calculation D70
    "fos_overturning": 3.6381521006834667,  # Calculation D75
    "eccentricity": 0.19245481415506172,    # Calculation C84
    "p_max": 123.81874062016726,            # Calculation K88
    "p_min": 88.75268795126132,             # Calculation K91
    "q_ult": 153.12760520881199,            # Calculation K142
    "water_active": 176.58,                 # Calculation J35
    # Earth-only totals implied by the two force columns of the sheet:
    "earth_u_column": 203.725,   # SC + A1 + U(A2) + U(A3)
    "earth_j_column": 221.320,   # SC + A1 + J(A2) + J(A3) -> feeds J36
}


@pytest.fixture
def tutorial(fill, cdg):
    """The tutorial wall analysed with the app defaults (partial factors)."""
    geo = WallGeometry(H_ret=8.0, t_base=0.5, B=7.0, toe=3.0, t_stem=0.5,
                       key_depth=0.5, key_width=0.5, Df=1.5)
    res = run_analysis(geo, fill, cdg, 10.0, 3.0, 24.0, partial_factor=1.2)
    return geo, res


class TestExactAgreement:
    def test_earth_pressure_coefficients(self, tutorial):
        _, res = tutorial
        assert res.blocks["Ka"] == pytest.approx(EXCEL["ka"], abs=1e-12)
        assert res.blocks["Kp"] == pytest.approx(EXCEL["kp"], abs=1e-12)

    def test_bearing_factors(self, tutorial):
        _, res = tutorial
        detail = res.bearing_detail
        assert detail["Nq"] == pytest.approx(EXCEL["nq"], abs=5e-3)
        assert detail["Nc"] == pytest.approx(EXCEL["nc"], abs=5e-3)
        assert detail["Ngamma"] == pytest.approx(EXCEL["ngamma"], abs=5e-3)

    def test_total_weight(self, tutorial):
        _, res = tutorial
        assert res.sum_W == pytest.approx(EXCEL["sum_w"], abs=1e-9)

    def test_weight_moment_about_toe(self, tutorial):
        _, res = tutorial
        moment = sum(f * x for _, f, x in res.blocks["weights"])
        assert moment == pytest.approx(EXCEL["sum_w_moment"], abs=1e-9)

    def test_water_pressure_force(self, tutorial):
        _, res = tutorial
        water = sum(f for _, f, _ in res.blocks["water_active"])
        assert water == pytest.approx(EXCEL["water_active"], abs=1e-6)


class TestMethodAgreement:
    def test_active_earth_force_lies_between_the_sheets_two_columns(self, tutorial):
        """The workbook's J and U columns disagree by 8.6%; the app is between them."""
        _, res = tutorial
        earth = sum(f for _, f, _ in res.blocks["active"])
        assert EXCEL["earth_u_column"] < earth < EXCEL["earth_j_column"]

    def test_sliding_fos_within_two_percent(self, tutorial):
        _, res = tutorial
        assert res.fos_sliding == pytest.approx(EXCEL["fos_sliding"], rel=0.02)

    def test_overturning_fos_within_five_percent(self, tutorial):
        _, res = tutorial
        assert res.fos_overturning == pytest.approx(EXCEL["fos_overturning"], rel=0.05)

    def test_overturning_moment_within_five_percent(self, tutorial):
        _, res = tutorial
        assert res.M_overturn == pytest.approx(EXCEL["m_overturn"], rel=0.05)

    def test_resisting_moment_within_one_percent(self, tutorial):
        _, res = tutorial
        assert res.M_resist == pytest.approx(EXCEL["m_resist"], rel=0.01)

    def test_eccentricity_same_order(self, tutorial):
        _, res = tutorial
        assert res.eccentricity == pytest.approx(EXCEL["eccentricity"], abs=0.06)
        assert res.eccentricity < 7.0 / 6.0

    def test_max_bearing_pressure_within_five_percent(self, tutorial):
        _, res = tutorial
        assert res.p_max == pytest.approx(EXCEL["p_max"], rel=0.05)
        assert res.p_min == pytest.approx(EXCEL["p_min"], rel=0.06)

    def test_bearing_capacity_same_order(self, fill, cdg):
        """Workbook omits c'Nc and uses sq=1, so the app is deliberately higher."""
        geo = WallGeometry(H_ret=8.0, t_base=0.5, B=7.0, toe=3.0, t_stem=0.5,
                           key_depth=0.5, key_width=0.5, Df=1.5)
        res = run_analysis(geo, fill, cdg, 10.0, 3.0, 24.0,
                           partial_factor=1.2,
                           include_cohesion_in_bearing=False)
        assert res.q_ult == pytest.approx(EXCEL["q_ult"], rel=0.12)
        assert res.q_ult > res.p_max

    def test_both_approaches_conclude_the_wall_is_adequate(self, tutorial):
        geo, res = tutorial
        checks = check_results(res, geo)
        assert all(checks.values())
        assert res.fos_sliding > 1.0
        assert res.fos_overturning > 1.0
        assert res.p_max < res.q_ult


class TestParameterSheetDiscrepancies:
    """The workbook header does not match its own calculation; the app follows the calc."""

    def test_app_uses_eight_metre_retained_height(self):
        """Header says "Retaining Height 7 m" but the pressure blocks use 8 m."""
        assert WallGeometry().H_ret == pytest.approx(8.0)

    def test_app_uses_seven_metre_base(self):
        """Parameter sheet lists L = 7.3 m; every block uses B = 7.0 m."""
        assert WallGeometry().B == pytest.approx(7.0)

    def test_app_uses_the_fill_on_both_sides(self, tutorial):
        geo, res = tutorial
        assert res.blocks["Kp"] > 1.0
        assert geo.heel == pytest.approx(3.5)


class TestTwoLayerSensitivity:
    """Sanity check that swapping fill properties moves the results in the right direction."""

    def test_weaker_backfill_increases_driving_force(self, assignment1_geometry, cdg):
        strong = Soil("Strong", 18.0, 2.0, 38.0)
        weak = Soil("Weak", 18.0, 2.0, 28.0)
        a = run_analysis(assignment1_geometry, strong, cdg, 10.0, 3.0)
        b = run_analysis(assignment1_geometry, weak, cdg, 10.0, 3.0)
        assert b.F_sliding > a.F_sliding
        assert b.fos_sliding < a.fos_sliding
