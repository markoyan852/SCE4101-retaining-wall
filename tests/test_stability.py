"""Tests for the wall geometry and the full stability analysis."""
from __future__ import annotations

import json
import math

import pytest

from core import (Soil, WallGeometry, base_friction, base_pressures,
                  check_results, eccentricity, run_analysis)


class TestGeometry:
    def test_derived_dimensions(self, assignment1_geometry):
        geo = assignment1_geometry
        assert geo.heel == pytest.approx(3.5)
        assert geo.height_total == pytest.approx(8.5)
        assert geo.y_ground_active == pytest.approx(8.5)
        assert geo.depth_active_profile == pytest.approx(9.0)
        assert geo.depth_passive_ground_below_active == pytest.approx(7.0)
        assert geo.key_x_from_toe == pytest.approx(6.5)

    def test_valid_geometry_has_no_problems(self, assignment1_geometry):
        assert assignment1_geometry.validate() == []

    def test_negative_heel_rejected(self):
        geo = WallGeometry(B=3.4, toe=3.0, t_stem=0.5)
        assert any("Heel" in p for p in geo.validate())

    def test_key_wider_than_heel_rejected(self):
        geo = WallGeometry(B=7.0, toe=3.0, t_stem=0.5, key_width=4.0)
        assert any("key" in p for p in geo.validate())

    def test_embedment_above_slab_top_rejected(self):
        geo = WallGeometry(Df=0.3, t_base=0.5)
        assert any("Df" in p for p in geo.validate())

    def test_negative_key_depth_rejected(self):
        geo = WallGeometry(key_depth=-0.5)
        assert any("key" in p for p in geo.validate())

    def test_invalid_geometry_raises_in_analysis(self, fill, cdg):
        with pytest.raises(ValueError):
            run_analysis(WallGeometry(B=3.4, toe=3.0), fill, cdg, 0.0, 100.0)


class TestWeightBlocks:
    def test_match_workbook(self, assignment1_geometry, fill):
        """C1=96, C2=84, C3=6, S1=504, S2=54 kN/m; total 744 kN/m."""
        blocks = assignment1_geometry.weight_blocks(fill, gamma_concrete=24.0)
        forces = {b.label: b.force for b in blocks}
        assert forces == pytest.approx({
            "C1 stem": 96.0,
            "C2 base": 84.0,
            "C3 key": 6.0,
            "S1 soil on heel": 504.0,
            "S2 soil on toe": 54.0,
        })

    def test_total_weight_matches_workbook(self, assignment1_geometry, fill):
        blocks = assignment1_geometry.weight_blocks(fill)
        assert sum(b.force for b in blocks) == pytest.approx(744.0)

    def test_moment_about_toe_matches_workbook(self, assignment1_geometry, fill):
        """Workbook cell W53: sum of weight moments = 3373.5 kNm."""
        blocks = assignment1_geometry.weight_blocks(fill)
        assert sum(b.force * b.x for b in blocks) == pytest.approx(3373.5)

    def test_stem_is_not_double_counted_with_the_slab(self, assignment1_geometry, fill):
        """Stem volume is measured above the slab top, so V_concrete = 3.5+4.0+0.25 m2."""
        blocks = assignment1_geometry.weight_blocks(fill, gamma_concrete=24.0)
        concrete = sum(b.force for b in blocks if b.label.startswith("C"))
        assert concrete == pytest.approx(24.0 * (0.5 * 8.0 + 7.0 * 0.5 + 0.25))

    def test_no_key_block_when_key_depth_is_zero(self, fill):
        geo = WallGeometry(key_depth=0.0)
        labels = [b.label for b in geo.weight_blocks(fill)]
        assert "C3 key" not in labels

    def test_no_toe_soil_when_embedment_equals_slab(self, fill):
        geo = WallGeometry(Df=0.5, t_base=0.5)
        labels = [b.label for b in geo.weight_blocks(fill)]
        assert "S2 soil on toe" not in labels

    def test_centroids_are_inside_the_base(self, assignment1_geometry, fill):
        geo = assignment1_geometry
        for block in geo.weight_blocks(fill):
            assert 0.0 <= block.x <= geo.B


