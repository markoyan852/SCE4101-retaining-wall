"""Design criteria: turn computed values into pass/fail verdicts.

The four standard checks for a cantilever retaining wall are

===============  ==========================================  =====================
Check            Value compared                              Limit
===============  ==========================================  =====================
Sliding          FOS = R / H                                 >= 1.0 (ULS factored)
Overturning      FOS = MR / MO                               >= 1.0 (ULS factored)
Middle third     |e|                                         <= B / 6
Bearing          q_ult / p_max                               >= 1.0 (ULS factored)
===============  ==========================================  =====================

In the global-factor approach all three factor-of-safety demands are raised to
3.0 by the UI; the comparison code is the same.
"""
from __future__ import annotations

from dataclasses import dataclass

from .geometry import WallGeometry
from .stability import StabilityResult


@dataclass
class Criterion:
    """One design criterion and its verdict.

    Attributes
    ----------
    key : str
        Machine-readable name (``"sliding"``, ``"overturning"``, ...).
    label : str
        Description for the results table.
    value : float
        Computed value.
    limit : float
        Required limit; for the middle-third check this is ``B/6``.
    passed : bool
        ``value >= limit`` for the FOS-type checks, ``value <= limit`` for the
        eccentricity check (the ``lower_is_better`` flag records which).
    unit : str
        Display unit.
    lower_is_better : bool
        ``True`` for the eccentricity check.
    """

    key: str
    label: str
    value: float
    limit: float
    passed: bool
    unit: str = ""
    lower_is_better: bool = False

    def as_row(self) -> dict:
        """Return the criterion as a flat dict (for a Streamlit dataframe)."""
        return {
            "Check": self.label,
            "Value": round(self.value, 4),
            "Limit": round(self.limit, 4),
            "Unit": self.unit,
            "Result": "PASS" if self.passed else "FAIL",
        }


def evaluate(res: StabilityResult, geo: WallGeometry,
             fos_sliding_min: float = 1.0,
             fos_overturning_min: float = 1.0,
             bearing_fos_min: float = 1.0) -> list[Criterion]:
    """Evaluate all four criteria and return them in reporting order.

    Parameters
    ----------
    res : StabilityResult
        Output of :func:`core.stability.run_analysis`.
    geo : WallGeometry
        Wall geometry (for ``B/6``).
    fos_sliding_min, fos_overturning_min, bearing_fos_min : float
        Required factors of safety.  ``1.0`` for the factored ULS approach,
        ``3.0`` for the global-factor approach.
    """
    bearing_ratio = res.q_ult / res.p_max if res.p_max > 0 else float("inf")
    b_over_6 = geo.B / 6.0
    return [
        Criterion("sliding", "FOS against sliding", res.fos_sliding,
                  fos_sliding_min, res.fos_sliding >= fos_sliding_min),
        Criterion("overturning", "FOS against overturning", res.fos_overturning,
                  fos_overturning_min, res.fos_overturning >= fos_overturning_min),
        Criterion("middle_third", "Eccentricity e", abs(res.eccentricity),
                  b_over_6, abs(res.eccentricity) <= b_over_6, "m",
                  lower_is_better=True),
        Criterion("bearing", "Bearing capacity qᵤₗₜ / pₘₐₓ", bearing_ratio,
                  bearing_fos_min, bearing_ratio >= bearing_fos_min),
    ]


def check_results(res: StabilityResult, geo: WallGeometry,
                  fos_sliding_min: float = 1.0,
                  fos_overturning_min: float = 1.0,
                  bearing_fos_min: float = 1.0) -> dict[str, bool]:
    """Return pass/fail booleans keyed by criterion name."""
    return {c.key: c.passed for c in evaluate(res, geo, fos_sliding_min,
                                              fos_overturning_min,
                                              bearing_fos_min)}


def all_pass(criteria: list[Criterion]) -> bool:
    """``True`` when every criterion passes."""
    return all(c.passed for c in criteria)


def failed(criteria: list[Criterion]) -> list[Criterion]:
    """The criteria that fail (empty list = design is acceptable)."""
    return [c for c in criteria if not c.passed]
