"""Soil parameters and Rankine earth-pressure coefficients.

One :class:`Soil` instance describes one homogeneous soil type by its
*characteristic* (unfactored) parameters.  Design values are obtained with
:meth:`Soil.factored`, which applies the GEOGUIDE 1 (2020) partial material
factor to ``tan(phi')`` and ``c'`` (not to ``phi'`` itself, which is why the
factored angle is not simply ``phi'/1.2``).
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from .constants import GAMMA_W, PARTIAL_FACTOR

# Sanity limits used for input validation (also enforced by the UI widgets).
PHI_MIN, PHI_MAX = 0.0, 45.0
C_MIN, C_MAX = 0.0, 200.0
GAMMA_MIN, GAMMA_MAX = 10.0, 25.0


@dataclass
class Soil:
    """Characteristic parameters of one soil type.

    Parameters
    ----------
    name : str
        Label used in reports and diagrams (e.g. ``"Fill"``).
    gamma : float
        Bulk unit weight above the water table (kN/m3).
    c_prime : float
        Effective cohesion (kPa).
    phi_prime : float
        Effective angle of shearing resistance (degrees).
    """

    name: str
    gamma: float
    c_prime: float
    phi_prime: float

    @property
    def gamma_sub(self) -> float:
        """Submerged unit weight ``gamma - gamma_w`` (kN/m3).

        Used for the effective vertical stress below the water table.
        """
        return self.gamma - GAMMA_W

    def factored(self, factor: float = PARTIAL_FACTOR) -> tuple[float, float]:
        """Design (factored) values per GEOGUIDE 1 (2020).

        The partial factor is applied to ``tan(phi')`` and to ``c'``:

            tan(phi'_d) = tan(phi') / factor,   c'_d = c' / factor

        Parameters
        ----------
        factor : float
            Partial material factor.  ``1.0`` returns the characteristic
            values (global-factor approach).

        Returns
        -------
        (phi_d [deg], c_d [kPa])
        """
        if factor <= 0:
            raise ValueError("partial factor must be positive")
        t = math.tan(math.radians(self.phi_prime)) / factor
        return math.degrees(math.atan(t)), self.c_prime / factor

    def validate(self) -> list[str]:
        """Return a list of input problems (empty list = acceptable).

        Checks the physically meaningful ranges only; the UI applies its own
        widget limits on top of this.
        """
        problems: list[str] = []
        if not (PHI_MIN <= self.phi_prime <= PHI_MAX):
            problems.append(
                f"{self.name}: phi' = {self.phi_prime:g} deg is outside "
                f"{PHI_MIN:g}-{PHI_MAX:g} deg.")
        if not (C_MIN <= self.c_prime <= C_MAX):
            problems.append(
                f"{self.name}: c' = {self.c_prime:g} kPa is outside "
                f"{C_MIN:g}-{C_MAX:g} kPa.")
        if not (GAMMA_MIN <= self.gamma <= GAMMA_MAX):
            problems.append(
                f"{self.name}: gamma = {self.gamma:g} kN/m3 is outside "
                f"{GAMMA_MIN:g}-{GAMMA_MAX:g} kN/m3.")
        elif self.gamma <= GAMMA_W:
            problems.append(
                f"{self.name}: gamma must exceed gamma_w = {GAMMA_W:g} kN/m3 "
                "for a submerged unit weight to be positive.")
        return problems


def rankine_ka(phi_deg: float) -> float:
    """Rankine active coefficient ``Ka = (1 - sin phi) / (1 + sin phi)``."""
    s = math.sin(math.radians(phi_deg))
    return (1.0 - s) / (1.0 + s)


def rankine_kp(phi_deg: float) -> float:
    """Rankine passive coefficient ``Kp = (1 + sin phi) / (1 - sin phi)``."""
    s = math.sin(math.radians(phi_deg))
    if s == 1.0:
        raise ValueError("phi = 90 deg gives infinite Kp")
    return (1.0 + s) / (1.0 - s)


def cohesion_term(soil: Soil, k: float, factor: float = PARTIAL_FACTOR) -> float:
    """Cohesion contribution to the lateral pressure ``2 c'_d sqrt(K)`` (kPa).

    ``k`` is ``Ka`` on the active side and ``Kp`` on the passive side; the sign
    of the contribution to the pressure is applied by the caller.
    """
    _, c_d = soil.factored(factor)
    return 2.0 * c_d * math.sqrt(k)