class TestSlidingAndOverturning:
    def test_friction_and_adhesion(self, cdg):
        phi_d, c_d = cdg.factored(1.2)
        assert base_friction(744.0, phi_d) == pytest.approx(434.13, abs=0.01)
        assert 7.0 * c_d == pytest.approx(29.1667, abs=1e-4)

    def test_tutorial_factors_of_safety(self, assignment1_geometry, fill, cdg):
        res = run_analysis(assignment1_geometry, fill, cdg, 10.0, 3.0)
        assert res.fos_sliding == pytest.approx(1.2855, abs=5e-4)
        assert res.fos_overturning == pytest.approx(3.7837, abs=1e-3)

    def test_vertical_load_matches_workbook(self, assignment1_geometry, fill, cdg):
        res = run_analysis(assignment1_geometry, fill, cdg, 10.0, 3.0)
        assert res.sum_W == pytest.approx(744.0)

    def test_driving_force_is_earth_plus_water(self, assignment1_geometry, fill, cdg):
        res = run_analysis(assignment1_geometry, fill, cdg, 10.0, 3.0)
        earth = sum(f for _, f, _ in res.blocks["active"])
        water = sum(f for _, f, _ in res.blocks["water_active"])
        assert res.F_sliding == pytest.approx(earth + water)
        assert earth == pytest.approx(218.287, abs=1e-3)
        assert water == pytest.approx(176.58, abs=1e-6)

    def test_moment_equilibrium(self, assignment1_geometry, fill, cdg):
        """MR - MO must equal V (B/2 - e) from the eccentricity definition."""
        geo = assignment1_geometry
        res = run_analysis(geo, fill, cdg, 10.0, 3.0)
        assert (res.M_resist - res.M_overturn) == pytest.approx(
            res.sum_W * (geo.B / 2.0 - res.eccentricity))

    def test_no_water_gives_higher_fos(self, assignment1_geometry, fill, cdg):
        wet = run_analysis(assignment1_geometry, fill, cdg, 10.0, 3.0)
        dry = run_analysis(assignment1_geometry, fill, cdg, 10.0, 100.0)
        assert dry.fos_sliding > wet.fos_sliding
        assert dry.F_sliding < wet.F_sliding

    def test_more_surcharge_increases_driving_force(self, assignment1_geometry, fill, cdg):
        low = run_analysis(assignment1_geometry, fill, cdg, 0.0, 3.0)
        high = run_analysis(assignment1_geometry, fill, cdg, 20.0, 3.0)
        assert high.F_sliding > low.F_sliding
        assert high.fos_sliding < low.fos_sliding

    def test_deeper_key_increases_driving_force(self, fill, cdg):
        shallow = WallGeometry(key_depth=0.0)
        deep = WallGeometry(key_depth=1.0)
        a = run_analysis(shallow, fill, cdg, 10.0, 3.0)
        b = run_analysis(deep, fill, cdg, 10.0, 3.0)
        assert b.F_sliding > a.F_sliding


class TestEccentricityAndPressure:
    def test_tutorial_eccentricity(self, assignment1_geometry, fill, cdg):
        res = run_analysis(assignment1_geometry, fill, cdg, 10.0, 3.0)
        assert res.eccentricity == pytest.approx(0.140148, abs=1e-6)
        assert abs(res.eccentricity) < assignment1_geometry.B / 6.0

    def test_eccentricity_formula(self):
        assert eccentricity(7.0, 3300.0, 900.0, 744.0) == pytest.approx(
            7.0 / 2.0 - 2400.0 / 744.0)

    def test_eccentricity_zero_load_rejected(self):
        with pytest.raises(ValueError):
            eccentricity(7.0, 1.0, 1.0, 0.0)

    def test_base_pressures_recover_the_vertical_load(self, assignment1_geometry,
                                                     fill, cdg):
        geo = assignment1_geometry
        res = run_analysis(geo, fill, cdg, 10.0, 3.0)
        assert (res.p_max + res.p_min) / 2.0 * geo.B == pytest.approx(res.sum_W)

    def test_base_pressures_formula(self):
        p_max, p_min = base_pressures(744.0, 7.0, 0.0)
        assert p_max == pytest.approx(744.0 / 7.0)
        assert p_min == pytest.approx(744.0 / 7.0)
        p_max, p_min = base_pressures(744.0, 7.0, 0.5)
        assert p_max > p_min

    def test_narrow_base_gives_negative_p_min_without_crashing(self, fill, cdg):
        geo = WallGeometry(B=3.2, toe=1.0)
        res = run_analysis(geo, fill, cdg, 10.0, 3.0)
        assert res.p_min < 0
        checks = check_results(res, geo)
        assert checks["middle_third"] is False


class TestDesignApproaches:
    def test_global_factors_reproduce_characteristic_ka(self, assignment1_geometry,
                                                       fill, cdg):
        res = run_analysis(assignment1_geometry, fill, cdg, 10.0, 3.0,
                           partial_factor=1.0)
        assert res.blocks["Ka"] == pytest.approx(0.307258524522, abs=1e-12)
        assert res.blocks["Kp"] == pytest.approx(3.254588303300, abs=1e-12)

    def test_partial_factors_reduce_ka_and_increase_driving_force(
            self, assignment1_geometry, fill, cdg):
        factored = run_analysis(assignment1_geometry, fill, cdg, 10.0, 3.0,
                                partial_factor=1.2)
        char = run_analysis(assignment1_geometry, fill, cdg, 10.0, 3.0,
                            partial_factor=1.0)
        assert factored.blocks["Ka"] > char.blocks["Ka"]
        assert factored.F_sliding > char.F_sliding

    def test_global_mode_fos_differs(self, assignment1_geometry, fill, cdg):
        res = run_analysis(assignment1_geometry, fill, cdg, 10.0, 3.0,
                           partial_factor=1.0)
        assert res.fos_sliding == pytest.approx(1.7175, abs=1e-3)


class TestResultExport:
    def test_result_is_json_serialisable(self, assignment1_geometry, fill, cdg):
        res = run_analysis(assignment1_geometry, fill, cdg, 10.0, 3.0)
        payload = json.dumps(res.to_dict())
        assert '"fos_sliding"' in payload
        assert len(json.loads(payload)["blocks"]["weights"]) == 5

    def test_infinite_fos_when_no_driving_force(self):
        """Zero driving force returns infinity instead of raising ZeroDivisionError."""
        from core.stability import factor_of_safety
        assert math.isinf(factor_of_safety(10.0, 0.0))
        assert factor_of_safety(10.0, 5.0) == pytest.approx(2.0)
