"""Streamlit Mission Control Dashboard Home.

Run:
    streamlit run frontend/app.py
"""
from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd
import streamlit as st

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR / "frontend") not in sys.path:
    sys.path.insert(0, str(ROOT_DIR / "frontend"))

from components.api_client import get, health  # noqa: E402
from components.charts import (  # noqa: E402
    atmosphere_envelope_chart,
    family_distribution_chart,
)
from components.theme import apply_flame_theme  # noqa: E402

st.set_page_config(
    page_title="Flame in Freefall | NASA Space Apps 2026",
    page_icon="🔥",
    layout="wide",
)

apply_flame_theme(
    title="Flame in Freefall",
    subtitle="SI-Powered Fire Safety Insights from NASA/JAXA Microgravity Combustion Data (892 Validated Records • 30 Dataset Families • Hybrid RRF & ML Risk Engine)",
)

ready = health()
meta = get("/meta")
version_info = meta.get("version_info", {})

with st.sidebar:
    st.markdown("### 🛰️ System Telemetry")
    if ready.get("status") == "ready":
        mode_badge = "HTTP :8000" if ready.get("mode") == "http" else "Embedded Engine"
        st.success(f"Backend Ready ({mode_badge})")
    else:
        st.error("Backend Offline")

    sha = (version_info.get("parquet_sha256") or "unknown")[:8]
    st.caption(f"**Snapshot SHA-256:** `{sha}`")
    st.caption(f"**Total Records:** `{version_info.get('total_rows', 892)}`")
    st.caption(f"**Raw Rebuild:** `{version_info.get('raw_rebuild_rows', 450)}` rows")
    st.caption(f"**Legacy Canonical:** `{version_info.get('canonical_legacy_rows', 442)}` rows")
    st.divider()
    st.markdown(
        """
        **Navigation**
        - **1_Explorer**: Browse 892 experiments & 44 provenance columns
        - **2_Insights**: Ranked fire-safety findings & data audit
        - **3_Risk_Simulator**: Moon/Mars cabin flammability predictor
        - **4_Ask_the_Data**: Grounded Hybrid RAG + QueryPlan inspector
        """
    )

# Top KPI Strip (matching StatStrip.tsx)
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Total Experiments", f"{version_info.get('total_rows', 892)}", "44 validated columns")
c2.metric("Dataset Families", f"{len(meta.get('dataset_families', []))}", "35 investigations")
c3.metric(
    "Physical Spaceflight/Drop",
    f"{version_info.get('total_rows', 892) - meta.get('modeled_rows_count', 52)}",
    "is_modeled = False",
)
c4.metric(
    "Modeled Partial-g Rows",
    f"{meta.get('modeled_rows_count', 52)}",
    "Excluded by default",
    delta_color="off",
)
c5.metric(
    "Quarantined Airflow Rows",
    f"{version_info.get('flags', {}).get('AIRFLOW_QUARANTINED', 42)}",
    "BASS-II > 1000 cm/s",
    delta_color="off",
)

# Scientific Caveats & Limitations Banner (matching LimitationsBanner.tsx)
with st.expander("⚠️ Mandatory Scientific Caveats & Data Provenance Rules (Click to Inspect)", expanded=True):
    for lim in meta.get("data_limitations", []):
        st.markdown(f"- {lim}")

# Load parquet for overview visualizations
parquet_path = ROOT_DIR / "data" / "processed" / "experiments.parquet"
if parquet_path.exists():
    df = pd.read_parquet(parquet_path)
    col_left, col_right = st.columns([1.05, 0.95])
    with col_left:
        st.plotly_chart(atmosphere_envelope_chart(df), use_container_width=True)
    with col_right:
        st.plotly_chart(family_distribution_chart(df), use_container_width=True)

st.divider()
st.markdown(
    """
    ### Mission Context: Why Microgravity Changes Everything
    In freefall ($\\sim 0g$), buoyant convection vanishes. Hot combustion products no longer rise, turning candle-like flames into
    slow, spherical, blue diffusion-controlled flames (**FLEX**, **ACME**). Yet when gentle spacecraft cabin ventilation ($2\\text{–}15\\text{ cm/s}$)
    is present (**BASS**, **BASS-II**, **SOFIE**, **SAFFIRE I–VI**), fresh oxidizer is continuously delivered to the flame front without
    buoyant cooling—allowing materials that self-extinguish in Earth's $1g$ upward screening (**NASA-STD-6001**) to sustain dangerous flame spread,
    especially in elevated-oxygen lunar and Martian exploration atmospheres ($34\\%\\text{ O}_2, 56.5\\text{ kPa}$).
    """
)
#chahel panjikar contribution
