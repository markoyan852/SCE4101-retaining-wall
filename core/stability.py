"""Stability analysis: sliding, overturning, eccentricity and base pressure.

This module assembles the pieces (soil -> pressure profiles -> force blocks ->
weights) and produces one :class:`StabilityResult` per metre run of wall.
Sign conventions follow :mod:`core.geometry`.

The checks themselves are performed in :mod:`core.checks`; this module only
computes the numbers.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from .bearing import bearing_capacity
from .constants import GAMMA_CONCRETE, PARTIAL_FACTOR
from .earth_pressure import (active_earth_nodes, blocks_from_nodes,
                             clip_negative_pressure, passive_earth_nodes)
from .forces import Block, total_force, total_moment
from .geometry import WallGeometry
from .hydro import water_nodes
from .soil import Soil


@dataclass
class StabilityResult:
    """All computed results of one stability analysis (per metre run).

    Attributes
    ----------
    fos_sliding, fos_overturning : float
        Factors of safety against sliding and overturning.
    eccentricity : float
        Resultant eccentricity from the centre of the base (m).
    p_max, p_min : float
        Maximum / minimum bearing pressure under the base slab (kPa).
    q_ult : float
        Ultimate bearing capacity of the founding soil (kPa).
    sum_W : float
        Total vertical load on the base, concrete + soil (kN/m).
    F_sliding : float
        Horizontal driving force, active earth + water (kN/m).
    M_overturn, M_resist : float
        Overturning and resisting moments about the toe (kNm/m).
    blocks : dict
        Named lists of ``(label, force, lever arm)`` for the detailed table.
    bearing_detail : dict
        Intermediate bearing capacity factors.
    """

    fos_sliding: float = 0.0
    fos_overturning: float = 0.0
    eccentricity: float = 0.0
    p_max: float = 0.0
    p_min: float = 0.0
    q_ult: float = 0.0
    sum_W: float = 0.0
    F_sliding: float = 0.0
    M_overturn: float = 0.0
    M_resist: float = 0.0
    blocks: dict = field(default_factory=dict)
    bearing_detail: dict = field(default_factory=dict)
    tension_crack_depth: float = 0.0

    def to_dict(self) -> dict:
        """Return the scalar results as a JSON-serialisable dict.

        Lists of blocks are included as plain lists of ``[label, force, lever]``
        so that a run can be archived or re-imported without custom encoders.
        """
        def rows(key: str) -> list[list]:
            return [[label, force, lever] for label, force, lever in self.blocks.get(key, [])]

        return {
            "fos_sliding": self.fos_sliding,
            "fos_overturning": self.fos_overturning,
            "eccentricity": self.eccentricity,
            "p_max": self.p_max,
            "p_min": self.p_min,
            "q_ult": self.q_ult,
            "sum_W": self.sum_W,
            "F_sliding": self.F_sliding,
            "M_overturn": self.M_overturn,
            "M_resist": self.M_resist,
            "tension_crack_depth": self.tension_crack_depth,
            "Ka": self.blocks.get("Ka"),
            "Kp": self.blocks.get("Kp"),
            "blocks": {
                "active": rows("active"),
                "water_active": rows("water_active"),
                "passive": rows("passive"),
                "water_passive": rows("water_passive"),
                "weights": rows("weights"),
            },
            "bearing_detail": dict(self.bearing_detail),
        }


# --------------------------------------------------------------------------
# Individual checks (pure functions, unit-tested directly)
# --------------------------------------------------------------------------
def base_friction(vertical_load: float, phi_d: float) -> float:
    """Sliding resistance from friction on the base, ``V tan(phi'_d)`` (kN/m)."""
    return vertical_load * math.tan(math.radians(phi_d))


def base_adhesion(c_d: float, base_width: float) -> float:
    """Sliding resistance from adhesion on the base, ``B c'_d`` (kN/m)."""
    return base_width * c_d


def factor_of_safety(resisting: float, driving: float) -> float:
    """Ratio ``resisting / driving``; infinite when there is nothing driving."""
    if driving <= 0.0:
        return math.inf
    return resisting / driving


def eccentricity(base_width: float, sum_m_resist: float, sum_m_overturn: float,
                 sum_w: float) -> float:
    """Resultant eccentricity from the base centre, ``B/2 - (MR - MO)/V`` (m).

    Positive values move the resultant towards the toe.  A negative value means
    the resultant is on the heel side of the centre.
    """
    if sum_w <= 0.0:
        raise ValueError("vertical load must be positive")
    return base_width / 2.0 - (sum_m_resist - sum_m_overturn) / sum_w


def base_pressures(vertical_load: float, base_width: float,
                   e: float) -> tuple[float, float]:
    """Bearing pressures under a rigid base, ``p = V/B (1 +/- 6e/B)`` (kPa).

    Returns ``(p_max, p_min)``.  ``p_min < 0`` indicates that the resultant
    falls outside the middle third and the base is partly in tension, which the
    middle-third check rejects.
    """
    mean = vertical_load / base_width
    spread = 1.0 + 6.0 * e / base_width
    return mean * spread, mean * (2.0 - spread)


# --------------------------------------------------------------------------
# Full analysis
# --------------------------------------------------------------------------
def run_analysis(geo: WallGeometry, backfill: Soil, bearing_soil: Soil,
                 q_surcharge: float, z_water: float,
                 gamma_concrete: float = GAMMA_CONCRETE,
                 partial_factor: float = PARTIAL_FACTOR,
                 include_cohesion_in_bearing: bool = True) -> StabilityResult:
    """Run the complete stability analysis of the wall.

    Parameters
    ----------
    geo : WallGeometry
        Wall dimensions.
    backfill : Soil
        Retained soil; also used for the passive side and for the soil resting
        on the base (the tutorial case uses the same fill on both sides).
    bearing_soil : Soil
        Soil beneath the base slab (shear strength for sliding and bearing).
    q_surcharge : float
        Uniform surcharge on the active ground (kPa).
    z_water : float
        Water table depth below the active ground surface (m).
    gamma_concrete : float
        Unit weight of concrete (kN/m3).
    partial_factor : float
        Partial material factor applied to ``c'`` and ``tan(phi')``.  Pass
        ``1.0`` for the global-factor (characteristic value) approach.
    include_cohesion_in_bearing : bool
        Include the ``c' Nc`` term in the bearing capacity (see
        :func:`core.bearing.ultimate_bearing_capacity`).

    Returns
    -------
    StabilityResult
    """
    geo_ok = geo.validate()
    if geo_ok:
        raise ValueError("invalid geometry: " + " ".join(geo_ok))
    for soil in (backfill, bearing_soil):
        problems = soil.validate()
        if problems:
            raise ValueError("invalid soil: " + " ".join(problems))

    res = StabilityResult()

    # --- active side: earth pressure over the full height to the key tip ----
    active_nodes, ka = active_earth_nodes(backfill, q_surcharge, z_water,
                                          geo.depth_active_profile, partial_factor)
    active_blocks = blocks_from_nodes(active_nodes, "A")
    active_water = blocks_from_nodes(
        water_nodes(z_water, geo.depth_active_profile), "Wa")
    crack_nodes, res.tension_crack_depth = clip_negative_pressure(active_nodes)

    # lever arms measured upwards from the underside of the base slab
    h_active = [geo.y_ground_active - b.z for b in active_blocks]
    h_active_water = [geo.y_ground_active - b.z for b in active_water]

    # --- passive side: from the excavation surface to the slab underside -----
    z_passive = geo.depth_passive_profile
    # The tutorial convention is that the passive side is drained to its own
    # ground surface, so water pressure there starts at the excavation level
    # (not at the active-side water table).  The wedge is taken as fully
    # submerged whenever the water table is above the base slab.
    submerged = z_water < geo.depth_passive_ground_below_active + z_passive
    passive_nodes, kp = passive_earth_nodes(backfill, z_passive, submerged,
                                            partial_factor)
    passive_blocks = blocks_from_nodes(passive_nodes, "P")
    # profile datum is the passive ground surface, so depths run 0 -> Df and
    # the lever arms below are measured from that same surface
    passive_water = blocks_from_nodes(water_nodes(0.0, z_passive), "Wp")
    h_passive = [geo.y_ground_passive - b.z for b in passive_blocks]
    h_passive_water = [geo.y_ground_passive - b.z for b in passive_water]

    # --- self-weight --------------------------------------------------------
    weight_blks = geo.weight_blocks(backfill, gamma_concrete)

    # --- sliding ------------------------------------------------------------
    driving_blocks = active_blocks + active_water
    passive_all = passive_blocks + passive_water
    res.F_sliding = total_force(driving_blocks)
    passive_force = total_force(passive_all)
    res.sum_W = total_force(weight_blks)
    phi_b, c_b = bearing_soil.factored(partial_factor)
    friction = base_friction(res.sum_W, phi_b)
    adhesion = base_adhesion(c_b, geo.B)
    res.fos_sliding = factor_of_safety(passive_force + friction + adhesion,
                                       res.F_sliding)

    # --- overturning about the toe, at slab underside level -----------------
    res.M_overturn = _moment(driving_blocks, h_active + h_active_water)
    res.M_resist = (_moment(passive_all, h_passive + h_passive_water)
                    + total_moment(weight_blks, "x"))
    res.fos_overturning = factor_of_safety(res.M_resist, res.M_overturn)

    # --- eccentricity, middle third, base pressure --------------------------
    res.eccentricity = eccentricity(geo.B, res.M_resist, res.M_overturn, res.sum_W)
    res.p_max, res.p_min = base_pressures(res.sum_W, geo.B, res.eccentricity)

    # --- ultimate bearing capacity ------------------------------------------
    l_prime = max(geo.B - 2.0 * abs(res.eccentricity), 0.1)
    founding_below_wt = (geo.y_ground_active - z_water) > 0.0
    gamma_term = bearing_soil.gamma_sub if founding_below_wt else bearing_soil.gamma
    res.q_ult, res.bearing_detail = bearing_capacity(
        bearing_soil, backfill.gamma, gamma_term, 1.0, l_prime, geo.Df,
        res.F_sliding, res.sum_W, partial_factor, include_cohesion_in_bearing)

    # --- reporting rows -----------------------------------------------------
    res.blocks = {
        "active": [(b.label, b.force, h) for b, h in zip(active_blocks, h_active)],
        "water_active": [(b.label, b.force, h) for b, h in zip(active_water, h_active_water)],
        "passive": [(b.label, b.force, h) for b, h in zip(passive_blocks, h_passive)],
        "water_passive": [(b.label, b.force, h) for b, h in zip(passive_water, h_passive_water)],
        "weights": [(b.label, b.force, b.x) for b in weight_blks],
        "Ka": ka, "Kp": kp,
        "base_friction": friction, "base_adhesion": adhesion,
        "F_passive": passive_force,
        "active_nodes": list(crack_nodes),
    }
    return res


def _moment(blocks: list[Block], lever_arms: list[float]) -> float:
    """Sum ``force x lever arm`` for parallel lists of blocks and arm lengths."""
    return sum(b.force * h for b, h in zip(blocks, lever_arms))
