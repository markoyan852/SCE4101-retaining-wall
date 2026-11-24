"""Physical constants and default design factors used across the package.

All values are in kN, m, kPa and degrees; results are per metre run of wall.
"""
from __future__ import annotations

# Unit weight of water (kN/m3).  The tutorial workbook uses 9.81, not 10.
GAMMA_W = 9.81

# Default partial material factor on tan(phi') and c' (GEOGUIDE 1, 2020).
PARTIAL_FACTOR = 1.2

# Default unit weight of reinforced concrete (kN/m3).
GAMMA_CONCRETE = 24.0
