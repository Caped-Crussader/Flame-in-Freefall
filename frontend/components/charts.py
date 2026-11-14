"""Reusable Plotly visualizations for microgravity combustion datasets."""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go


def _style_glass_figure(fig: go.Figure, **extra_layout: object) -> go.Figure:
    """Apply translucent glassmorphic dark styling so the animated flame background shines through."""
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(11, 16, 32, 0.62)",
        plot_bgcolor="rgba(6, 10, 22, 0.48)",
        font=dict(family="Inter, sans-serif", color="#e2e8f0"),
        xaxis=dict(gridcolor="rgba(148, 163, 184, 0.12)", zerolinecolor="rgba(148, 163, 184, 0.18)"),
        yaxis=dict(gridcolor="rgba(148, 163, 184, 0.12)", zerolinecolor="rgba(148, 163, 184, 0.18)"),
        **extra_layout,
    )
    return fig


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
    fig.add_hline(y=21.0, line_dash="dot", line_color="#60a5fa", annotation_text="ISS / Earth (21% O₂)")
    fig.add_hline(y=34.0, line_dash="dash", line_color="#f97316", annotation_text="Artemis Exploration (34% O₂)")
    fig.add_vline(x=56.5, line_dash="dash", line_color="#f97316", annotation_text="56.5 kPa (8.2 psia)")
    return _style_glass_figure(fig, margin=dict(l=20, r=20, t=50, b=20))


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
    return _style_glass_figure(fig, margin=dict(l=20, r=20, t=50, b=20))


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
    return _style_glass_figure(fig, margin=dict(l=20, r=20, t=50, b=20))


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
    return _style_glass_figure(fig, margin=dict(l=20, r=20, t=50, b=20))


def flammability_moc_contour_chart(
    envelope: dict,
    current_o2: float,
    current_kpa: float,
    material: str,
    airflow: float,
) -> go.Figure:
    """2D Flammability Risk Contour Map (Oxygen % vs Pressure kPa) with 0g & 1g MOC boundary curves."""
    p_grid = envelope.get("pressure_grid_kpa", [])
    o2_grid = envelope.get("oxygen_grid_pct", [])
    z_mat = envelope.get("risk_matrix", [])
    moc_0g = envelope.get("moc_0g_o2_pct", [])
    moc_1g = envelope.get("moc_1g_std6001_o2_pct", [])
    exp_pts = envelope.get("material_experiments", [])

    fig = go.Figure()

    # 1. 2D Flammability Risk Contour
    fig.add_trace(
        go.Contour(
            x=p_grid,
            y=o2_grid,
            z=z_mat,
            colorscale="YlOrRd",
            zmin=0.0,
            zmax=1.0,
            contours=dict(
                coloring="heatmap",
                showlabels=True,
                labelfont=dict(size=11, color="white"),
            ),
            colorbar=dict(title="Risk Score"),
            hovertemplate="Pressure: %{x:.1f} kPa<br>O₂: %{y:.1f}%<br>Risk Score: %{z:.2f}<extra></extra>",
            name="Flammability Risk",
        )
    )

    # 2. Microgravity 0g MOC Boundary Curve
    if p_grid and moc_0g:
        fig.add_trace(
            go.Scatter(
                x=p_grid,
                y=moc_0g,
                mode="lines+markers",
                line=dict(color="#38bdf8", width=3.5),
                marker=dict(size=5, color="#38bdf8"),
                name="0g Microgravity MOC Boundary (BASS-II / SOFIE)",
                hovertemplate="Pressure: %{x:.1f} kPa<br>0g MOC Limit: %{y:.1f}% O₂<extra></extra>",
            )
        )

    # 3. 1g NASA-STD-6001 MOC Screening Curve
    if p_grid and moc_1g:
        fig.add_trace(
            go.Scatter(
                x=p_grid,
                y=moc_1g,
                mode="lines",
                line=dict(color="#4ade80", width=2.5, dash="dash"),
                name="1g NASA-STD-6001 Upward Screening MOC",
                hovertemplate="Pressure: %{x:.1f} kPa<br>1g STD-6001 MOC: %{y:.1f}% O₂<extra></extra>",
            )
        )

    # 4. Historical Experimental Data Points Overlay
    if exp_pts:
        sustained_pts = [p for p in exp_pts if p.get("sustained")]
        quenched_pts = [p for p in exp_pts if not p.get("sustained")]
        if sustained_pts:
            fig.add_trace(
                go.Scatter(
                    x=[p["pressure_kpa"] for p in sustained_pts],
                    y=[p["oxygen_pct"] for p in sustained_pts],
                    mode="markers",
                    marker=dict(
                        symbol="circle",
                        size=8,
                        color="#ef4444",
                        line=dict(width=1.2, color="white"),
                    ),
                    text=[
                        f"{p['experiment_id']} ({p['dataset_family']}) — {p['extinction_outcome']}"
                        for p in sustained_pts
                    ],
                    hovertemplate="%{text}<br>P=%{x:.1f} kPa, O₂=%{y:.1f}%<extra></extra>",
                    name="Sustained Burn (Flight/Drop Tests)",
                )
            )
        if quenched_pts:
            fig.add_trace(
                go.Scatter(
                    x=[p["pressure_kpa"] for p in quenched_pts],
                    y=[p["oxygen_pct"] for p in quenched_pts],
                    mode="markers",
                    marker=dict(
                        symbol="x",
                        size=8,
                        color="#22c55e",
                        line=dict(width=1.2, color="white"),
                    ),
                    text=[
                        f"{p['experiment_id']} ({p['dataset_family']}) — {p['extinction_outcome']}"
                        for p in quenched_pts
                    ],
                    hovertemplate="%{text}<br>P=%{x:.1f} kPa, O₂=%{y:.1f}%<extra></extra>",
                    name="Quenched / Self-Extinguished Tests",
                )
            )

    # 5. Reference Spacecraft Regimes & User's Selected Operating Point
    fig.add_trace(
        go.Scatter(
            x=[101.3, 70.3, 56.5],
            y=[21.0, 26.5, 34.0],
            mode="markers+text",
            marker=dict(symbol="diamond", size=11, color="#e2e8f0", line=dict(width=1.5, color="#0f172a")),
            text=["ISS (21% O₂)", "EVA Pre-Breathe (26.5%)", "Artemis SEA (34% O₂)"],
            textposition="top center",
            textfont=dict(color="white", size=11),
            name="Reference Mission Regimes",
        )
    )

    fig.add_trace(
        go.Scatter(
            x=[current_kpa],
            y=[current_o2],
            mode="markers+text",
            marker=dict(
                symbol="star",
                size=17,
                color="#facc15",
                line=dict(width=2, color="black"),
            ),
            text=["Selected Point"],
            textposition="bottom center",
            textfont=dict(color="#facc15", size=12),
            name=f"Selected ({current_o2:.1f}% O₂, {current_kpa:.1f} kPa)",
        )
    )

    return _style_glass_figure(
        fig,
        title=f"2D Flammability Envelope & MOC Boundary — {material} @ {airflow:.1f} cm/s Flow",
        xaxis_title="Cabin / Chamber Pressure (kPa)",
        yaxis_title="Oxygen Concentration (% O₂)",
        height=500,
        legend=dict(orientation="h", yanchor="bottom", y=-0.28, xanchor="center", x=0.5),
        margin=dict(l=20, r=20, t=55, b=90),
    )


