"""Page 4: Grounded Hybrid RAG Question Answering + Live 65-Question Golden Benchmark Scorecard."""
from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd
import streamlit as st
import yaml

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR / "frontend") not in sys.path:
    sys.path.insert(0, str(ROOT_DIR / "frontend"))

from components.api_client import get, post  # noqa: E402
from components.theme import apply_flame_theme  # noqa: E402

st.set_page_config(page_title="Ask the Data | Flame in Freefall", page_icon="💬", layout="wide")

apply_flame_theme(
    title="Ask the Data — Grounded Hybrid RAG & Benchmark Scorecard",
    subtitle="Every natural-language question compiles to a validated QueryPlan, runs against the 892-row snapshot (SQL + Hybrid SentenceTransformer/BM25 RRF), and verifies every citation via deterministic guardrails.",
    badge="GROUNDED HYBRID RAG • 65/65 GOLDEN BENCHMARK",
)

tab_qa, tab_eval = st.tabs(
    [
        "💬 Interactive Grounded Q&A & QueryPlan Inspector",
        "📊 Live 65-Question Golden Benchmark Scorecard",
    ]
)

with tab_qa:
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
        selected_opt = st.selectbox(
            "Select a Golden Question to Test", options, index=1 if len(options) > 1 else 0
        )
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

        # Grounded Answer Panel
        st.markdown("### 📝 Grounded Answer")
        with st.container(border=True):
            st.markdown(resp.get("answer_markdown") or "*No markdown answer produced.*")

        if citations:
            st.markdown("#### 🔗 Verified Experiment Citations")
            st.dataframe(pd.DataFrame(citations), use_container_width=True, hide_index=True)

        # Sub-tabs for PlanPanel, Aggregates, EvidenceTable, Limitations
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

with tab_eval:
    c_title, c_btn = st.columns([3, 1])
    c_title.markdown(
        "### 📊 Live 65-Question Golden Benchmark Scorecard\n"
        "Automated regression harness (`evaluation/run_eval.py`) verifying deterministic SQL lookup, "
        "exact null/quarantine-aware aggregation, `explain_experiment`, `out_of_scope` abstention, "
        "and Hybrid BM25 + Dense SVD/TF-IDF RRF Recall@5 / Recall@10."
    )
    if c_btn.button("🔄 Re-Run 65-Question Benchmark Suite", use_container_width=True):
        with st.spinner("Running all 65 golden benchmark questions against ExperimentStore + Hybrid RRF..."):
            eval_data = post("/evaluation/run", {})
        st.success("Fresh 65-question evaluation completed!")
    else:
        eval_data = get("/evaluation")

    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric(
        "Overall 65-Question Score",
        f"{eval_data.get('overall_passed', 0)} / {eval_data.get('overall_evaluated', 65)}",
        f"{eval_data.get('overall_pass_rate', 0.0) * 100:.1f}%",
    )
    k2.metric(
        "Deterministic & Boundary (50 Qs)",
        f"{eval_data.get('deterministic_passed', 0)} / {eval_data.get('deterministic_evaluated', 50)}",
        f"{eval_data.get('deterministic_pass_rate', 0.0) * 100:.1f}%",
    )
    k3.metric(
        "Qualitative Hybrid RRF Recall@10",
        f"{eval_data.get('qualitative_recall_at_10', 0.0) * 100:.1f}%",
        f"Recall@5: {eval_data.get('qualitative_recall_at_5', 0.0) * 100:.1f}%",
    )
    k4.metric(
        "Plan Structural Accuracy",
        f"{eval_data.get('plan_structural_accuracy', 0.0) * 100:.1f}%",
    )
    k5.metric(
        "Plan Exact-Match Accuracy",
        f"{eval_data.get('plan_exact_match_accuracy', 0.0) * 100:.1f}%",
    )

    st.caption(
        f"**Evaluated At:** `{eval_data.get('evaluated_at', 'N/A')}` | "
        f"**Snapshot SHA-256:** `{eval_data.get('parquet_sha256', 'N/A')[:16]}...` | "
        f"**Planner Mode:** `{eval_data.get('planner_mode', 'N/A')}`"
    )

    cat_breakdown = eval_data.get("category_breakdown", {})
    if cat_breakdown:
        st.markdown("#### 📂 Category Performance Breakdown")
        cat_rows = [
            {
                "Category": cat,
                "Total Questions": stats.get("total", 0),
                "Passed": stats.get("passed", 0),
                "Failed": stats.get("failed", 0),
                "Pass Rate (%)": round(stats.get("pass_rate", 0.0) * 100.0, 1),
            }
            for cat, stats in sorted(cat_breakdown.items())
        ]
        st.dataframe(pd.DataFrame(cat_rows), use_container_width=True, hide_index=True)

    q_results = eval_data.get("results", [])
    if q_results:
        st.markdown("#### 🔍 Question-by-Question Audit Log (q01–q65)")
        q_df = pd.DataFrame(q_results)
        st.dataframe(
            q_df[
                [
                    "id",
                    "category",
                    "intent",
                    "passed",
                    "plan_structural_match",
                    "expected_row_count",
                    "actual_row_count",
                    "recall_at_5",
                    "recall_at_10",
                    "question",
                ]
            ],
            use_container_width=True,
            height=480,
            hide_index=True,
        )
