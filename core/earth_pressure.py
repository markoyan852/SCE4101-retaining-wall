"""Rankine lateral earth pressure profiles and their block decomposition.

The lateral pressure at depth ``z`` on the active side is

    p_a(z) = sigma'_v(z) * Ka - 2 c'_d sqrt(Ka)

and on the passive side

    p_p(z) = sigma'_v(z) * Kp + 2 c'_d sqrt(Kp)

where ``sigma'_v`` is the *effective* vertical stress (surcharge, then bulk unit
weight above the water table, then submerged unit weight below it) and the
subscript ``d`` denotes design (partially factored) parameters.

Profiles are returned as a list of ``(z, p)`` nodes, piecewise linear between
nodes.  :func:`blocks_from_nodes` turns a profile into rectangles and triangles
whose force and centroid are exact for that linear profile, so the sum of the
blocks equals the integral of the pressure diagram.
"""
from __future__ import annotations

import math

from .constants import PARTIAL_FACTOR
from .forces import Block
from .soil import Soil, cohesion_term, rankine_ka, rankine_kp


def _lateral_active(sigma_v: float, ka: float, coh: float) -> float:
    """Active lateral pressure for one effective vertical stress (kPa)."""
    return sigma_v * ka - coh


def active_earth_nodes(soil: Soil, q_surcharge: float, z_water: float,
                       z_total: float,
                       factor: float = PARTIAL_FACTOR) -> tuple[list[tuple[float, float]], float]:
    """Active earth pressure profile, ground surface down to ``z_total``.

    The vertical effective stress starts at the surcharge, increases with the
    bulk unit weight above the water table and with the submerged unit weight
    below it.  The water table depth ``z_water`` is measured from the active
    ground surface; a water table below ``z_total`` (or no water) simply leaves
    the whole profile above the water table.

    Parameters
    ----------
    soil : Soil
        Backfill soil, characteristic parameters.
    q_surcharge : float
        Uniform surcharge on the active ground (kPa).
    z_water : float
        Water table depth below the active ground surface (m).
    z_total : float
        Depth of the bottom of the profile below the active ground (m).
    factor : float
        Partial material factor; ``1.0`` gives characteristic values.

    Returns
    -------
    (nodes, Ka)
        ``nodes`` is ``[(z, p), ...]`` with ``z`` in m and ``p`` in kPa
        (theoretical value -- it may be negative near the surface when the
        cohesion term dominates; see :func:`clip_negative_pressure`).
    """
    phi_d, _ = soil.factored(factor)
    ka = rankine_ka(phi_d)
    coh = cohesion_term(soil, ka, factor)

    sigma_v = q_surcharge
    nodes: list[tuple[float, float]] = [(0.0, _lateral_active(sigma_v, ka, coh))]

    if z_water < z_total:
        sigma_v += soil.gamma * z_water
        nodes.append((z_water, _lateral_active(sigma_v, ka, coh)))
        g_below = soil.gamma_sub
        sigma_v += g_below * (z_total - z_water)
        nodes.append((z_total, _lateral_active(sigma_v, ka, coh)))
    else:
        sigma_v += soil.gamma * z_total
        nodes.append((z_total, _lateral_active(sigma_v, ka, coh)))

    return nodes, ka


def passive_earth_nodes(soil: Soil, z_total: float, submerged: bool = True,
                        factor: float = PARTIAL_FACTOR) -> tuple[list[tuple[float, float]], float]:
    """Passive earth pressure profile, passive ground surface to ``z_total``.

    ``submerged`` selects the unit weight used over the whole passive wedge:
    ``True`` uses ``gamma - gamma_w``, ``False`` uses ``gamma``.  The tutorial
    workbook and the default app case have the water table above the passive
    ground surface, so the whole wedge is submerged.

    Returns
    -------
    (nodes, Kp)
        ``nodes`` is ``[(0, 2c'_d sqrt(Kp)), (z_total, p_bottom)]``.
    """
    phi_d, _ = soil.factored(factor)
    kp = rankine_kp(phi_d)
    coh = cohesion_term(soil, kp, factor)
    g = soil.gamma_sub if submerged else soil.gamma
    p_bottom = g * z_total * kp + coh
    return [(0.0, coh), (z_total, p_bottom)], kp


def clip_negative_pressure(nodes: list[tuple[float, float]]
                           ) -> tuple[list[tuple[float, float]], float]:
    """Remove the tensile part of a lateral pressure profile.

    Soil cannot sustain tension, so negative lateral pressure is set to zero
    and the zero-crossing is inserted as an extra node.  This is the standard
    "tension crack" treatment: the cohesive zone near the surface is ignored.

    Parameters
    ----------
    nodes : list[(z, p)]
        Profile nodes, top to bottom.

    Returns
    -------
    (clipped_nodes, crack_depth)
        ``crack_depth`` is the depth at which the profile first reaches zero
        from a tensile (negative) value, or 0.0 if there is no tension.
    """
    if not nodes:
        return [], 0.0
    clipped: list[tuple[float, float]] = [(nodes[0][0], max(nodes[0][1], 0.0))]
    crack_depth = 0.0
    for (z1, p1), (z2, p2) in zip(nodes, nodes[1:]):
        if (p1 < 0.0) != (p2 < 0.0) and p2 != p1:
            z0 = z1 + (0.0 - p1) * (z2 - z1) / (p2 - p1)
            clipped.append((z0, 0.0))
            if crack_depth == 0.0:
                crack_depth = z0
        clipped.append((z2, max(p2, 0.0)))
    return clipped, crack_depth


def blocks_from_nodes(nodes: list[tuple[float, float]], prefix: str,
                      clip_tension: bool = True) -> list[Block]:
    """Split a piecewise-linear pressure profile into rectangle and triangle blocks.

    Every segment between consecutive nodes is decomposed into a rectangle of
    the smaller end pressure and a triangle of the pressure increment, so the
    block forces add up exactly to the integral of the profile and the moments
    add up exactly to its first moment.

    Parameters
    ----------
    nodes : list[(z, p)]
        Profile nodes, top to bottom (m, kPa).
    prefix : str
        Label prefix, e.g. ``"A"`` gives ``A1r``, ``A1t``, ``A2r`` ...
    clip_tension : bool
        If ``True`` (default) negative pressures are replaced by zero first
        (:func:`clip_negative_pressure`), which is the physical treatment.

    Returns
    -------
    list[Block]
        Blocks with ``force`` (kN/m) and ``z`` = centroid depth below the
        profile datum (m).
    """
    if clip_tension:
        nodes, _ = clip_negative_pressure(nodes)

    blocks: list[Block] = []
    for i, ((z1, p1), (z2, p2)) in enumerate(zip(nodes, nodes[1:])):
        h = z2 - z1
        if h <= 0:
            continue
        p_min, p_max = min(p1, p2), max(p1, p2)
        if p_min > 0.0:
            blocks.append(Block(f"{prefix}{i + 1}r", p_min * h, z1 + h / 2.0))
        if p_max - p_min > 1e-12:
            # centroid: 2h/3 from the end where the pressure is smaller
            z_tri = z1 + (2.0 * h / 3.0 if p2 > p1 else h / 3.0)
            blocks.append(Block(f"{prefix}{i + 1}t", 0.5 * (p_max - p_min) * h, z_tri))
    return blocks
