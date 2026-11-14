"""Page 3: Moon/Mars Habitat Flammability & Risk Simulator."""
from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd
import streamlit as st

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR / "frontend") not in sys.path:
    sys.path.insert(0, str(ROOT_DIR / "frontend"))

from components.api_client import post  # noqa: E402

st.set_page_config(page_title="Risk Simulator | Flame in Freefall", page_icon="🧪", layout="wide")

st.title("🧪 Spacecraft & Lunar/Martian Habitat Flammability Simulator")
st.caption(
    "Estimate sustained flammability probability, spread rate, and flame temperature using a Random Forest model "
    "trained on the 840 physical microgravity experiments, and retrieve the 5 closest real NASA/JAXA tests."
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
oxygen = col1.slider("Cabin Oxygen (% O₂)", 12.0, 50.0, float(st.session_state.sim_o2), 0.5)
pressure = col2.slider("Cabin Pressure (kPa)", 25.0, 120.0, float(st.session_state.sim_kpa), 0.5)
airflow = col3.slider("HVAC Airflow Velocity (cm/s)", 0.0, 60.0, float(st.session_state.sim_flow), 0.5)
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

st.markdown("#### Recommended Fire-Safety & Crew Controls")
for rec in res.get("recommendations", []):
    st.markdown(f"- {rec}")

st.markdown("#### 5 Closest Historical NASA/JAXA Experiments in `(O₂, Pressure, Airflow, Material)` Space")
nearest = res.get("nearest_experiments", [])
if nearest:
    st.dataframe(pd.DataFrame(nearest), use_container_width=True, hide_index=True)
