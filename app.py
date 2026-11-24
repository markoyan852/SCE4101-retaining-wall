"""
Streamlit front-end for the retaining wall stability web app.

Run with:  streamlit run app.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent))
from core import (Soil, WallGeometry, check_results, evaluate, run_analysis)
from viz.draw import draw_pressure, draw_wall

st.set_page_config(page_title="Retaining Wall Checker",
                   page_icon="🏗️", layout="wide")

st.title("🏗️ Retaining Wall Stability Checker")

GLOBAL_FOS = 3.0  # required FOS when the global-factor approach is selected

# --------------------------------------------------------------------------
# Sidebar inputs
# --------------------------------------------------------------------------
with st.sidebar:
    st.header("📐 Design approach")
    approach = st.radio(
        "Method",
        ["Partial factor (GEOGUIDE 1 2020)", "Global factor"],
        help="Partial factor: c'/γm and tan φ'/γm with FOS demand 1.0. "
             "Global factor: characteristic values, FOS demand %.1f." % GLOBAL_FOS,
        label_visibility="collapsed")
    use_partial = approach.startswith("Partial")

    if use_partial:
        partial_factor = st.number_input(
            "Partial factor γₘ (on c′ and tan φ′)",
            min_value=1.0, max_value=2.0, value=1.2, step=0.05, format="%.2f")
        st.caption(rf"$c'_d = c'/\gamma_m$, "
                   rf"$\phi'_d = \tan^{{-1}}(\tan\phi'/\gamma_m)$ with "
                   rf"$\gamma_m$ = {partial_factor:.2f}")
    else:
        partial_factor = 1.0
        st.caption(rf"Characteristic values used ($\gamma_m$ = 1.0); "
                   f"required FOS locked at {GLOBAL_FOS:.1f}")

    st.header("🔧 Geometry")

    def slider_box(label, lo, hi, default, step, key, fmt="%.2f", help=None):
        """Slider plus a synced type-in box.

        Dragging the bar and typing an exact value both work: the two
        widgets share one session-state value, so the user is not locked
        to the slider's step. Returns the current value (float).
        """
        s_key, n_key, v_key = f"{key}_s", f"{key}_n", key
        for k in (s_key, n_key, v_key):
            if k not in st.session_state:
                st.session_state[k] = default
        prev = st.session_state[v_key]
        s_state = st.session_state[s_key]
        n_state = st.session_state[n_key]
        if n_state is None:  # box cleared mid-edit
            n_state = prev
        if s_state != prev and n_state != prev:
            new = n_state        # both moved: trust the typed number
        elif s_state != prev:
            new = s_state
        elif n_state != prev:
            new = n_state
        else:
            new = prev
        new = round(min(max(float(new), lo), hi), 6)
        # keep slider, box and shared value in agreement before rendering
        st.session_state[s_key] = new
        st.session_state[n_key] = new
        st.session_state[v_key] = new
        bar, box_col = st.columns([3.1, 1.05])
        with bar:
            st.slider(label, lo, hi, key=s_key, step=step, format=fmt,
                      help=help)
        with box_col:
            st.number_input(label, min_value=float(lo), max_value=float(hi),
                            key=n_key, step=float(step), format=fmt,
                            label_visibility="collapsed")
        return new

    H_ret = slider_box("Retained height H (m)", 2.0, 12.0, 8.0, 0.1, "H_ret")
    B = slider_box("Base width B (m)", 1.0, 16.0, 7.0, 0.1, "B")
    toe = slider_box("Toe length (m)", 0.0, B, 3.0, 0.1, "toe")
    t_stem = slider_box("Stem thickness (m)", 0.2, 2.0, 0.5, 0.05, "t_stem")
    t_base = slider_box("Base slab thickness (m)", 0.2, 2.0, 0.5, 0.05, "t_base")
    key_depth = slider_box("Shear key depth (m)", 0.0, 2.0, 0.5, 0.05, "key_depth")
    key_width = slider_box("Shear key width (m)", 0.1, 2.0, 0.5, 0.05, "key_width")
    Df = slider_box("Embedment Df (m)", 0.3, 5.0, 1.5, 0.1, "Df")

    st.header("⬇️ Loads & water")
    q_surcharge = slider_box("Surcharge (kPa)", 0.0, 50.0, 10.0, 1.0,
                             "q_surcharge", "%.0f")
    z_water = slider_box("Water table below active ground (m)",
                         0.0, H_ret + t_base, 3.0, 0.1, "z_water")

    st.header("🪨 Soils (type-in values)")

    def box(label, lo, hi, default, step, fmt="%.2f", help=None):
        return st.number_input(label, min_value=float(lo),
                               max_value=float(hi), value=float(default),
                               step=float(step), format=fmt, help=help)

    st.markdown("**Backfill (retained soil)**")
    gamma_fill = box("Backfill γ (kN/m³)", 14.0, 22.0, 18.0, 0.5)
    c_fill = box("Backfill c′ (kPa)", 0.0, 50.0, 2.0, 0.5)
    phi_fill = box("Backfill φ′ (°)", 20.0, 45.0, 32.0, 0.5)
    st.markdown("**Bearing soil (CDG)**")
    gamma_b = box("Bearing γ (kN/m³)", 14.0, 22.0, 19.0, 0.5)
    c_b = box("Bearing c′ (kPa)", 0.0, 50.0, 5.0, 0.5)
    phi_b = box("Bearing φ′ (°)", 20.0, 45.0, 35.0, 0.5)

    st.header("⚙️ Materials & criteria")
    gamma_concrete = slider_box("Concrete γc (kN/m³)", 20.0, 26.0, 24.0, 0.5,
                                "gamma_concrete")
    include_c_term = st.checkbox(
        "Include c′·Nc term in bearing capacity", value=True,
        help="GEO Publication 1/2006 includes the cohesion term. The tutorial "
             "workbook left it blank — untick to reproduce the tutorial value.")
    if use_partial:
        fos_slide_min = slider_box("Min FOS sliding", 1.0, 2.0, 1.0, 0.05,
                                   "fos_slide")
        fos_ot_min = slider_box("Min FOS overturning", 1.0, 3.0, 1.0, 0.05,
                                "fos_ot")
        bearing_fos_min = slider_box("Min bearing ratio qᵤₗₜ / pₘₐₓ",
                                     1.0, 3.0, 1.0, 0.05, "bearing_fos")
    else:
        st.metric("Required FOS (locked)", f"{GLOBAL_FOS:.1f}")
        fos_slide_min = fos_ot_min = bearing_fos_min = GLOBAL_FOS

    if st.button("↺ Reset to Assignment 1 defaults", width="stretch"):
        st.session_state.clear()
        st.rerun()

# --------------------------------------------------------------------------
# Build model and analyse
# --------------------------------------------------------------------------
if use_partial:
    st.caption(rf"Factored ULS checks to GEOGUIDE 1 (2020) — "
               rf"$c'_d = c'/\gamma_m$, "
               rf"$\phi'_d = \tan^{{-1}}(\tan\phi'/\gamma_m)$ with "
               rf"$\gamma_m = {partial_factor:.2f}$; "
               f"FOS demands: sliding {fos_slide_min:.2f}, "
               f"overturning {fos_ot_min:.2f}, bearing {bearing_fos_min:.2f}")
else:
    st.caption(f"Global factor approach — characteristic (unfactored) soil "
               f"parameters; all FOS checks demand FOS ≥ {GLOBAL_FOS:.1f}")

geo = WallGeometry(H_ret=H_ret, t_base=t_base, B=B, toe=toe, t_stem=t_stem,
                   key_depth=key_depth, key_width=key_width, Df=Df)
problems = geo.validate()
if problems:
    st.error("⚠️ Geometry problem: " + " ".join(problems))
    st.stop()

backfill = Soil("Backfill (Fill)", gamma_fill, c_fill, phi_fill)
bearing_soil = Soil("Bearing (CDG)", gamma_b, c_b, phi_b)

soil_problems = backfill.validate() + bearing_soil.validate()
if soil_problems:
    st.error("⚠️ Soil input problem: " + " ".join(soil_problems))
    st.stop()

try:
    res = run_analysis(geo, backfill, bearing_soil, q_surcharge, z_water,
                       gamma_concrete, partial_factor=partial_factor,
                       include_cohesion_in_bearing=include_c_term)
except ValueError as exc:
    st.error(f"⚠️ Cannot analyse this wall: {exc}")
    st.stop()

checks = check_results(res, geo, fos_slide_min, fos_ot_min, bearing_fos_min)
criteria = evaluate(res, geo, fos_slide_min, fos_ot_min, bearing_fos_min)

# --------------------------------------------------------------------------
# Metrics row
# --------------------------------------------------------------------------
c1, c2, c3, c4 = st.columns(4)
c1.metric("Sliding FOS", f"{res.fos_sliding:.2f}",
          delta=f"limit {fos_slide_min:.2f}",
          delta_color="normal" if checks["sliding"] else "inverse")
c2.metric("Overturning FOS", f"{res.fos_overturning:.2f}",
          delta=f"limit {fos_ot_min:.2f}",
          delta_color="normal" if checks["overturning"] else "inverse")
c3.metric("Max bearing pressure", f"{res.p_max:.1f} kPa",
          delta=f"qᵤₗₜ/pₘₐₓ = {res.q_ult / max(res.p_max, 1e-9):.2f} "
                f"(need {bearing_fos_min:.2f})",
          delta_color="normal" if checks["bearing"] else "inverse")
c4.metric("Eccentricity e", f"{res.eccentricity:.3f} m",
          delta=f"B/6 = {geo.B/6:.3f} m",
          delta_color="normal" if checks["middle_third"] else "inverse")

ok = all(checks.values())
st.success("✅ All stability checks PASS" if ok else "❌ Design FAILS — adjust geometry")

with st.expander("✅ Check summary", expanded=True):
    st.dataframe([c.as_row() for c in criteria], width="stretch",
                 hide_index=True)
    if res.tension_crack_depth > 0:
        st.caption(f"Tension crack treated as zero pressure down to "
                   f"{res.tension_crack_depth:.2f} m below the active ground.")

# --------------------------------------------------------------------------
# Design parameters: characteristic -> factored
# --------------------------------------------------------------------------
with st.expander("🧮 Design parameters (characteristic → factored)",
                 expanded=False):
    phi_f_d, c_f_d = backfill.factored(partial_factor)
    phi_b_d, c_b_d = bearing_soil.factored(partial_factor)
    param_rows = [
        {"Soil": "Backfill (active)", "γ (kN/m³)": backfill.gamma,
         "γ_d (kN/m³)": backfill.gamma, "c′ (kPa)": backfill.c_prime,
         "c′_d (kPa)": round(c_f_d, 2), "φ′ (°)": backfill.phi_prime,
         "φ′_d (°)": round(phi_f_d, 2),
         "K (design)": f"{res.blocks['Ka']:.4f}  K_a"},
        {"Soil": "Backfill (passive)", "γ (kN/m³)": backfill.gamma,
         "γ_d (kN/m³)": backfill.gamma, "c′ (kPa)": backfill.c_prime,
         "c′_d (kPa)": round(c_f_d, 2), "φ′ (°)": backfill.phi_prime,
         "φ′_d (°)": round(phi_f_d, 2),
         "K (design)": f"{res.blocks['Kp']:.4f}  K_p"},
        {"Soil": "Bearing (base)", "γ (kN/m³)": bearing_soil.gamma,
         "γ_d (kN/m³)": bearing_soil.gamma, "c′ (kPa)": bearing_soil.c_prime,
         "c′_d (kPa)": round(c_b_d, 2), "φ′ (°)": bearing_soil.phi_prime,
         "φ′_d (°)": round(phi_b_d, 2), "K (design)": "—"},
    ]
    st.dataframe(param_rows, width="stretch", hide_index=True)
    st.caption(
        rf"$c'_d = c'/\gamma_m$ and "
        rf"$\phi'_d = \tan^{{-1}}(\tan\phi'/\gamma_m)$ with "
        rf"$\gamma_m$ = {partial_factor:.2f}; unit-weight factor = 1.0.")

# --------------------------------------------------------------------------
# Diagrams
# --------------------------------------------------------------------------
left, right = st.columns([3, 2])
with left:
    st.pyplot(draw_wall(geo, q_surcharge, z_water), width="stretch")
with right:
    st.pyplot(draw_pressure(geo, backfill, q_surcharge, z_water,
                            factor=partial_factor),
              width="stretch")

# --------------------------------------------------------------------------
# Detailed results
# --------------------------------------------------------------------------
with st.expander("📋 Detailed force / moment table"):
    pa_earth = sum(f for _, f, _ in res.blocks["active"])
    pa_water = sum(f for _, f, _ in res.blocks["water_active"])
    pp_earth = sum(f for _, f, _ in res.blocks["passive"])
    pp_water = sum(f for _, f, _ in res.blocks["water_passive"])
    st.markdown(
        rf"**Lateral forces** — active $\Sigma H_a = {pa_earth + pa_water:.1f}$ kN "
        rf"(earth {pa_earth:.1f} + water {pa_water:.1f}) · "
        rf"passive $\Sigma P_p = {pp_earth + pp_water:.1f}$ kN "
        rf"(earth {pp_earth:.1f} + water {pp_water:.1f})"
    )
    st.markdown(
        rf"**Design coefficients** — $K_a = {res.blocks['Ka']:.4f}$, "
        rf"$K_p = {res.blocks['Kp']:.4f}$, "
        rf"$\Sigma W = {res.sum_W:.1f} \text{{ kN}}$"
    )
    st.markdown(
        rf"$M_{{ov}} = {res.M_overturn:.1f} \text{{ kNm}} \quad\cdot\quad "
        rf"M_R = {res.M_resist:.1f} \text{{ kNm}}$"
    )
    rows = []
    for grp, key in [("Active earth", "active"), ("Active water", "water_active"),
                     ("Passive earth", "passive"), ("Passive water", "water_passive")]:
        for label, f, lever in res.blocks[key]:
            rows.append({"Group": grp, "Block": label, "Force (kN/m)": round(f, 2),
                         "Lever arm (m)": round(lever, 3),
                         "Moment (kNm/m)": round(f * lever, 2)})
    for label, f, x in res.blocks["weights"]:
        rows.append({"Group": "Weights", "Block": label,
                     "Force (kN/m)": round(f, 2),
                     "Lever arm (m)": round(x, 3),
                     "Moment (kNm/m)": round(f * x, 2)})
    st.dataframe(rows, width="stretch", hide_index=True)
    bd = res.bearing_detail
    l_prime = bd["L'"]
    st.markdown(
        rf"$N_q = {bd['Nq']:.2f} \;\; N_c = {bd['Nc']:.2f} \;\; "
        rf"N_\gamma = {bd['Ngamma']:.2f} \;\;|\;\; "
        rf"s_c = {bd['sc']:.3f} \;\; s_q = {bd['sq']:.3f} \;\; "
        rf"s_\gamma = {bd['sg']:.3f} \;\;|\;\; "
        rf"K_i = {bd['Ki']:.3f} \;\; i_q = {bd['iq']:.3f} \;\; "
        rf"i_\gamma = {bd['ig']:.3f} \;\; i_c = {bd['ic']:.3f} \;\;|\;\; "
        rf"L' = {l_prime:.3f} \text{{ m}}$")
    st.markdown(
        rf"$p_{{min}} = {res.p_min:.1f} \text{{ kPa}} \quad\cdot\quad "
        rf"q_{{ult}} = {res.q_ult:.1f} \text{{ kPa}} \quad\cdot\quad "
        rf"\text{{Base friction}} = {res.blocks['base_friction']:.1f} \text{{ kN}} "
        rf"\;\;|\;\; "
        rf"\text{{Base adhesion}} = {res.blocks['base_adhesion']:.1f} \text{{ kN}} "
        rf"\;\;|\;\; "
        rf"\text{{Passive resistance}} = {res.blocks['F_passive']:.1f} \text{{ kN}}$")
