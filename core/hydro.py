"""Hydrostatic water pressure.

Water pressure is treated separately from effective earth pressure: the earth
pressure profiles use effective vertical stress ``sigma'_v``, and the water
pressure ``u = gamma_w * h`` is added on top of them.
"""
from __future__ import annotations

from .constants import GAMMA_W


def hydrostatic_pressure(head: float) -> float:
    """Water pressure at a depth ``head`` below the water table (kPa)."""
    return GAMMA_W * head


def water_nodes(z_water: float, z_total: float) -> list[tuple[float, float]]:
    """Water pressure profile from the water table to the bottom of the profile.

    Parameters
    ----------
    z_water : float
        Depth of the water table below the profile datum (m).
    z_total : float
        Depth of the bottom of the profile below the same datum (m).

    Returns
    -------
    list[(z, u)]
        ``[(z_water, 0), (z_total, gamma_w (z_total - z_water))]``, or an empty
        list when the water table is at/below the bottom of the profile.
    """
    if z_water >= z_total:
        return []
    return [(z_water, 0.0), (z_total, hydrostatic_pressure(z_total - z_water))]
