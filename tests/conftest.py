"""Shared pytest fixtures and path setup.

The app is run as a script (``streamlit run app.py``), so the package root is
added to ``sys.path`` here to make ``import core`` work under pytest without
installing the project.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

APP_ROOT = Path(__file__).resolve().parents[1]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from core import Soil, WallGeometry  # noqa: E402


@pytest.fixture
def assignment1_geometry() -> WallGeometry:
    """Wall dimensions read from the tutorial workbook (blocks C1-C3, S1-S2).

    B = 7.0 m, toe = 3.0 m, stem = 0.5 m, heel = 3.5 m, slab = 0.5 m,
    key 0.5 x 0.5 m at the heel, retained height 8 m, embedment 1.5 m.
    """
    return WallGeometry(H_ret=8.0, t_base=0.5, B=7.0, toe=3.0, t_stem=0.5,
                        key_depth=0.5, key_width=0.5, Df=1.5)


@pytest.fixture
def fill() -> Soil:
    """Backfill soil of the tutorial case (characteristic values)."""
    return Soil("Fill", gamma=18.0, c_prime=2.0, phi_prime=32.0)


@pytest.fixture
def cdg() -> Soil:
    """Bearing soil of the tutorial case (completely decomposed granite)."""
    return Soil("CDG", gamma=19.0, c_prime=5.0, phi_prime=35.0)
