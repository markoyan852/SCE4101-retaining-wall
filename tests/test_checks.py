"""Tests for the design criteria (pass/fail) layer."""
from __future__ import annotations

import pytest

from core import (WallGeometry, all_pass, check_results, evaluate, failed,
                  run_analysis)


class TestEvaluate:
    def test_returns_four_criteria_in_order(self, assignment1_geometry, fill, cdg):
        res = run_analysis(assignment1_geometry, fill, cdg, 10.0, 3.0)
        criteria = evaluate(res, assignment1_geometry)
        assert [c.key for c in criteria] == [
            "sliding", "overturning", "middle_third", "bearing"]

    def test_tutorial_case_passes_every_check(self, assignment1_geometry, fill, cdg):
        res = run_analysis(assignment1_geometry, fill, cdg, 10.0, 3.0)
        assert all_pass(evaluate(res, assignment1_geometry))
        assert all(check_results(res, assignment1_geometry).values())
        assert failed(evaluate(res, assignment1_geometry)) == []

    def test_middle_third_limit_is_b_over_six(self, assignment1_geometry, fill, cdg):
        res = run_analysis(assignment1_geometry, fill, cdg, 10.0, 3.0)
        middle = [c for c in evaluate(res, assignment1_geometry)
                  if c.key == "middle_third"][0]
        assert middle.limit == pytest.approx(assignment1_geometry.B / 6.0)
        assert middle.lower_is_better is True

    def test_global_factor_mode_fails_the_tutorial_wall(self, assignment1_geometry,
                                                       fill, cdg):
        """FOS 1.72 < 3.0: a wall designed to ULS limits cannot meet global FOS 3."""
        res = run_analysis(assignment1_geometry, fill, cdg, 10.0, 3.0,
                           partial_factor=1.0)
        checks = check_results(res, assignment1_geometry, 3.0, 3.0, 3.0)
        assert checks["sliding"] is False
        assert checks["overturning"] is True

    def test_limits_are_inclusive(self, assignment1_geometry, fill, cdg):
        res = run_analysis(assignment1_geometry, fill, cdg, 10.0, 3.0)
        at_limit = check_results(res, assignment1_geometry,
                                 res.fos_sliding, res.fos_overturning, 1.0)
        assert at_limit["sliding"] is True
        assert at_limit["overturning"] is True

    def test_narrow_base_fails_middle_third_and_bearing(self, fill, cdg):
        geo = WallGeometry(B=3.2, toe=1.0)
        res = run_analysis(geo, fill, cdg, 10.0, 3.0)
        checks = check_results(res, geo)
        assert checks["middle_third"] is False
        assert checks["bearing"] is False

    def test_row_format(self, assignment1_geometry, fill, cdg):
        res = run_analysis(assignment1_geometry, fill, cdg, 10.0, 3.0)
        row = evaluate(res, assignment1_geometry)[0].as_row()
        assert set(row) == {"Check", "Value", "Limit", "Unit", "Result"}
        assert row["Result"] in {"PASS", "FAIL"}

    def test_bearing_ratio_uses_p_max(self, assignment1_geometry, fill, cdg):
        res = run_analysis(assignment1_geometry, fill, cdg, 10.0, 3.0)
        bearing = [c for c in evaluate(res, assignment1_geometry)
                   if c.key == "bearing"][0]
        assert bearing.value == pytest.approx(res.q_ult / res.p_max)
