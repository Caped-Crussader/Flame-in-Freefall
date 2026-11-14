"""Page 3: Moon/Mars Habitat Flammability & Risk Simulator + 2D MOC Boundary Envelope."""
from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd
import streamlit as st

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR / "frontend") not in sys.path:
    sys.path.insert(0, str(ROOT_DIR / "frontend"))

from components.api_client import post  # noqa: E402
from components.charts import (  # noqa: E402
    airflow_quenching_contour_chart,
    flammability_moc_contour_chart,
)
from components.theme import apply_flame_theme  # noqa: E402

st.set_page_config(page_title="Risk Simulator | Flame in Freefall", page_icon="🧪", layout="wide")

apply_flame_theme(
    title="Spacecraft & Lunar/Martian Habitat Flammability Simulator",
    subtitle="Estimate sustained flammability probability, spread rate, flame temperature, and 2D Minimum Oxygen Concentration (MOC) boundary curves from 840 physical microgravity experiments.",
    badge="ML FLAMMABILITY PREDICTOR & 2D MOC ENVELOPE",
)

# Mission presets
st.markdown("#### Quick Mission Atmosphere Presets")
p1, p2, p3, p4 = st.columns(4)
if "sim_o2" not in st.session_state:
    st.session_state.sim_o2 = 21.0
    st.session_state.sim_kpa = 101.3
    st.session_state.sim_flow = 5.0
    st.session_state.sim_mat = "SIBAL (Cotton-Fiberglass Blend)"

if p1.button("🛰️ ISS Standard (21% O₂, 101.3 kPa)", use_container_width=True):
    st.session_state.sim_o2 = 21.0
    st.session_state.sim_kpa = 101.3
    st.session_state.sim_flow = 8.0
if p2.button("🌙 Artemis Lunar Habitat (34% O₂, 56.5 kPa)", use_container_width=True):
    st.session_state.sim_o2 = 34.0
    st.session_state.sim_kpa = 56.5
    st.session_state.sim_flow = 10.0
if p3.button("👨‍🚀 EVA Pre-Breathe (26.5% O₂, 70.3 kPa)", use_container_width=True):
    st.session_state.sim_o2 = 26.5
    st.session_state.sim_kpa = 70.3
    st.session_state.sim_flow = 6.0
if p4.button("🛑 Fans Off / Quiescent (21% O₂, 0 cm/s)", use_container_width=True):
    st.session_state.sim_o2 = 21.0
    st.session_state.sim_kpa = 101.3
    st.session_state.sim_flow = 0.0

parquet_path = ROOT_DIR / "data" / "processed" / "experiments.parquet"
df = pd.read_parquet(parquet_path)
popular_materials = [
    "SIBAL (Cotton-Fiberglass Blend)",
    "PMMA (Acrylic)",
    "Nomex (Aramid)",
    "Velcro Hook-and-Loop (Nylon)",
    "Cotton Fabric",
    "Polyurethane Foam (Open-Cell)",
    "Methanol",
    "n-Heptane",
    "Ethanol",
    "Cellulose Tissue / Kimwipe",
]
all_mats = popular_materials + [
    m for m in sorted(df["fuel_material"].dropna().unique().tolist()) if m not in popular_materials
]

col1, col2, col3, col4 = st.columns(4)
oxygen = col1.slider("Cabin Oxygen (% O₂)", 12.0, 48.0, float(st.session_state.sim_o2), 0.5)
pressure = col2.slider("Cabin Pressure (kPa)", 25.0, 115.0, float(st.session_state.sim_kpa), 0.5)
airflow = col3.slider("HVAC Airflow Velocity (cm/s)", 0.0, 55.0, float(st.session_state.sim_flow), 0.5)
material = col4.selectbox("Fuel / Specimen Material", all_mats, index=0)

res = post(
    "/insights/risk",
    {
        "oxygen_pct": oxygen,
        "pressure_kpa": pressure,
        "airflow_velocity_cms": airflow,
        "fuel_material": material,
        "gravity_regime": "Microgravity (~0g)",
    },
)

