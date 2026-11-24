"""Backwards-compatibility shim for the original monolithic ``core.calc``.

The calculation core was split into focused modules on 2026-11-11 (see
``core/__init__.py`` for the module map).  This module re-exports the old names
so that existing imports keep working.

.. deprecated::
    Import from :mod:`core` instead, e.g. ``from core import Soil,
    WallGeometry, run_analysis``.
"""
from __future__ import annotations

from .bearing import bearing_capacity
from .checks import check_results
from .constants import GAMMA_CONCRETE, GAMMA_W, PARTIAL_FACTOR
from .earth_pressure import (active_earth_nodes, blocks_from_nodes,
                             passive_earth_nodes)
from .forces import Block
from .geometry import WallGeometry
from .hydro import water_nodes
from .soil import Soil, rankine_ka, rankine_kp
from .stability import StabilityResult, run_analysis

# Name used by older code for the self-weight blocks of the wall.
weight_blocks = WallGeometry.weight_blocks

__all__ = [
    "GAMMA_CONCRETE", "GAMMA_W", "PARTIAL_FACTOR",
    "Block", "Soil", "WallGeometry", "StabilityResult",
    "rankine_ka", "rankine_kp",
    "active_earth_nodes", "passive_earth_nodes", "water_nodes",
    "blocks_from_nodes", "weight_blocks",
    "bearing_capacity", "run_analysis", "check_results",
]
