"""End-to-end smoke tests of the Streamlit page using ``streamlit.testing.AppTest``.

These run ``app.py`` in a headless script runner: the page is built exactly as it
would be in the browser, so a runtime error (renamed key, bad widget argument,
missing figure) fails the test instead of being hidden behind the HTML shell.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parents[1] / "app.py")
TIMEOUT = 90


def by_label(widgets, label: str):
    """Return the widget whose visible label matches ``label``."""
    for widget in widgets:
        if widget.label == label:
            return widget
    raise AssertionError(f"widget not found: {label}")


def fresh_app() -> AppTest:
    """Build and run the app once with the default inputs."""
    at = AppTest.from_file(APP, default_timeout=TIMEOUT)
    at.run()
    assert not at.exception, f"app raised: {at.exception[0].value}"
    return at


class TestDefaultPage:
    def test_page_runs(self):
        at = fresh_app()
        assert [m.label for m in at.metric] == [
            "Sliding FOS", "Overturning FOS", "Max bearing pressure", "Eccentricity e"]

    def test_tutorial_wall_passes(self):
        at = fresh_app()
        assert len(at.success) == 1
        assert "PASS" in at.success[0].value
        assert at.error == []

    def test_metric_values(self):
        at = fresh_app()
        values = {m.label: m.value for m in at.metric}
        assert values["Sliding FOS"] == "1.29"
        assert values["Overturning FOS"] == "3.78"
        assert values["Max bearing pressure"] == "119.1 kPa"
        assert values["Eccentricity e"] == "0.140 m"

    def test_check_summary_table(self):
        at = fresh_app()
        assert len(at.dataframe) >= 1
        summary = at.dataframe[0].value
        assert list(summary["Result"]) == ["PASS", "PASS", "PASS", "PASS"]
        assert summary.shape == (4, 5)

    def test_detailed_table_is_present(self):
        at = fresh_app()
        tables = [df.value for df in at.dataframe]
        assert tables[-1].shape[0] == 13  # active 4 + water 1 + passive 2 + water 1 + weights 5

    def test_figures_are_drawn(self):
        at = fresh_app()
        assert len(at.get("image")) == 2  # wall section + pressure diagram

    def test_passive_force_is_reported(self):
        at = fresh_app()
        texts = [b.value for b in at.markdown]
        assert any("P_p" in t for t in texts)


class TestFactoredParameterTable:
    def test_parameter_table_lists_unfactored_and_factored_values(self):
        import math
        at = fresh_app()
        # dataframes: [0] check summary, [1] parameters, [2] detailed blocks
        param = at.dataframe[1].value
        cols = list(param.columns)
        assert "c′ (kPa)" in cols and "c′_d (kPa)" in cols
        assert "φ′ (°)" in cols and "φ′_d (°)" in cols
        row = param[param["Soil"] == "Backfill (active)"].iloc[0]
        assert row["c′ (kPa)"] == 2.0
        assert row["c′_d (kPa)"] == pytest.approx(2.0 / 1.2, abs=0.01)
        expected = math.degrees(math.atan(math.tan(math.radians(32.0)) / 1.2))
        assert row["φ′_d (°)"] == pytest.approx(expected, abs=0.01)


class TestGeometryInputBox:
    def test_typing_base_width_syncs_slider_and_results(self):
        at = fresh_app()
        box = by_label(at.number_input, "Base width B (m)")
        box.set_value(11.0)
        at.run()
        assert not at.exception
        slider = by_label(at.slider, "Base width B (m)")
        assert slider.value == 11.0
        values = {m.label: m.value for m in at.metric}
        assert float(values["Overturning FOS"]) > 3.78


class TestDesignApproachSwitch:
    def test_global_factor_mode_runs(self):
        at = fresh_app()
        at.radio[0].set_value("Global factor").run()
        assert not at.exception
        assert at.error == []

    def test_global_factor_mode_fails_the_tutorial_wall(self):
        at = fresh_app()
        at.radio[0].set_value("Global factor").run()
        assert "FAILS" in at.success[0].value
        values = {m.label: m.value for m in at.metric}
        assert values["Sliding FOS"] == "1.72"

    def test_partial_factor_inputs_appear_only_in_partial_mode(self):
        partial = fresh_app()
        partial_sliders = len(partial.slider)
        partial.radio[0].set_value("Global factor").run()
        assert len(partial.slider) == partial_sliders - 3  # three FOS demands removed
        assert not partial.exception


class TestBearingCohesionToggle:
    @staticmethod
    def _bearing_text(at: AppTest) -> str:
        for block in at.markdown:
            if "q_{ult}" in block.value:
                return block.value
        raise AssertionError("bearing detail markdown not found")

    def test_unticking_cohesion_term_reduces_q_ult(self):
        at = fresh_app()
        before = self._bearing_text(at)
        by_label(at.checkbox, "Include c′·Nc term in bearing capacity").set_value(False).run()
        assert not at.exception
        after = self._bearing_text(at)
        assert before != after
        assert "q_{ult}" in after


class TestInvalidInputHandling:
    def test_toe_equal_to_base_shows_error_instead_of_crashing(self):
        at = fresh_app()
        by_label(at.slider, "Base width B (m)").set_value(3.0)
        at.run()
        assert not at.exception
        toe = by_label(at.slider, "Toe length (m)")
        toe.set_value(3.0)
        at.run()
        assert not at.exception
        assert len(at.error) == 1
        assert "Heel width" in at.error[0].value

    def test_extreme_friction_angle_is_accepted(self):
        at = fresh_app()
        by_label(at.number_input, "Backfill φ′ (°)").set_value(45.0)
        at.run()
        assert not at.exception
        assert at.error == []

    def test_wide_base_changes_results(self):
        at = fresh_app()
        by_label(at.slider, "Base width B (m)").set_value(11.0)
        at.run()
        assert not at.exception
        values = {m.label: m.value for m in at.metric}
        assert float(values["Overturning FOS"]) > 3.78


@pytest.mark.parametrize("height", [4.0, 8.0, 12.0])
def test_heights_run_cleanly(height):
    at = AppTest.from_file(APP, default_timeout=TIMEOUT)
    at.run()
    by_label(at.slider, "Retained height H (m)").set_value(height)
    at.run()
    assert not at.exception
