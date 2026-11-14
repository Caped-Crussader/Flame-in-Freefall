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
from components.theme import apply_flame_theme  # noqa: E402

st.set_page_config(page_title="Insights | Flame in Freefall", page_icon="📊", layout="wide")

apply_flame_theme(
    title="Ranked Fire-Safety Insights & Provenance Audit",
    subtitle="Synthesized mission safety rankings across 30 dataset families, historical spacecraft fire incidents, live NASA PSI catalog tables, and data-quality quarantine audits.",
    badge="MISSION SAFETY RANKINGS & LIVE NASA PSI CATALOG",
)

data = get("/insights/ranking")
findings = data.get("findings", [])
family_rankings = data.get("family_rankings", [])
psi_investigations = data.get("psi_investigations", [])
historical_incidents = data.get("historical_incidents", [])
psi_dossiers = data.get("psi_dossiers", [])
psi_experimental_tables = data.get("psi_experimental_tables", [])

tab_findings, tab_incidents, tab_families, tab_psi, tab_audit = st.tabs(
    [
        "🏆 Top 5 Ranked Fire-Safety Findings",
        "🚀 Historical Spacecraft Incidents vs. Data",
        "📈 Dataset Family Criticality Ranking",
        "🛰️ Live NASA PSI Catalog & Experimental Tables",
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

with tab_incidents:
    st.markdown(
        "### 🚀 Real Spacecraft Fire Incidents Mapped to Microgravity Experimental Data\n"
        "Connecting historical spaceflight emergencies highlighted in the **2026 NASA Space Apps Challenge Resources** "
        "directly to experimental combustion regimes in `data/processed/experiments.parquet`."
    )
    for inc in historical_incidents:
        sev_icon = "🔴" if inc["severity"] in ("CATASTROPHIC", "CRITICAL") else "🟠"
        with st.container(border=True):
            c_head, c_link = st.columns([4, 1])
            c_head.markdown(f"#### {sev_icon} {inc['name']} ({inc['date']})")
            c_link.link_button("🔗 Official NASA Reference", inc["official_nasa_url"], use_container_width=True)

            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Mission / Vehicle", inc["mission"])
            m2.metric("Oxygen Concentration", f"{inc['atmosphere_o2_pct']:.1f}% O₂")
            m3.metric("Ambient Pressure", f"{inc['pressure_kpa']:.1f} kPa")
            m4.metric("Gravity Regime", inc["gravity_regime"])

            st.markdown(f"**Ignition Source & Fuel Geometry:** {inc['ignition_source_and_fuel']}")
            st.markdown(f"**Incident Progression:** {inc['what_happened']}")
            st.success(f"**Microgravity Physics & Dataset Insight:** {inc['microgravity_physics_insight']}")
            st.caption(
                f"**Matched Dataset Families:** `{', '.join(inc['matched_dataset_families'])}` | "
                f"**Linked Experiment IDs:** `{', '.join(inc['matched_experiment_ids'])}`"
            )

with tab_families:
    if family_rankings:
        st.plotly_chart(criticality_ranking_chart(family_rankings), use_container_width=True)
        st.dataframe(pd.DataFrame(family_rankings), use_container_width=True, hide_index=True)

with tab_psi:
    st.markdown(
        "Fetched directly from **`https://psi.nasa.gov/geode-py/ws/repo/search?term=combustion`** "
        "and **`/geode-py/ws/studies/{accession}/download`** using our verified TLS trust bundle (`certs/sslcom-tls-issuing-rsa-r1.pem`)."
    )
    if psi_experimental_tables:
        st.subheader("🧪 Downloaded Live NASA PSI Experimental CSV Tables")
        tbl_labels = [
            f"{t['accession']} — {t['file_name']} ({t['row_count']} rows × {t['column_count']} cols)"
            for t in psi_experimental_tables
        ]
        sel_tbl_idx = st.selectbox(
            "Select a downloaded PSI Experimental Table to inspect",
            range(len(tbl_labels)),
            format_func=lambda i: tbl_labels[i],
        )
        chosen_tbl = psi_experimental_tables[sel_tbl_idx]
        st.caption(
            f"**Local Path:** `{chosen_tbl['relative_path']}` | "
            f"**Rows:** `{chosen_tbl['row_count']}` | "
            f"**Columns:** `{', '.join(chosen_tbl['columns'])}`"
        )
        st.dataframe(pd.DataFrame(chosen_tbl["preview_rows"]), use_container_width=True, hide_index=True)
        st.divider()

    if psi_dossiers:
        st.subheader("📑 Deep-Dive PSI Investigation Dossiers (DOI, PIs & Peer-Reviewed Publications)")
        for dos in psi_dossiers:
            with st.expander(
                f"🔬 {dos['accession']} ({dos['acronym']}) — {dos['title']} | DOI: {dos['doi'] or 'N/A'}",
                expanded=(dos["accession"] == "PSI-10"),
            ):
                d1, d2, d3, d4 = st.columns(4)
                d1.metric("Flight Program", dos["flight_program"] or "ISS")
                d2.metric("Hardware", dos["hardware"] or "CIR / MSG")
                d3.metric("Peer-Reviewed Papers", dos["publications_count"])
                d4.metric("Repository Files", dos["repo_files_count"])
                if dos["investigators"]:
                    st.markdown(f"**Principal & Co-Investigators:** {', '.join(dos['investigators'])}")
                if dos["experimental_table_files"]:
                    st.markdown(f"**Curated Experimental Tables:** `{', '.join(dos['experimental_table_files'])}`")
                if dos["top_publications"]:
                    st.markdown("**Selected Publications:**")
                    for pub in dos["top_publications"]:
                        doi_str = f" (DOI: `{pub['doi']}`)" if pub.get("doi") else ""
                        st.markdown(f"- *{pub['title']}* — {pub['authors']}{doi_str}")

    if psi_investigations:
        st.subheader("🛰️ Full 26-Investigation PSI Combustion Search Index")
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
