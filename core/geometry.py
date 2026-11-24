"""Wall geometry and self-weight blocks.

Coordinate system (cross-section, per metre run of wall):

* ``x = 0`` at the toe (front edge of the base slab), increasing towards the
  heel (retained side).
* ``y = 0`` at the underside of the base slab, increasing upwards.
* The stem sits between ``x = toe`` and ``x = toe + t_stem``.
* The shear key hangs below the heel edge, at the back of the base slab.

The class is a plain data container; the :meth:`WallGeometry.validate` method
reports combinations that are geometrically impossible so that the UI can
refuse them instead of crashing.
"""
from __future__ import annotations

from dataclasses import dataclass

from .constants import GAMMA_CONCRETE
from .forces import Block
from .soil import Soil


@dataclass
class WallGeometry:
    """Dimensions of a cantilever L-shaped wall (per metre run).

    Parameters
    ----------
    H_ret : float
        Retained soil height, from the top of the base slab to the active-side
        ground surface (m).
    t_base : float
        Base slab thickness (m).
    B : float
        Base slab width, toe edge to heel edge (m).
    toe : float
        Toe length in front of the stem (m).
    t_stem : float
        Stem thickness, assumed constant with depth (m).
    key_depth : float
        Depth of the shear key below the base slab; 0 = no key (m).
    key_width : float
        Width of the shear key (m).
    Df : float
        Embedment: height of the passive-side ground above the underside of the
        base slab (m).
    """

    H_ret: float = 8.0
    t_base: float = 0.5
    B: float = 7.0
    toe: float = 3.0
    t_stem: float = 0.5
    key_depth: float = 0.5
    key_width: float = 0.5
    Df: float = 1.5

    # ------------------------------------------------------------------
    # Derived dimensions
    # ------------------------------------------------------------------
    @property
    def heel(self) -> float:
        """Heel width behind the stem (m)."""
        return self.B - self.toe - self.t_stem

    @property
    def height_total(self) -> float:
        """Overall stem height above the underside of the base slab (m)."""
        return self.t_base + self.H_ret

    @property
    def y_slab_top(self) -> float:
        """Elevation of the top of the base slab (m above slab underside)."""
        return self.t_base

    @property
    def y_ground_active(self) -> float:
        """Elevation of the active-side ground surface (m)."""
        return self.t_base + self.H_ret

    @property
    def y_ground_passive(self) -> float:
        """Elevation of the passive-side (excavation) ground surface (m)."""
        return self.Df

    @property
    def depth_active_profile(self) -> float:
        """Depth below the active ground surface over which pressure acts (m).

        The active pressure is integrated from the ground surface down to the
        bottom of the shear key (or the underside of the base slab when there is
        no key), because the soil in front of the key offers no resistance at
        that level.
        """
        return self.H_ret + self.t_base + self.key_depth

    @property
    def depth_passive_profile(self) -> float:
        """Depth of passive soil, from the excavation surface to slab underside (m)."""
        return self.Df

    @property
    def depth_passive_ground_below_active(self) -> float:
        """Depth of the passive-side ground surface below the active ground (m)."""
        return self.y_ground_active - self.y_ground_passive

    @property
    def key_x_from_toe(self) -> float:
        """Distance from the toe to the front face of the shear key (m)."""
        return self.B - self.key_width

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------
    def validate(self) -> list[str]:
        """Return a list of geometry problems (empty list = valid)."""
        problems: list[str] = []
        if self.H_ret <= 0:
            problems.append("Retained height H must be positive.")
        if self.t_base <= 0:
            problems.append("Base slab thickness must be positive.")
        if self.t_stem <= 0:
            problems.append("Stem thickness must be positive.")
        if self.toe < 0:
            problems.append("Toe length cannot be negative.")
        if self.heel <= 0:
            problems.append("Heel width <= 0: B must exceed toe + t_stem.")
        if self.key_depth < 0:
            problems.append("Shear key depth cannot be negative.")
        if self.key_depth > 0 and self.key_width > self.heel:
            problems.append("Shear key is wider than the heel.")
        if self.Df < self.t_base:
            problems.append(
                "Df < base thickness: the passive-side ground would be below "
                "the top of the base slab.")
        return problems

    # ------------------------------------------------------------------
    # Self-weight
    # ------------------------------------------------------------------
    def weight_blocks(self, soil: Soil,
                      gamma_concrete: float = GAMMA_CONCRETE) -> list[Block]:
        """Self-weight blocks of the concrete and the soil resting on the wall.

        Corresponds to blocks C1-C3 (concrete) and S1-S2 (soil) of the tutorial
        workbook:

        * C1 stem          ``gamma_c * t_stem * H_ret``
        * C2 base slab     ``gamma_c * B * t_base``
        * C3 shear key     ``gamma_c * key_width * key_depth`` (if any)
        * S1 soil on heel  ``gamma * heel * H_ret``
        * S2 soil on toe   ``gamma * toe * (Df - t_base)`` (if any)

        The soil weight uses the bulk unit weight, i.e. no buoyancy is deducted:
        the water pressure is applied separately as a lateral force on both
        sides, which is the convention of the tutorial workbook.  Uplift on the
        base slab is outside the scope of the check (see `docs/validation_notes.md`).

        Parameters
        ----------
        soil : Soil
            Backfill / passive-side soil (bulk unit weight is used).
        gamma_concrete : float
            Unit weight of concrete (kN/m3).

        Returns
        -------
        list[Block]
            Blocks with ``force`` (kN/m) and ``x`` = centroid from the toe (m).
        """
        blocks: list[Block] = []

        # C1 - stem, from the top of the base slab up to the active ground
        # surface (the slab is a separate block, so the stem height excludes
        # the slab thickness to avoid counting that volume twice)
        blocks.append(Block(
            "C1 stem",
            gamma_concrete * self.t_stem * self.H_ret,
            0.0,
            self.toe + self.t_stem / 2.0,
            "weight"))

        # C2 - base slab
        blocks.append(Block(
            "C2 base",
            gamma_concrete * self.B * self.t_base,
            0.0,
            self.B / 2.0,
            "weight"))

        # C3 - shear key at the heel edge
        if self.key_depth > 0:
            blocks.append(Block(
                "C3 key",
                gamma_concrete * self.key_width * self.key_depth,
                0.0,
                self.key_x_from_toe + self.key_width / 2.0,
                "weight"))

        # S1 - retained soil on the heel
        blocks.append(Block(
            "S1 soil on heel",
            soil.gamma * self.heel * self.H_ret,
            0.0,
            self.toe + self.t_stem + self.heel / 2.0,
            "weight"))

        # S2 - passive-side soil on the toe
        t_toe_soil = self.Df - self.t_base
        if t_toe_soil > 0:
            blocks.append(Block(
                "S2 soil on toe",
                soil.gamma * self.toe * t_toe_soil,
                0.0,
                self.toe / 2.0,
                "weight"))

        return blocks
