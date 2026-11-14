"""Page 1: Dataset & Provenance Explorer (with Modeled Toggle & 44-Column Detail Drawer)."""
from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd
import streamlit as st

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR / "frontend") not in sys.path:
    sys.path.insert(0, str(ROOT_DIR / "frontend"))

from components.api_client import get  # noqa: E402
from components.charts import (  # noqa: E402
    atmosphere_envelope_chart,
    spread_vs_oxygen_chart,
)

st.set_page_config(page_title="Explorer | Flame in Freefall", page_icon="🔎", layout="wide")

st.title("🔎 Experiment & Provenance Explorer")
st.caption("Filter all 892 NASA/JAXA combustion records, inspect data-quality flags, and trace raw source rows.")

parquet_path = ROOT_DIR / "data" / "processed" / "experiments.parquet"
df = pd.read_parquet(parquet_path)

# Top Filter Bar
with st.container():
    f1, f2, f3, f4 = st.columns([1.4, 1.4, 1.2, 1.0])
    families = ["All"] + sorted(df["dataset_family"].dropna().unique().tolist())
    sel_family = f1.selectbox("Dataset Family (30)", families, index=0)

    sub_for_mat = df if sel_family == "All" else df[df["dataset_family"] == sel_family]
    materials = ["All"] + sorted(sub_for_mat["fuel_material"].dropna().unique().tolist())
    sel_material = f2.selectbox("Fuel / Specimen Material", materials, index=0)

    gravities = ["All"] + sorted(df["gravity_condition"].dropna().unique().tolist())
    sel_gravity = f3.selectbox("Gravity Condition", gravities, index=0)

    include_modeled = f4.toggle(
        "Include Modeled Rows (52)",
        value=False,
        help="When off (default), excludes the 50 Partial-g Bounded and 2 LUCI/FM2 engineering model rows.",
    )

    s1, s2, s3 = st.columns([1.4, 1.4, 1.2])
    o2_min, o2_max = float(df["oxygen_pct"].min()), float(df["oxygen_pct"].max())
    sel_o2 = s1.slider("Oxygen Range (% O₂)", o2_min, o2_max, (o2_min, o2_max))

    p_min, p_max = float(df["pressure_kpa"].min()), float(df["pressure_kpa"].max())
    sel_p = s2.slider("Pressure Range (kPa)", p_min, p_max, (p_min, p_max))

    search_text = s3.text_input("Search ID / Notes / Description", placeholder="e.g. cool flame, BASS-B1, water mist")

# Apply filters
filtered = df.copy()
if not include_modeled:
    filtered = filtered[~filtered["is_modeled"]]
if sel_family != "All":
    filtered = filtered[filtered["dataset_family"] == sel_family]
if sel_material != "All":
    filtered = filtered[filtered["fuel_material"] == sel_material]
if sel_gravity != "All":
    filtered = filtered[filtered["gravity_condition"] == sel_gravity]

filtered = filtered[
    (filtered["oxygen_pct"].isna() | filtered["oxygen_pct"].between(sel_o2[0], sel_o2[1]))
    & (filtered["pressure_kpa"].isna() | filtered["pressure_kpa"].between(sel_p[0], sel_p[1]))
]

if search_text.strip():
    q = search_text.strip().lower()
    mask = (
        filtered["experiment_id"].astype(str).str.lower().str.contains(q, na=False)
        | filtered["notes"].astype(str).str.lower().str.contains(q, na=False)
        | filtered["sample_description"].astype(str).str.lower().str.contains(q, na=False)
        | filtered["extinction_outcome"].astype(str).str.lower().str.contains(q, na=False)
    )
    filtered = filtered[mask]

st.markdown(f"**Showing `{len(filtered)}` matching experiments** (of `{len(df)}` total)")

# Interactive Plots
tab_table, tab_charts, tab_detail = st.tabs(
    ["📋 Experiment Table", "📈 Interactive Charts", "🔬 Single-Record Provenance Inspector (44 Columns)"]
)

display_cols = [
    "experiment_id",
    "dataset_family",
    "investigation_id",
    "fuel_material",
    "oxygen_pct",
    "pressure_kpa",
    "airflow_velocity_cms",
    "burning_rate_mms",
    "flame_temp_k",
    "burn_time_s",
    "extinction_outcome",
    "gravity_condition",
    "is_modeled",
    "record_source",
]

with tab_table:
    st.dataframe(
        filtered[display_cols],
        use_container_width=True,
        height=460,
        hide_index=True,
    )

with tab_charts:
    c_left, c_right = st.columns(2)
    with c_left:
        st.plotly_chart(atmosphere_envelope_chart(filtered), use_container_width=True)
    with c_right:
        st.plotly_chart(spread_vs_oxygen_chart(filtered), use_container_width=True)

with tab_detail:
    exp_ids = filtered["experiment_id"].tolist()
    if not exp_ids:
        st.warning("No experiments match the current filters.")
    else:
        sel_exp_id = st.selectbox("Select Experiment ID to Inspect Full Provenance & Raw Fields", exp_ids, index=0)
        record = get(f"/experiments/{sel_exp_id}")
        if record and "experiment_id" in record:
            d1, d2, d3 = st.columns(3)
            d1.metric("Experiment ID", record["experiment_id"], record.get("dataset_family"))
            d2.metric(
                "Atmosphere",
                f"{record.get('oxygen_pct')}% O₂ @ {record.get('pressure_kpa')} kPa",
                f"Airflow: {record.get('airflow_velocity_cms')} cm/s",
            )
            d3.metric(
                "Outcome",
                str(record.get("extinction_outcome")),
                "MODELED" if record.get("is_modeled") else f"Source: {record.get('record_source')}",
            )

            flags = record.get("data_quality_flags") or []
            if flags:
                st.warning(f"**Data Quality Flags Fired:** `{', '.join(flags)}`")
            else:
                st.success("**Data Quality Flags:** None (Clean Record)")

            st.markdown(f"**Sample Description:** {record.get('sample_description')}")
            st.markdown(f"**Experiment Notes:** {record.get('notes')}")
            st.markdown(
                f"**Provenance Trace:** File `{record.get('source_file')}` (Row `{record.get('source_row')}`) "
                f"| Hardware: `{record.get('facility_hardware')}` | [Source URL]({record.get('source_url')})"
            )
            with st.expander("Full 44-Column JSON Record"):
                st.json(record)
