"""Page 4: Grounded Hybrid RAG Question Answering + QueryPlan & Evidence Inspector."""
from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd
import streamlit as st
import yaml

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR / "frontend") not in sys.path:
    sys.path.insert(0, str(ROOT_DIR / "frontend"))

from components.api_client import post  # noqa: E402

st.set_page_config(page_title="Ask the Data | Flame in Freefall", page_icon="💬", layout="wide")

st.title("💬 Ask the Data — Grounded Hybrid RAG")
st.caption(
    "Every natural-language question compiles to a validated `QueryPlan`, runs against the 892-row snapshot "
    "(SQL + Hybrid BM25/Dense RRF for qualitative queries), and verifies every citation and number via deterministic guardrails."
)

# Load 65 benchmark questions from evaluation/golden_questions.yaml
golden_path = ROOT_DIR / "evaluation" / "golden_questions.yaml"
benchmark_questions: list[dict] = []
if golden_path.exists():
    try:
        gdata = yaml.safe_load(golden_path.read_text(encoding="utf-8")) or {}
        benchmark_questions = gdata.get("questions", [])
    except Exception:
        pass

with st.container(border=True):
    st.markdown("##### Benchmark Question Library (65 Hand-Verified Golden Questions) or Custom Query")
    options = ["(Type a custom question below)"] + [
        f"[{q.get('id')}] ({q.get('category')}) {q.get('question')}" for q in benchmark_questions
    ]
    selected_opt = st.selectbox("Select a Golden Question to Test", options, index=1 if len(options) > 1 else 0)
    default_q = ""
    if selected_opt != "(Type a custom question below)":
        idx = options.index(selected_opt) - 1
        default_q = benchmark_questions[idx].get("question", "")

    user_q = st.text_input(
        "Question",
        value=default_q,
        placeholder="e.g. Which experiments studied radiative cool flames around 740 K?",
    )
    run_btn = st.button("🚀 Run Grounded Query Pipeline", type="primary")

if run_btn and user_q.strip():
    with st.spinner("Planning QueryPlan -> Executing Structured/Hybrid Retrieval -> Verifying Guardrails..."):
        resp = post("/ask", {"question": user_q.strip()})

    status = resp.get("status", "unknown")
    timings = resp.get("timings", {})
    citations = resp.get("citations", [])
    evidence = resp.get("evidence", [])
    aggregates = resp.get("aggregates", [])
    plan = resp.get("plan", {})
    limitations = resp.get("limitations", [])
    warnings = resp.get("warnings", [])

    # Status strip
    s1, s2, s3, s4, s5 = st.columns(5)
    s1.metric("Pipeline Status", status.upper())
    s2.metric("Plan Intent", str(plan.get("intent", "n/a")).upper())
    s3.metric("Verified Citations", len(citations))
    s4.metric("Evidence Rows", len(evidence))
    s5.metric("Total Latency", f"{timings.get('total_s', 0.0) * 1000:.1f} ms")

    # Grounded Answer Panel (matching AnswerPanel.tsx)
    st.markdown("### 📝 Grounded Answer")
    with st.container(border=True):
        st.markdown(resp.get("answer_markdown") or "*No markdown answer produced.*")

    if citations:
        st.markdown("#### 🔗 Verified Experiment Citations")
        st.dataframe(pd.DataFrame(citations), use_container_width=True, hide_index=True)

    # Tabs for PlanPanel, Aggregates, EvidenceTable, Limitations
    t_plan, t_ev, t_agg, t_lim = st.tabs(
        [
            "🧭 Compiled QueryPlan Inspector",
            f"📋 Retrieved Evidence Table ({len(evidence)} rows)",
            f"🔢 Computed Aggregates ({len(aggregates)})",
            f"⚠️ Guardrail Caveats & Warnings ({len(limitations) + len(warnings)})",
        ]
    )

    with t_plan:
        st.json(plan)

    with t_ev:
        if evidence:
            st.dataframe(pd.DataFrame(evidence), use_container_width=True, height=420, hide_index=True)
        else:
            st.info("No individual evidence rows returned for this query.")

    with t_agg:
        if aggregates:
            st.dataframe(pd.DataFrame(aggregates), use_container_width=True, hide_index=True)
        else:
            st.info("No SQL aggregates computed for this intent.")

    with t_lim:
        if limitations:
            st.markdown("**Mandatory Scientific Limitations:**")
            for lim in limitations:
                st.markdown(f"- {lim}")
        if warnings:
            st.markdown("**Pipeline & Guardrail Warnings:**")
            for w in warnings:
                st.warning(w)
