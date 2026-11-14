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
m1.metric("Flammability Risk Level", f"{badge} {lvl}", f"Score: {res.get('risk_score', 0):.2f} / 1.00")
m2.metric("Sustained Burn Probability", f"{res.get('sustained_burn_probability', 0) * 100:.1f}%", "Random Forest Classifier")
m3.metric("Predicted Spread / Burn Rate", f"{res.get('predicted_burning_rate_mms', 0):.2f} mm/s", "Family-peer estimate")
m4.metric("Predicted Flame Temperature", f"{res.get('predicted_flame_temp_k', 0):.0f} K", "Estimated reaction temp")

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

st.markdown("#### 🔬 5 Closest Historical NASA/JAXA Experiments in `(O₂, Pressure, Airflow, Material)` Space")
nearest = res.get("nearest_experiments", [])
if nearest:
    st.dataframe(pd.DataFrame(nearest), use_container_width=True, hide_index=True)
