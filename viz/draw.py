"""
Matplotlib visualisations for the retaining wall app.

Provides:
* draw_wall        - annotated cross-section (wall, soil, water, surcharge)
* draw_pressure    - lateral earth + water pressure diagram
"""
from __future__ import annotations

import math

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrow, Polygon, Rectangle

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from core import (GAMMA_W, WallGeometry, active_earth_nodes,
                  clip_negative_pressure, passive_earth_nodes, water_nodes)

EARTH = "#b98a5a"     # dry soil
EARTH_WET = "#7fa8c9" # submerged soil
CONCRETE = "#c8c8c8"
WATER = "#2f6db3"


def draw_wall(geo: WallGeometry, q_surcharge: float, z_water: float,
              show_dims: bool = True):
    """Draw an annotated wall cross-section.

    The toe is on the left, the retained soil on the right.  The water
    table, surcharge arrows and (optionally) dimension lines are drawn.

    Returns a matplotlib Figure.
    """
    fig, ax = plt.subplots(figsize=(8.6, 6.2))
    y_top = geo.y_ground_active
    y_bot = -geo.key_depth - 0.4
    x_right = geo.B + geo.H_ret * 0.55 + 0.6
    x_left = -0.6

    # --- soil masses -------------------------------------------------------
    # retained (active) soil above the heel, from slab top to ground
    ax.add_patch(Polygon([(geo.toe + geo.t_stem, geo.t_base), (geo.B, geo.t_base),
                          (geo.B, y_top), (geo.toe + geo.t_stem, y_top)],
                         closed=True, facecolor=EARTH, alpha=0.75, hatch="//",
                         edgecolor="#8a6a45", linewidth=0.8))
    # submerged tint below the water table (water table measured from
    # the active ground surface)
    y_wt = y_top - z_water
    if y_wt > geo.t_base:
        ax.add_patch(Polygon([(geo.toe + geo.t_stem, geo.t_base), (geo.B, geo.t_base),
                              (geo.B, y_wt), (geo.toe + geo.t_stem, y_wt)],
                             closed=True, facecolor=EARTH_WET, alpha=0.45,
                             edgecolor="none"))
        ax.plot([geo.toe + geo.t_stem, geo.B + 0.55], [y_wt, y_wt],
                ls="--", color=WATER, lw=1.6)
        ax.plot(geo.B + 0.62, y_wt, marker="v", color=WATER, ms=7)
        ax.text(geo.B + 0.72, y_wt, "WT", color=WATER, fontsize=9,
                va="center")
    # passive-side soil over the toe (up to the excavation level)
    if geo.Df > geo.t_base:
        ax.add_patch(Polygon([(0, geo.t_base), (geo.toe, geo.t_base),
                              (geo.toe, geo.Df), (0, geo.Df)],
                             closed=True, facecolor=EARTH, alpha=0.55,
                             hatch="//", edgecolor="#8a6a45", linewidth=0.8))
    # soil in front of the toe above the excavation level (hatched lightly,
    # resisting mass indicator)
    ax.add_patch(Polygon([(x_left, geo.Df), (0, geo.Df), (0, y_bot + 0.05),
                          (x_left, y_bot + 0.05)],
                         closed=True, facecolor=EARTH, alpha=0.28, hatch="..",
                         edgecolor="#8a6a45", linewidth=0.6))
    # soil behind the heel beyond the wall (visual continuation)
    ax.add_patch(Polygon([(geo.B, y_top), (x_right, y_top),
                          (x_right, y_bot + 0.05), (geo.B, y_bot + 0.05)],
                         closed=True, facecolor=EARTH, alpha=0.28, hatch="..",
                         edgecolor="#8a6a45", linewidth=0.6))

    # --- concrete ----------------------------------------------------------
    # stem
    ax.add_patch(Rectangle((geo.toe, 0), geo.t_stem, y_top,
                           facecolor=CONCRETE, edgecolor="#555", lw=1.2))
    # base slab
    ax.add_patch(Rectangle((0, 0), geo.B, geo.t_base,
                           facecolor=CONCRETE, edgecolor="#555", lw=1.2))
    # shear key under the heel edge
    if geo.key_depth > 0:
        ax.add_patch(Rectangle((geo.B - geo.key_width, -geo.key_depth),
                               geo.key_width, geo.key_depth,
                               facecolor=CONCRETE, edgecolor="#555", lw=1.2))

    # --- surcharge arrows ---------------------------------------------------
    n_arrows = 5
    for i in range(n_arrows):
        x = geo.toe + geo.t_stem + (geo.heel + 0.2) * (i + 0.5) / n_arrows
        ax.add_patch(FancyArrow(x, y_top + 0.55, 0, -0.42, width=0.02,
                                head_width=0.12, head_length=0.14,
                                color="#c0392b", alpha=0.85))
    ax.text(geo.toe + geo.t_stem + geo.heel / 2, y_top + 0.72,
            f"Surcharge = {q_surcharge:g} kPa", ha="center",
            color="#c0392b", fontsize=9)

    # --- active thrust arrow -------------------------------------------------
    ax.add_patch(FancyArrow(geo.B + geo.H_ret * 0.45, y_top - geo.H_ret * 0.45,
                            -(geo.H_ret * 0.32), 0, width=0.035,
                            head_width=0.22, head_length=0.22,
                            color="#c0392b"))
    ax.text(geo.B + geo.H_ret * 0.34, y_top - geo.H_ret * 0.45 + 0.18,
            "Active thrust", color="#c0392b", fontsize=9)

    # --- labels ---------------------------------------------------------------
    ax.text(geo.toe + geo.t_stem / 2, y_top / 2 + geo.t_base / 2, "Stem",
            rotation=90, ha="center", va="center", fontsize=10)
    ax.text(geo.toe / 2, geo.t_base / 2, "Toe", ha="center", va="center",
            fontsize=10)
    ax.text(geo.toe + geo.t_stem + geo.heel / 2, geo.t_base / 2, "Heel",
            ha="center", va="center", fontsize=10)
    if geo.key_depth > 0:
        ax.annotate("Shear key", xy=(geo.B - geo.key_width / 2, -geo.key_depth),
                    xytext=(geo.B - geo.key_width - 0.9, -geo.key_depth - 0.55),
                    fontsize=9, arrowprops=dict(arrowstyle="->", lw=0.9))

    # --- dimensions -----------------------------------------------------------
    if show_dims:
        dim_kw = dict(color="#333", fontsize=9)
        # overall height on the left
        ax.annotate("", xy=(-0.28, y_top), xytext=(-0.28, 0),
                    arrowprops=dict(arrowstyle="<->", lw=1))
        ax.text(-0.36, y_top / 2, f"H = {geo.H_ret + geo.t_base:g} m",
                rotation=90, ha="right", va="center", **dim_kw)
        # base width below
        ax.annotate("", xy=(0, -0.25), xytext=(geo.B, -0.25),
                    arrowprops=dict(arrowstyle="<->", lw=1))
        ax.text(geo.B / 2, -0.33, f"B = {geo.B:g} m", ha="center",
                va="top", **dim_kw)

    ax.set_xlim(x_left, x_right)
    ax.set_ylim(y_bot, y_top + 1.0)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title("Cantilever Retaining Wall — Cross Section")
    fig.tight_layout()
    return fig