st.divider()
m1, m2, m3, m4 = st.columns(4)
lvl = res.get("risk_level", "MODERATE")
badge = "🔴" if lvl == "CRITICAL" else "🟠" if lvl == "HIGH" else "🟡" if lvl == "MODERATE" else "🟢"
unc = res.get("uncertainty") or {}
phys = res.get("physics_diagnostics") or {}
conf_str = (
    f" · {unc.get('confidence_level', 'HIGH')} ({unc.get('confidence_score', 0.8) * 100:.0f}%)"
    if unc
    else ""
)
br_ci = unc.get("burning_rate_ci90_mms", [0.0, 0.0])
ft_ci = unc.get("flame_temp_ci90_k", [0.0, 0.0])
m1.metric("Flammability Risk Level", f"{badge} {lvl}", f"Score: {res.get('risk_score', 0):.2f}{conf_str}")
m2.metric(
    "Sustained Burn Probability",
    f"{res.get('sustained_burn_probability', 0) * 100:.1f}%",
    f"Ensemble ±{unc.get('sustained_prob_std', 0) * 100:.1f}%",
)
m3.metric(
    "Predicted Spread / Burn Rate",
    f"{res.get('predicted_burning_rate_mms', 0):.2f} mm/s",
    f"90% CI: {br_ci[0]:.2f}–{br_ci[1]:.2f} mm/s" if len(br_ci) == 2 else "Ensemble RF",
)
m4.metric(
    "Predicted Flame Temperature",
    f"{res.get('predicted_flame_temp_k', 0):.0f} K",
    f"90% CI: {ft_ci[0]:.0f}–{ft_ci[1]:.0f} K" if len(ft_ci) == 2 else "Ensemble RF",
)

if phys:
    st.markdown("#### ⚛️ Physics-Informed Nondimensional Diagnostics (7-Feature Coupled Engine)")
    p_c1, p_c2, p_c3, p_c4 = st.columns(4)
    p_c1.metric(
        "O₂ Partial Pressure (P_O₂)",
        f"{phys.get('oxygen_partial_pressure_kpa', 0):.2f} kPa",
        f"{phys.get('normoxic_po2_ratio', 1.0):.2f}× Earth Normoxic",
    )
    p_c2.metric(
        "Inert Diluent Ratio (N₂/O₂)",
        f"{phys.get('diluent_to_o2_ratio', 3.76):.2f} : 1",
        "Earth Air Baseline: 3.76 : 1",
    )
    p_c3.metric(
        "0g MOC vs. 1g STD-6001",
        f"{phys.get('moc_0g_limit_o2_pct', 0):.1f}% vs. {phys.get('moc_1g_std6001_limit_o2_pct', 0):.1f}%",
        phys.get("transport_regime", ""),
    )
    margin = phys.get("moc_safety_margin_o2_pct", 0.0)
    p_c4.metric(
        "0g MOC Safety Margin",
        f"{margin:+.1f}% O₂",
        "Below 0g limit" if margin >= 0 else "Exceeds 0g MOC limit",
    )

st.info(f"**1g NASA-STD-6001 vs. Microgravity Comparison:** {res.get('std6001_comparison')}")

envelope = res.get("envelope")
if envelope:
    st.markdown("### 🗺️ 2D Flammability Envelope & Minimum Oxygen Concentration (MOC) Boundary Curves")
    st.caption(
        "**Left:** Oxygen (% O₂) vs. Cabin Pressure (kPa) contour surface comparing the **0g Microgravity MOC Boundary** "
        "(solid cyan curve) against the **1g NASA-STD-6001 Upward Screening MOC** (dashed green curve) with real flight/drop-tower data points. "
        "**Right:** Microgravity ventilation U-curve showing **Diffusive Quenching (<1.5 cm/s)** when cabin fans are shut off vs. **Peak Ventilation Hazard (2–22 cm/s)**."
    )
    c_left, c_right = st.columns(2)
    with c_left:
        st.plotly_chart(
            flammability_moc_contour_chart(envelope, oxygen, pressure, material, airflow),
            use_container_width=True,
        )
    with c_right:
        st.plotly_chart(
            airflow_quenching_contour_chart(envelope, oxygen, airflow, material, pressure),
            use_container_width=True,
        )

