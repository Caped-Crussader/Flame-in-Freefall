import streamlit as st

from components.api_client import post

st.title("🧪 Risk Simulator")

col1, col2 = st.columns(2)
oxygen = col1.slider("Oxygen (%)", 15.0, 40.0, 21.0)
pressure = col2.slider("Pressure (kPa)", 30.0, 105.0, 101.3)
material = st.selectbox("Material", ["Cotton", "Nomex", "PMMA", "Paper", "Polyethylene"])
flow = st.slider("Ventilation flow (cm/s)", 0.0, 50.0, 5.0)

if st.button("Estimate risk"):
    res = post("/api/insights/risk", {"oxygen_pct": oxygen, "pressure_kpa": pressure,
                                      "material": material, "flow_velocity_cms": flow})
    st.metric("Risk level", res.get("risk_level"), f"score {res.get('risk_score', 0):.2f}")
    st.write(res.get("explanation"))
