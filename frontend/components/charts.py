"""Reusable Plotly visualizations for microgravity combustion datasets."""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go


def atmosphere_envelope_chart(df: pd.DataFrame) -> go.Figure:
    """Plot Oxygen % vs Pressure (kPa) across NASA/JAXA experiments with reference habitat regimes."""
    plot_df = df.dropna(subset=["oxygen_pct", "pressure_kpa"]).copy()
    fig = px.scatter(
        plot_df,
        x="pressure_kpa",
        y="oxygen_pct",
        color="dataset_family",
        symbol="is_modeled",
        hover_name="experiment_id",
        hover_data=["fuel_material", "extinction_outcome", "burning_rate_mms", "airflow_velocity_cms"],
        labels={
            "pressure_kpa": "Cabin / Chamber Pressure (kPa)",
            "oxygen_pct": "Oxygen Concentration (% O₂)",
            "dataset_family": "Dataset Family",
            "is_modeled": "Modeled Row",
        },
        title="Spacecraft Atmosphere Envelope: Oxygen (%) vs. Pressure (kPa)",
        height=460,
    )
    # Add reference annotations for ISS and Artemis Lunar Exploration Atmosphere
    fig.add_hline(y=21.0, line_dash="dot", line_color="#60a5fa", annotation_text="ISS / Earth (21% O₂)")
    fig.add_hline(y=34.0, line_dash="dash", line_color="#f97316", annotation_text="Artemis Exploration (34% O₂)")
    fig.add_vline(x=56.5, line_dash="dash", line_color="#f97316", annotation_text="56.5 kPa (8.2 psia)")
    fig.update_layout(template="plotly_dark", margin=dict(l=20, r=20, t=50, b=20))
    return fig


def family_distribution_chart(df: pd.DataFrame) -> go.Figure:
    """Horizontal bar chart of experiment counts by dataset family and record source."""
    counts = (
        df.groupby(["dataset_family", "record_source"], as_index=False)
        .size()
        .rename(columns={"size": "count"})
        .sort_values("count", ascending=True)
    )
    fig = px.bar(
        counts,
        x="count",
        y="dataset_family",
        color="record_source",
        orientation="h",
        labels={
            "count": "Number of Experiments",
            "dataset_family": "Dataset Family",
            "record_source": "Provenance Source",
        },
        title="892 Experiments Across 30 NASA/JAXA Dataset Families",
        color_discrete_map={"raw_rebuild": "#38bdf8", "canonical_legacy": "#a78bfa"},
        height=560,
    )
    fig.update_layout(template="plotly_dark", margin=dict(l=20, r=20, t=50, b=20))
    return fig


def spread_vs_oxygen_chart(df: pd.DataFrame) -> go.Figure:
    """Plot Burning / Spread Rate (mm/s) vs Oxygen (%) colored by Dataset Family."""
    sub = df.dropna(subset=["oxygen_pct", "burning_rate_mms"]).copy()
    sub = sub[sub["burning_rate_mms"] > 0]
    fig = px.scatter(
        sub,
        x="oxygen_pct",
        y="burning_rate_mms",
        color="dataset_family",
        hover_name="experiment_id",
        hover_data=["fuel_material", "pressure_kpa", "airflow_velocity_cms", "extinction_outcome"],
        labels={
            "oxygen_pct": "Oxygen Concentration (% O₂)",
            "burning_rate_mms": "Reported Burning / Spread Rate (mm/s)",
            "dataset_family": "Dataset Family",
        },
        title="Burning / Spread Rate vs. Oxygen Concentration (Note: Semantics Vary by Family)",
        height=440,
    )
    fig.update_layout(template="plotly_dark", margin=dict(l=20, r=20, t=50, b=20))
    return fig


def criticality_ranking_chart(rankings: list[dict]) -> go.Figure:
    """Bar chart of family fire-safety criticality scores."""
    rdf = pd.DataFrame(rankings).head(15).sort_values("criticality_score", ascending=True)
    fig = px.bar(
        rdf,
        x="criticality_score",
        y="dataset_family",
        color="sustained_burn_rate_pct",
        orientation="h",
        hover_data=["experiments_count", "max_oxygen_pct", "min_pressure_kpa"],
        labels={
            "criticality_score": "Fire-Safety Criticality Index (0–100)",
            "dataset_family": "Dataset Family",
            "sustained_burn_rate_pct": "Sustained Burn (%)",
        },
        title="Top 15 Dataset Families by Spacecraft Fire-Safety Criticality",
        color_continuous_scale="YlOrRd",
        height=460,
    )
    fig.update_layout(template="plotly_dark", margin=dict(l=20, r=20, t=50, b=20))
    return fig
