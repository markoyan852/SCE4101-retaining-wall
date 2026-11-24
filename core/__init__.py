"""Calculation core of the retaining-wall web app.

Public API (import from here rather than from the individual modules):

    from core import Soil, WallGeometry, run_analysis, evaluate

Module map
----------
``constants``       physical constants and default factors
``forces``          ``Block`` (one force + its lever arm) and summation helpers
``soil``            ``Soil``, Rankine ``Ka``/``Kp``, partial factoring
``geometry``        ``WallGeometry``, self-weight blocks
``earth_pressure``  active/passive pressure profiles, block decomposition
``hydro``           hydrostatic water pressure
``bearing``         bearing capacity factors and ``q_ult``
``stability``       ``run_analysis`` and its result container
``checks``          pass/fail criteria
"""
from __future__ import annotations

from .bearing import (bearing_capacity, bearing_factors,
                      ultimate_bearing_capacity)
from .checks import Criterion, all_pass, check_results, evaluate, failed
from .constants import GAMMA_CONCRETE, GAMMA_W, PARTIAL_FACTOR
from .earth_pressure import (active_earth_nodes, blocks_from_nodes,
                             clip_negative_pressure, passive_earth_nodes)
from .forces import Block
from .geometry import WallGeometry
from .hydro import hydrostatic_pressure, water_nodes
from .soil import Soil, rankine_ka, rankine_kp
from .stability import (StabilityResult, base_friction, base_pressures,
                        eccentricity, run_analysis)

__all__ = [
    "GAMMA_CONCRETE", "GAMMA_W", "PARTIAL_FACTOR",
    "Block", "Soil", "WallGeometry", "StabilityResult", "Criterion",
    "rankine_ka", "rankine_kp",
    "active_earth_nodes", "passive_earth_nodes", "blocks_from_nodes",
    "clip_negative_pressure",
    "water_nodes", "hydrostatic_pressure",
    "bearing_factors", "bearing_capacity", "ultimate_bearing_capacity",
    "run_analysis", "base_friction", "base_pressures", "eccentricity",
    "evaluate", "check_results", "all_pass", "failed",
]
