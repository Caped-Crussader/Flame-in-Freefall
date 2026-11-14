"""Page 2: Ranked Fire-Safety Insights, PSI Repository Catalog & Data Quality Audit."""
from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd
import streamlit as st

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR / "frontend") not in sys.path:
    sys.path.insert(0, str(ROOT_DIR / "frontend"))

from components.api_client import get  # noqa: E402
from components.charts import criticality_ranking_chart  # noqa: E402

st.set_page_config(page_title="Insights | Flame in Freefall", page_icon="📊", layout="wide")

st.title("📊 Ranked Fire-Safety Insights & Provenance Audit")
st.caption("Synthesized mission safety rankings across 30 dataset families, live NASA PSI catalog metadata, and data-quality quarantine audits.")

data = get("/insights/ranking")
findings = data.get("findings", [])
family_rankings = data.get("family_rankings", [])
psi_investigations = data.get("psi_investigations", [])

tab_findings, tab_families, tab_psi, tab_audit = st.tabs(
    [
        "🏆 Top 5 Ranked Fire-Safety Findings",
        "📈 Dataset Family Criticality Ranking",
        "🛰️ Live NASA PSI Combustion Catalog (26 Investigations)",
        "🛡️ Data Quality & Quarantine Audit",
    ]
)

with tab_findings:
    for item in findings:
        badge_color = "🔴" if item["severity"] == "CRITICAL" else "🟠" if item["severity"] == "HIGH" else "🟡"
        with st.container(border=True):
            st.markdown(
                f"#### #{item['rank']} {badge_color} [{item['severity']}] {item['title']} "
                f"— *Criticality Score: `{item['score']}/100`*"
            )
            st.markdown(item["summary"])
            st.info(f"**Actionable Spacecraft Design & Crew Recommendation:** {item['actionable_recommendation']}")
            st.caption(
                f"**Dataset Families:** `{', '.join(item['families'])}` | "
                f"**Key Citations:** `{', '.join(item['key_citations'])}`"
            )

with tab_families:
    if family_rankings:
        st.plotly_chart(criticality_ranking_chart(family_rankings), use_container_width=True)
        st.dataframe(pd.DataFrame(family_rankings), use_container_width=True, hide_index=True)

with tab_psi:
    st.markdown(
        "Fetched directly from **`https://psi.nasa.gov/geode-py/ws/repo/search?term=combustion`** "
        "using our verified TLS trust bundle (`certs/sslcom-tls-issuing-rsa-r1.pem`)."
    )
    if psi_investigations:
        psi_df = pd.DataFrame(psi_investigations)
        st.dataframe(
            psi_df[["accession", "acronym", "title", "sub_area", "platform", "hardware"]],
            use_container_width=True,
            hide_index=True,
        )
        sel_acc = st.selectbox("Inspect PSI Investigation Objectives", [p["accession"] for p in psi_investigations])
        match = next((p for p in psi_investigations if p["accession"] == sel_acc), None)
        if match:
            st.markdown(f"**{match['accession']} ({match['acronym']}) — {match['title']}**")
            st.write(match.get("objectives") or "No objective text listed.")

with tab_audit:
    st.markdown("### Deterministic Ingestion & Quarantine Summary")
    report_path = ROOT_DIR / "data" / "reports" / "quality_report.md"
    if report_path.exists():
        st.markdown(report_path.read_text(encoding="utf-8"))