def draw_pressure(geo: WallGeometry, backfill, q_surcharge: float,
                  z_water: float, factor: float = 1.2):
    """Draw the combined lateral pressure diagram, both sides of the wall.

    Passive pressures (pushing the wall from the excavation side) are
    plotted to the left of the wall line, active pressures (driving the
    wall from the retained side) to the right.  Earth and water are
    drawn separately with their own fills, so the passive resistance is
    visible alongside the active demand.

    Depth is measured below the active ground surface; the passive
    (excavation) surface sits at ``geo.depth_passive_ground_below_active``.

    Returns a matplotlib Figure.
    """
    z_active = geo.depth_active_profile
    z_passive = geo.depth_passive_profile
    z_p0 = geo.depth_passive_ground_below_active
    submerged = z_water < z_p0 + z_passive

    # active side (driving, plotted right of the wall)
    active_nodes, ka = active_earth_nodes(backfill, q_surcharge, z_water,
                                          z_active, factor)
    active_nodes, _ = clip_negative_pressure(active_nodes)
    active_water = water_nodes(z_water, z_active)

    # passive side (resisting, plotted left of the wall); its profile datum
    # is the excavation surface, shifted here to the shared depth axis
    passive_nodes, kp = passive_earth_nodes(backfill, z_passive, submerged,
                                            factor)
    passive_nodes = [(z_p0 + z, p) for z, p in passive_nodes]
    passive_water = [(z_p0 + z, p) for z, p in water_nodes(0.0, z_passive)]

    fig, ax = plt.subplots(figsize=(7.6, 6.2))

    # --- passive side (negative x) ------------------------------------------
    pz = [z for z, _ in passive_nodes]
    pp = [-p for _, p in passive_nodes]
    ax.plot(pp, pz, color="#1f7a33", lw=1.8,
            label=f"Passive earth ($K_p$ = {kp:.3f})")
    ax.fill(pp + [0], pz + [0], color="#1f7a33", alpha=0.15)
    if passive_water:
        wpz = [z for z, _ in passive_water]
        wpp = [-p for _, p in passive_water]
        ax.plot(wpp, wpz, color=WATER, lw=1.8, ls="--",
                label="Passive water")
        ax.fill(wpp + [0], wpz + [0], color=WATER, alpha=0.15)

    # --- active side (positive x) -------------------------------------------
    az = [z for z, _ in active_nodes]
    ap = [p for _, p in active_nodes]
    ax.plot(ap, az, color="#c0392b", lw=1.8,
            label=f"Active earth ($K_a$ = {ka:.3f})")
    ax.fill(ap + [0], az + [0], color="#c0392b", alpha=0.18)
    if active_water:
        awz = [z for z, _ in active_water]
        awp = [p for _, p in active_water]
        ax.plot(awp, awz, color=WATER, lw=1.8, ls="--",
                label="Active water")
        ax.fill(awp + [0], awz + [0], color=WATER, alpha=0.18)

    # reference lines: wall face, water table, excavation surface
    ax.axvline(0, color="#555", lw=1.4)
    if z_water < z_active:
        ax.axhline(z_water, color=WATER, lw=0.8, ls=":")
    ax.axhline(z_p0, color="#8a6a45", lw=0.8, ls=":")
    ax.text(0.995, z_p0, " excavation", transform=ax.get_yaxis_transform(),
            ha="right", va="bottom", fontsize=8, color="#8a6a45")

    ax.invert_yaxis()
    ax.set_xlabel("Lateral pressure (kPa)  —  passive (−) / active (+)")
    ax.set_ylabel("Depth below active ground (m)")
    ax.set_title("Combined Lateral Pressure Diagram")
    ax.legend(loc="lower right", fontsize=8)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    return fig
