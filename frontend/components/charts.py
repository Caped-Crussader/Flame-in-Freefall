"""Reusable Plotly charts (flame spread vs O2, pressure maps, etc.)."""
import plotly.express as px


def spread_vs_oxygen(df):
    return px.scatter(df, x="oxygen_pct", y="flame_spread_rate", color="fuel", hover_name="name")