def airflow_quenching_contour_chart(
    envelope: dict,
    current_o2: float,
    current_flow: float,
    material: str,
    pressure: float,
) -> go.Figure:
    """2D Ventilation Quenching & Blowoff Contour Map (Oxygen % vs Airflow Velocity cm/s)."""
    flow_grid = envelope.get("airflow_grid_cms", [])
    o2_grid = envelope.get("oxygen_grid_pct", [])
    z_af = envelope.get("airflow_risk_matrix", [])

    fig = go.Figure()
    fig.add_trace(
        go.Contour(
            x=flow_grid,
            y=o2_grid,
            z=z_af,
            colorscale="YlOrRd",
            zmin=0.0,
            zmax=1.0,
            contours=dict(
                coloring="heatmap",
                showlabels=True,
                labelfont=dict(size=11, color="white"),
            ),
            colorbar=dict(title="Risk Score"),
            hovertemplate="Airflow: %{x:.1f} cm/s<br>O₂: %{y:.1f}%<br>Risk Score: %{z:.2f}<extra></extra>",
            name="Ventilation Risk",
        )
    )

    fig.add_vline(
        x=1.5,
        line_dash="dot",
        line_color="#38bdf8",
        annotation_text="Diffusive Quenching (<1.5 cm/s, Fans Off)",
        annotation_position="top left",
    )
    fig.add_vline(
        x=32.0,
        line_dash="dash",
        line_color="#a78bfa",
        annotation_text="High-Flow Blowoff (>32 cm/s)",
        annotation_position="top right",
    )

    fig.add_trace(
        go.Scatter(
            x=[current_flow],
            y=[current_o2],
            mode="markers+text",
            marker=dict(symbol="star", size=17, color="#facc15", line=dict(width=2, color="black")),
            text=["Selected Flow"],
            textposition="bottom center",
            textfont=dict(color="#facc15", size=12),
            name=f"Selected ({current_flow:.1f} cm/s, {current_o2:.1f}% O₂)",
        )
    )

    return _style_glass_figure(
        fig,
        title=f"Microgravity Ventilation Quenching & Blowoff Map — {material} @ {pressure:.1f} kPa",
        xaxis_title="Forced HVAC / Ventilation Airflow Velocity (cm/s)",
        yaxis_title="Oxygen Concentration (% O₂)",
        height=500,
        legend=dict(orientation="h", yanchor="bottom", y=-0.25, xanchor="center", x=0.5),
        margin=dict(l=20, r=20, t=55, b=80),
    )