st.markdown("#### 🛡️ Recommended Fire-Safety & Crew Controls")
for rec in res.get("recommendations", []):
    st.markdown(f"- {rec}")

det_sup = res.get("detection_suppression") or {}
if det_sup:
    st.markdown("### 🚨 Spacecraft Fire Detection, Suppression & Post-Fire Cleanup Advisor (`SAME`, `DAFT`, `SLICE`, `SAFFIRE IV–VI`)")
    d1, d2, d3, d4 = st.columns(4)
    d1.metric(
        "0g Smoke Particle CMD",
        f"{det_sup.get('smoke_cmd_0g_um', 0.42):.2f} μm",
        f"vs. {det_sup.get('smoke_cmd_1g_um', 0.14):.2f} μm in 1g",
    )
    d2.metric(
        "Laser Photoelectric vs. Ionization",
        f"{det_sup.get('photoelectric_sensitivity', 0.9) * 100:.0f}% vs. {det_sup.get('ionization_sensitivity', 0.6) * 100:.0f}%",
        f"Alarm Delay ~{det_sup.get('estimated_alarm_time_s', 25):.0f} s",
    )
    d3.metric(
        "Est. Peak CO Concentration",
        f"{det_sup.get('estimated_peak_co_ppm', 0):.1f} ppm",
        det_sup.get("co_toxicity_level", ""),
    )
    d4.metric(
        "Target CO₂ Flood / N₂ LOI",
        f"{det_sup.get('required_co2_inerting_pct', 18.0):.1f}% CO₂",
        f"LOI < {det_sup.get('limiting_oxygen_index_pct', 13.8):.1f}% O₂",
    )
    st.info(
        f"**Optimal Detector Modality:** {det_sup.get('recommended_detector_modality')} — {det_sup.get('detector_rationale')}\n\n"
        f"**🌕 Lunar Dust False-Alarm Mitigation (`DAFT / DAFT-2`):** {det_sup.get('lunar_dust_discrimination_note')}"
    )
    st.markdown(f"**Primary Extinguishant (`SLICE`):** `{det_sup.get('primary_extinguishant')}` | **Backup:** `{det_sup.get('secondary_extinguishant')}`")
    ext_opts = det_sup.get("extinguishant_options", [])
    if ext_opts:
        st.dataframe(pd.DataFrame(ext_opts), use_container_width=True, hide_index=True)
    st.markdown("**♻️ Post-Fire Cabin Scrubbing & ECLSS Recovery Protocol (`SAFFIRE-VI`):**")
    for step in det_sup.get("post_fire_cleanup_steps", []):
        st.markdown(f"- {step}")

st.markdown("#### 🔬 5 Closest Historical NASA/JAXA Experiments in `(O₂, Pressure, Airflow, Material)` Space")
nearest = res.get("nearest_experiments", [])
if nearest:
    st.dataframe(pd.DataFrame(nearest), use_container_width=True, hide_index=True)

st.divider()
st.markdown("### 📜 Exportable Mission Fire-Safety Dossier (PDF Certificate & Markdown Report)")
dossier_res = post(
    "/insights/dossier",
    {
        "oxygen_pct": oxygen,
        "pressure_kpa": pressure,
        "airflow_velocity_cms": airflow,
        "fuel_material": material,
        "gravity_regime": "Microgravity (~0g)",
    },
)
if dossier_res and dossier_res.get("dossier_id"):
    dl1, dl2 = st.columns(2)
    dl1.download_button(
        label=f"📥 Download Markdown Dossier ({dossier_res['dossier_id']}.md)",
        data=dossier_res.get("markdown_report", ""),
        file_name=f"{dossier_res['dossier_id']}.md",
        mime="text/markdown",
        use_container_width=True,
    )
    dl2.download_button(
        label=f"🖨️ Download Print-Ready PDF/HTML Certificate ({dossier_res['dossier_id']}.html)",
        data=dossier_res.get("html_printable", ""),
        file_name=f"{dossier_res['dossier_id']}.html",
        mime="text/html",
        use_container_width=True,
    )
    with st.expander("👁️ Preview Generated Mission Fire-Safety Dossier Markdown"):
        st.markdown(dossier_res.get("markdown_report", ""))
