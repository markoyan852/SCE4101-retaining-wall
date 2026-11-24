# Retaining Wall Stability Checker

Streamlit web app for SCE4101 Large Programme Development: enter a cantilever retaining
wall's geometry, soil parameters, water table and surcharge, and the app checks it against
the stability requirements of GEOGUIDE 1 (2020) and GEO Publication 1/2006.

## Run

```bash
cd retaining_wall_app
pip install -r requirements.txt
streamlit run app.py
```

The browser opens on the app; everything runs offline.

> The folder lives in OneDrive, so keep the virtual environment **outside** it — a
> ~475 MB `.venv` would sync to every machine (and a macOS one is useless on Windows).
> On this machine it is at `~/.venvs/sce4101-retaining-wall`.

## What it checks

| Check | Method | Limit |
|---|---|---|
| Active / passive earth pressure | Rankine, with `c'` term, partial-factored `c'`, `tan φ'` | — |
| Water pressure | Hydrostatic `u = γw h`, active and passive side | — |
| Sliding | `(Pp + V tan φ'd + B c'd) / ΣH` | ≥ 1.0 (factored ULS) or 3.0 (global) |
| Overturning | `MR / MO` about the toe | ≥ 1.0 / 3.0 |
| Eccentricity | `e = B/2 − ΣM/ΣV`, middle-third test | `|e| ≤ B/6` |
| Base pressure | `p = ΣV/B (1 ± 6e/B)` | `p_min ≥ 0` via middle third |
| Bearing capacity | `Nq/Nc/Nγ` + shape and load-inclination factors | `q_ult / p_max ≥ 1.0` |

Two design approaches are available: **partial factor** (GEOGUIDE 1 2020, editable factor
and FOS demands) and **global factor** (characteristic parameters, FOS locked at 3.0).

## Layout

```
app.py                  Streamlit page: inputs, validation, result cards, tables
core/
  constants.py          γw, default partial factor, concrete unit weight
  forces.py             Block = one force + lever arm, summation helpers
  soil.py               Soil, Rankine Ka/Kp, partial factoring
  geometry.py           WallGeometry, validation, self-weight blocks
  earth_pressure.py     active/passive profiles, block decomposition, tension crack
  hydro.py              hydrostatic water pressure
  bearing.py            bearing capacity factors and q_ult
  stability.py          run_analysis: sliding, overturning, e, p_max/p_min
  checks.py             pass/fail criteria
viz/draw.py             Matplotlib cross-section and pressure diagrams
tests/                  pytest suite (formulae, workbook benchmark, UI smoke tests)
```

## Tests

```bash
pip install -r requirements-dev.txt
pytest
```

The suite checks each formula against hand calculations, the tutorial workbook
(`Reference/Geo Assignment 1 calculation.xlsx`) against documented tolerances, the boundary
behaviour of the inputs, and runs the Streamlit page headlessly with
`streamlit.testing.AppTest`.

Where the workbook and the theory disagree, the app follows the theory; the differences and
their causes are recorded in [`../docs/validation_notes.md`](../docs/validation_notes.md).

## References

* GEOGUIDE 1 (2020) — Guide to Retaining Wall Design, Geotechnical Engineering Office, Hong Kong.
* GEO Publication No. 1/2006 — Foundation Design and Construction.
* SCE4101 lecture notes 1, *Retaining Wall Design*.
