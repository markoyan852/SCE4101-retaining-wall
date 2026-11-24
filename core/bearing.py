"""Ultimate bearing capacity of the base slab (GEO Publication 1/2006 form).

The bearing resistance is calculated for an equivalent strip footing under the
base slab (per metre run of wall), using Meyerhof/Vesic-style bearing capacity
factors with shape and load-inclination factors:

    q_ult = c'_d Nc sc ic + q Nq sq iq + 0.5 gamma B' Ngamma sgamma igamma

with ``q = gamma * Df`` the surcharge at founding level.  Tilt and ground-slope
factors are taken as 1.0 (level base, level ground, vertical wall).  The load
inclination is derived from the horizontal driving force and the vertical load
on the base.
"""
from __future__ import annotations

import math

from .constants import PARTIAL_FACTOR
from .soil import Soil

# Nc at phi = 0 (undrained limit, Prandtl), used to avoid 0/0 in the factors.
NC_PHI_ZERO = 5.14


def bearing_factors(phi_deg: float) -> tuple[float, float, float]:
    """Bearing capacity factors ``(Nq, Nc, Ngamma)``.

    .. math::
        N_q = e^{\\pi \\tan\\phi} \\tan^2(45^\\circ + \\phi/2), \\quad
        N_c = (N_q - 1)/\\tan\\phi, \\quad
        N_\\gamma = 2 (N_q + 1) \\tan\\phi

    At ``phi = 0`` the analytic limit ``Nq = 1, Nc = 5.14, Ngamma = 0`` is
    returned instead of the indeterminate form.
    """
    phi = math.radians(phi_deg)
    tan_phi = math.tan(phi)
    if tan_phi < 1e-9:
        return 1.0, NC_PHI_ZERO, 0.0
    nq = math.exp(math.pi * tan_phi) * math.tan(math.radians(45.0 + phi_deg / 2.0)) ** 2
    nc = (nq - 1.0) / tan_phi
    ngamma = 2.0 * (nq + 1.0) * tan_phi
    return nq, nc, ngamma


def shape_factors(phi_deg: float, nq: float, nc: float,
                  b_prime: float, l_prime: float) -> tuple[float, float, float]:
    """Shape factors ``(sc, sq, sgamma)`` for a footing ``B' x L'``.

    With ``r = B'/L'``: ``sc = 1 + (Nq/Nc) r``, ``sq = 1 + tan(phi) r`` and
    ``sgamma = 1 - 0.4 r``.  For a long strip footing (``r -> 1``) all three
    approach their strip values.
    """
    r = b_prime / l_prime
    tan_phi = math.tan(math.radians(phi_deg))
    sc = 1.0 + (nq / nc) * r if nc > 1e-9 else 1.0
    sq = 1.0 + tan_phi * r
    sg = 1.0 - 0.4 * r
    return sc, sq, sg


def inclination_factors(h_load: float, v_load: float, c_d: float,
                        phi_deg: float, b_prime: float, l_prime: float,
                        nq: float, nc: float) -> dict[str, float]:
    """Load inclination factors and the auxiliary values used to derive them.

    ``Ki = H / (V + A' c'_d / tan(phi'))`` is the normalised horizontal load;
    then ``iq = (1 - Ki)^m``, ``igamma = (1 - Ki)^(m+1)``,
    ``ic = iq - (1 - iq)/(Nc tan(phi'))`` and ``m = (2 + B'/L')/(1 + B'/L')``.

    Returns a dict with ``m``, ``Ki``, ``iq``, ``ig`` and ``ic``.
    """
    tan_phi = math.tan(math.radians(phi_deg))
    r = b_prime / l_prime
    m = (2.0 + r) / (1.0 + r)
    a_eff = b_prime * l_prime
    if tan_phi < 1e-9:
        denominator = v_load + a_eff * c_d
    else:
        denominator = v_load + a_eff * c_d / tan_phi
    ki = min(h_load / denominator, 1.0) if denominator > 1e-9 else 1.0
    iq = (1.0 - ki) ** m
    ig = (1.0 - ki) ** (m + 1.0)
    ic = iq - (1.0 - iq) / (nc * tan_phi) if tan_phi > 1e-9 else iq
    return {"m": m, "Ki": ki, "iq": iq, "ig": ig, "ic": ic}


def ultimate_bearing_capacity(phi_d: float, c_d: float, gamma_overburden: float,
                              gamma_term: float, b_prime: float, l_prime: float,
                              df: float, h_load: float, v_load: float,
                              include_cohesion: bool = True) -> tuple[float, dict]:
    """Ultimate bearing capacity ``q_ult`` (kPa) and the intermediate values.

    Parameters
    ----------
    phi_d, c_d : float
        Factored (design) bearing-soil parameters (degrees, kPa).
    gamma_overburden : float
        Unit weight used for the surcharge at founding level, ``q = gamma Df``
        (kN/m3).
    gamma_term : float
        Unit weight used in the ``0.5 gamma B' Ngamma`` term (kN/m3); use the
        submerged value when the foundation is below the water table.
    b_prime, l_prime : float
        Effective footing dimensions (m); ``B' = 1 m`` across the wall run.
    df : float
        Founding depth below the passive-side ground (m).
    h_load, v_load : float
        Horizontal driving force and vertical load on the base (kN/m).
    include_cohesion : bool
        Set to ``False`` to omit the ``c' Nc`` term.  The tutorial workbook
        leaves this term out; the code default (``True``) includes it because it
        is part of the bearing formula in GEO Publication 1/2006.

    Returns
    -------
    (q_ult [kPa], detail dict)
        The detail dict holds the factors, the effective dimensions, the
        overburden term and the cohesion term for reporting.
    """
    nq, nc, ngamma = bearing_factors(phi_d)
    sc, sq, sg = shape_factors(phi_d, nq, nc, b_prime, l_prime)
    inc = inclination_factors(h_load, v_load, c_d, phi_d, b_prime, l_prime, nq, nc)

    q_surcharge = gamma_overburden * df
    c_term = c_d * nc * sc * inc["ic"] if include_cohesion else 0.0
    q_ult = (c_term
             + q_surcharge * nq * sq * inc["iq"]
             + 0.5 * gamma_term * b_prime * ngamma * sg * inc["ig"])

    detail = {
        "Nq": nq, "Nc": nc, "Ngamma": ngamma,
        "sc": sc, "sq": sq, "sg": sg,
        **inc,
        "B'": b_prime, "L'": l_prime,
        "q_surcharge": q_surcharge, "c_term": c_term,
    }
    return q_ult, detail


def bearing_capacity(soil: Soil, gamma_overburden: float, gamma_term: float,
                     b_prime: float, l_prime: float, df: float,
                     h_load: float, v_load: float,
                     factor: float = PARTIAL_FACTOR,
                     include_cohesion: bool = True) -> tuple[float, dict]:
    """Convenience wrapper: factor one :class:`Soil` and call the capacity formula."""
    phi_d, c_d = soil.factored(factor)
    return ultimate_bearing_capacity(phi_d, c_d, gamma_overburden, gamma_term,
                                     b_prime, l_prime, df, h_load, v_load,
                                     include_cohesion)
