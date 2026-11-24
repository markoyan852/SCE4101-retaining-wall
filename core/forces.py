"""Force blocks: the common record for every load in the stability calculation.

A retaining-wall stability check is a sum of forces and moments.  Each
contributor (a rectangle or triangle of lateral pressure, the stem, the base
slab, a soil wedge on the heel) is described by one :class:`Block`, so that the
same summation code can be used for earth pressures, water pressures and
self-weights.

Sign conventions
----------------
* ``force`` is always positive (magnitude, kN per metre run).
* Lateral blocks carry the lever arm ``z``: depth below the profile datum (m).
* Weight blocks carry the lever arm ``x``: distance from the toe (m), which is
  also the x-coordinate of the centroid in the cross-section drawing.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Block:
    """One force block (kN/m) with its centroid.

    Parameters
    ----------
    label : str
        Short identifier shown in the results table (e.g. ``"A1"``, ``"Stem"``).
    force : float
        Magnitude of the resultant force per metre run of wall (kN/m).
    z : float
        Lever arm for lateral blocks: centroid depth below the profile datum (m).
        Zero for weight blocks.
    x : float
        Lever arm for weight blocks: centroid distance from the toe (m).
        Zero for lateral blocks.
    kind : str
        ``"lateral"`` or ``"weight"`` -- used only for reporting/plotting.
    """

    label: str
    force: float
    z: float = 0.0
    x: float = 0.0
    kind: str = "lateral"


def total_force(blocks: list[Block]) -> float:
    """Return the sum of the block forces (kN/m)."""
    return sum(b.force for b in blocks)


def total_moment(blocks: list[Block], lever_arm: str = "z") -> float:
    """Return the sum of ``force x lever arm`` (kNm/m).

    Parameters
    ----------
    blocks : list[Block]
        Blocks to sum.
    lever_arm : str
        ``"z"`` for lateral blocks (depth), ``"x"`` for weight blocks
        (distance from the toe).
    """
    if lever_arm not in ("z", "x"):
        raise ValueError("lever_arm must be 'z' or 'x'")
    return sum(b.force * getattr(b, lever_arm) for b in blocks)
