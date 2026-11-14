"""Golden Benchmark Evaluation Harness for Flame in Freefall.

Evaluates all 65 benchmark questions in `evaluation/golden_questions.yaml`:
- Questions q01–q38: Deterministic SQL lookup, aggregation, and explain_experiment.
- Questions q39–q44: Qualitative methodology / data-dictionary questions.
- Questions q45–q50: Out-of-scope / needs_expert abstention boundary questions.
- Questions q51–q65: Qualitative Hybrid RRF retrieval (BM25 + Dense SVD/TF-IDF),
  scoring Recall@5 and Recall@10 against `expected_experiment_ids`.

Usage:
    PYTHONPATH=src:. .venv/bin/python evaluation/run_eval.py
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import json
import math
from pathlib import Path
from typing import Any

import yaml

from flame.config import PROJECT_ROOT
from flame.llm.local_client import LocalHeuristicLLMClient
from flame.rag.planner import QueryPlanner
from flame.retrieval.fusion import fuse_retrieval
from flame.retrieval.semantic import SemanticRetriever
from flame.retrieval.store import ExperimentStore
from flame.schemas.query_plan import PlanIntent, QueryPlan

DEFAULT_PARQUET_PATH = PROJECT_ROOT / "data" / "processed" / "experiments.parquet"
GOLDEN_QUESTIONS_PATH = PROJECT_ROOT / "evaluation" / "golden_questions.yaml"
EXPECTED_ANSWERS_PATH = PROJECT_ROOT / "evaluation" / "expected_answers.yaml"
RESULTS_DIR = PROJECT_ROOT / "evaluation" / "results"


@dataclass
class QuestionResult:
    """Evaluation outcome for a single benchmark question."""

    id: str
    category: str
    intent: str
    question: str
    passed: bool
    plan_structural_match: bool = True
    plan_exact_match: bool = True
    expected_row_count: int = 0
    actual_row_count: int = 0
    recall_at_5: float | None = None
    recall_at_10: float | None = None
    errors: list[str] = field(default_factory=list)


def _float_close(a: Any, b: Any, abs_tol: float = 1e-4) -> bool:
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    try:
        return math.isclose(float(a), float(b), rel_tol=1e-4, abs_tol=abs_tol)
    except (TypeError, ValueError):
        return str(a) == str(b)


def _compare_aggregates(
    expected_aggs: list[dict[str, Any]],
    actual_aggs: list[Any],
) -> list[str]:
    errors: list[str] = []
    if len(expected_aggs) != len(actual_aggs):
        errors.append(
            f"Aggregate count mismatch: expected {len(expected_aggs)}, got {len(actual_aggs)}"
        )
        return errors

    for idx, (exp_a, act_obj) in enumerate(zip(expected_aggs, actual_aggs, strict=True)):
        act_a = act_obj.model_dump() if hasattr(act_obj, "model_dump") else dict(act_obj)
        for key in ("fn", "field", "n_used", "n_null_excluded", "n_quarantined_excluded", "group_key"):
            if key in exp_a and exp_a[key] != act_a.get(key):
                errors.append(
                    f"Aggregate[{idx}] '{key}' mismatch: expected {exp_a[key]!r}, got {act_a.get(key)!r}"
                )
        if "value" in exp_a and not _float_close(exp_a["value"], act_a.get("value")):
            errors.append(
                f"Aggregate[{idx}] value mismatch: expected {exp_a['value']}, got {act_a.get('value')}"
            )
    return errors


def _canonical_filter_set(plan: QueryPlan) -> set[tuple[str, str, str]]:
    out: set[tuple[str, str, str]] = set()
    for f in plan.filters:
        val_repr = (
            json.dumps(sorted(str(x) for x in f.value))
            if isinstance(f.value, (list, tuple, set))
            else json.dumps(f.value)
        )
        out.add((f.field, str(f.op.value), val_repr))
    return out


def _canonical_agg_set(plan: QueryPlan) -> set[tuple[str, str]]:
    return {(a.field, str(a.fn.value)) for a in plan.aggregates}


def compare_plans(expected_plan: QueryPlan, actual_plan: QueryPlan) -> tuple[bool, bool, list[str]]:
    diffs: list[str] = []
    structural_ok = True

    if expected_plan.intent != actual_plan.intent:
        structural_ok = False
        diffs.append(f"intent mismatch: expected={expected_plan.intent} actual={actual_plan.intent}")

    if expected_plan.include_modeled != actual_plan.include_modeled:
        structural_ok = False
        diffs.append(
            f"include_modeled mismatch: expected={expected_plan.include_modeled} actual={actual_plan.include_modeled}"
        )

    if set(expected_plan.group_by) != set(actual_plan.group_by):
        structural_ok = False
        diffs.append(
            f"group_by mismatch: expected={expected_plan.group_by} actual={actual_plan.group_by}"
        )

    if _canonical_agg_set(expected_plan) != _canonical_agg_set(actual_plan):
        structural_ok = False
        diffs.append("aggregates mismatch")

    exp_filters = _canonical_filter_set(expected_plan)
    act_filters = _canonical_filter_set(actual_plan)
    if exp_filters != act_filters:
        structural_ok = False
        diffs.append(f"filters mismatch: expected={sorted(exp_filters)} actual={sorted(act_filters)}")

    exact_ok = (
        structural_ok
        and expected_plan.group_by == actual_plan.group_by
        and expected_plan.sort == actual_plan.sort
        and expected_plan.limit == actual_plan.limit
    )
    return structural_ok, exact_ok, diffs


def evaluate_question(
    q: dict[str, Any],
    expected_entry: dict[str, Any],
    store: ExperimentStore,
    semantic_retriever: SemanticRetriever,
    planner: QueryPlanner | None = None,
) -> QuestionResult:
    qid = q["id"]
    category = q["category"]
    question_text = q["question"]
    golden_plan = QueryPlan.model_validate(q["plan"])

    if planner is not None:
        plan_res = planner.plan(question_text)
        plan = plan_res.plan
    else:
        plan = golden_plan

    structural_ok, exact_ok, _plan_diffs = compare_plans(golden_plan, plan)
    errors: list[str] = []

    # 1. Qualitative Hybrid RRF Evaluation (q39–q44 & q51–q65)
    if category == "qualitative":
        exp_ids = list(q.get("expected_experiment_ids") or [])
        fused = fuse_retrieval(
            question_text, plan, store, semantic_retriever=semantic_retriever
        )
        retrieved_ids = [str(r.get("experiment_id")) for r in fused.rows if r.get("experiment_id")]
        top5 = set(retrieved_ids[:5])
        top10 = set(retrieved_ids[:10])
        if exp_ids:
            r5 = round(sum(1 for eid in exp_ids if eid in top5) / len(exp_ids), 4)
            r10 = round(sum(1 for eid in exp_ids if eid in top10) / len(exp_ids), 4)
            if r10 < 1.0:
                missing = [eid for eid in exp_ids if eid not in top10]
                errors.append(f"Missing expected experiment_ids in Top-10 RRF: {missing}")
        else:
            # Methodology / data-dictionary qualitative questions (q39–q44)
            r5, r10 = 1.0, 1.0

        return QuestionResult(
            id=qid,
            category=category,
            intent=str(plan.intent.value),
            question=question_text,
            passed=(len(errors) == 0 and structural_ok),
            plan_structural_match=structural_ok,
            plan_exact_match=exact_ok,
            expected_row_count=len(exp_ids),
            actual_row_count=len(retrieved_ids),
            recall_at_5=r5,
            recall_at_10=r10,
            errors=errors,
        )

    # 2. Out-of-Scope / Needs-Expert Boundary Questions (q45–q50)
    if category == "out_of_scope" or plan.intent == PlanIntent.OUT_OF_SCOPE:
        res = store.execute_plan(plan)
        if plan.intent != PlanIntent.OUT_OF_SCOPE:
            errors.append(f"Expected out_of_scope intent, got {plan.intent.value}")
        if res.rows:
            errors.append(f"out_of_scope query returned {len(res.rows)} rows; expected 0")
        return QuestionResult(
            id=qid,
            category=category,
            intent=str(plan.intent.value),
            question=question_text,
            passed=len(errors) == 0,
            plan_structural_match=structural_ok,
            plan_exact_match=exact_ok,
            expected_row_count=0,
            actual_row_count=len(res.rows),
            errors=errors,
        )

    # 3. Deterministic Lookup / Explain / Aggregate (q01–q38)
    res = store.execute_plan(plan)

    if plan.intent in (PlanIntent.LOOKUP, PlanIntent.COMPARE, PlanIntent.EXPLAIN_EXPERIMENT):
        exp_ids = list(
            q.get("expected_experiment_ids")
            or expected_entry.get("expected_experiment_ids")
            or []
        )
        act_ids = [str(r.get("experiment_id")) for r in res.rows]
        if act_ids != exp_ids:
            exp_set = set(exp_ids)
            act_set = set(act_ids)
            missing = sorted(exp_set - act_set)[:5]
            extra = sorted(act_set - exp_set)[:5]
            errors.append(
                f"ID list mismatch: expected {len(exp_ids)} IDs, got {len(act_ids)}. "
                f"Missing(up to 5)={missing}, Extra(up to 5)={extra}"
            )
        if plan.intent == PlanIntent.EXPLAIN_EXPERIMENT and len(res.rows) == 1:
            exp_details = q.get("expected_details") or {}
            act_rec = res.rows[0]
            for key, exp_val in exp_details.items():
                act_val = act_rec.get(key)
                if isinstance(exp_val, float):
                    if not _float_close(exp_val, act_val):
                        errors.append(
                            f"explain_experiment '{key}' mismatch: expected {exp_val}, got {act_val}"
                        )
                elif isinstance(exp_val, list):
                    if sorted(str(x) for x in exp_val) != sorted(str(x) for x in (act_val or [])):
                        errors.append(
                            f"explain_experiment '{key}' list mismatch: expected {exp_val}, got {act_val}"
                        )
                elif exp_val != act_val:
                    errors.append(
                        f"explain_experiment '{key}' mismatch: expected {exp_val!r}, got {act_val!r}"
                    )
        return QuestionResult(
            id=qid,
            category=category,
            intent=str(plan.intent.value),
            question=question_text,
            passed=len(errors) == 0,
            plan_structural_match=structural_ok,
            plan_exact_match=exact_ok,
            expected_row_count=len(exp_ids),
            actual_row_count=len(act_ids),
            errors=errors,
        )

    if plan.intent == PlanIntent.AGGREGATE:
        exp_aggs = list(
            q.get("expected_aggregates")
            or expected_entry.get("expected_aggregates")
            or []
        )
        agg_errors = _compare_aggregates(exp_aggs, res.aggregates)
        errors.extend(agg_errors)
        return QuestionResult(
            id=qid,
            category=category,
            intent=str(plan.intent.value),
            question=question_text,
            passed=len(errors) == 0,
            plan_structural_match=structural_ok,
            plan_exact_match=exact_ok,
            expected_row_count=len(exp_aggs),
            actual_row_count=len(res.aggregates),
            errors=errors,
        )

    errors.append(f"Unsupported intent during evaluation: {plan.intent}")
    return QuestionResult(
        id=qid,
        category=category,
        intent=str(plan.intent.value),
        question=question_text,
        passed=False,
        plan_structural_match=structural_ok,
        plan_exact_match=exact_ok,
        errors=errors,
    )


def run_evaluation(
    parquet_path: Path = DEFAULT_PARQUET_PATH,
    questions_path: Path = GOLDEN_QUESTIONS_PATH,
    expected_path: Path = EXPECTED_ANSWERS_PATH,
    output_dir: Path = RESULTS_DIR,
    use_planner: bool = True,
) -> dict[str, Any]:
    """Run all 65 golden benchmark questions and write JSON + Markdown reports."""
    store = ExperimentStore(parquet_path=parquet_path)
    semantic_retriever = SemanticRetriever()
    planner = (
        QueryPlanner(llm_client=LocalHeuristicLLMClient(), store=store)
        if use_planner
        else None
    )

    questions_doc = yaml.safe_load(questions_path.read_text(encoding="utf-8"))
    expected_doc = yaml.safe_load(expected_path.read_text(encoding="utf-8"))

    questions_list: list[dict[str, Any]] = questions_doc.get("questions", [])
    expected_map: dict[str, dict[str, Any]] = (
        expected_doc.get("expected") or expected_doc.get("answers") or {}
    )

    det_results: list[QuestionResult] = []
    qual_results: list[QuestionResult] = []
    all_results: list[QuestionResult] = []

    for q in questions_list:
        qid = q["id"]
        exp_entry = expected_map.get(qid, {})
        q_res = evaluate_question(
            q, exp_entry, store, semantic_retriever=semantic_retriever, planner=planner
        )
        all_results.append(q_res)
        if q.get("category") == "qualitative" and q.get("expected_experiment_ids"):
            qual_results.append(q_res)
        else:
            det_results.append(q_res)

    det_total = len(det_results)
    det_passed = sum(1 for r in det_results if r.passed)
    det_pass_rate = round(det_passed / det_total, 4) if det_total else 0.0

    qual_total = len(qual_results)
    qual_passed = sum(1 for r in qual_results if r.passed)
    qual_r5 = (
        round(sum(r.recall_at_5 or 0.0 for r in qual_results) / qual_total, 4)
        if qual_total
        else 0.0
    )
    qual_r10 = (
        round(sum(r.recall_at_10 or 0.0 for r in qual_results) / qual_total, 4)
        if qual_total
        else 0.0
    )

    total_65 = len(all_results)
    passed_65 = sum(1 for r in all_results if r.passed)
    overall_pass_rate = round(passed_65 / total_65, 4) if total_65 else 0.0

    struct_match_count = sum(1 for r in all_results if r.plan_structural_match)
    exact_match_count = sum(1 for r in all_results if r.plan_exact_match)
    plan_structural_acc = round(struct_match_count / total_65, 4) if total_65 else 0.0
    plan_exact_acc = round(exact_match_count / total_65, 4) if total_65 else 0.0

    by_category: dict[str, dict[str, Any]] = {}
    for r in all_results:
        cat_stat = by_category.setdefault(
            r.category, {"total": 0, "passed": 0, "failed": 0, "pass_rate": 0.0}
        )
        cat_stat["total"] += 1
        if r.passed:
            cat_stat["passed"] += 1
        else:
            cat_stat["failed"] += 1
    for cat_stat in by_category.values():
        cat_stat["pass_rate"] = round(cat_stat["passed"] / max(cat_stat["total"], 1), 4)

    summary: dict[str, Any] = {
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "parquet_sha256": store.dataset_version.parquet_sha256,
        "planner_mode": "QueryPlanner (LocalHeuristicLLMClient)" if use_planner else "golden_reference",
        "total_questions_in_yaml": len(questions_list),
        "deterministic_evaluated": det_total,
        "deterministic_passed": det_passed,
        "deterministic_failed": det_total - det_passed,
        "deterministic_pass_rate": det_pass_rate,
        "qualitative_evaluated": qual_total,
        "qualitative_passed": qual_passed,
        "qualitative_recall_at_5": qual_r5,
        "qualitative_recall_at_10": qual_r10,
        "overall_evaluated": total_65,
        "overall_passed": passed_65,
        "overall_pass_rate": overall_pass_rate,
        "plan_structural_accuracy": plan_structural_acc,
        "plan_exact_match_accuracy": plan_exact_acc,
        "category_breakdown": by_category,
        "results": [asdict(r) for r in all_results],
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "latest.json"
    md_path = output_dir / "latest.md"

    json_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    md_path.write_text(_render_markdown_report(summary), encoding="utf-8")
    return summary


def _render_markdown_report(summary: dict[str, Any]) -> str:
    lines: list[str] = [
        "# Golden Benchmark Evaluation Report",
        "",
        f"- **Evaluated At:** `{summary['evaluated_at']}`",
        f"- **Snapshot SHA-256:** `{summary['parquet_sha256']}`",
        f"- **Planner Mode:** `{summary['planner_mode']}`",
        f"- **Overall 65-Question Score:** **{summary['overall_passed']} / {summary['overall_evaluated']}** (`{summary['overall_pass_rate'] * 100:.1f}%`)",
        f"- **Deterministic SQL & Boundary Pass Rate (50 Qs):** **{summary['deterministic_passed']} / {summary['deterministic_evaluated']}** (`{summary['deterministic_pass_rate'] * 100:.1f}%`)",
        f"- **Qualitative Hybrid RRF Recall@5 / Recall@10 (15 Qs):** `{summary['qualitative_recall_at_5'] * 100:.1f}%` / `{summary['qualitative_recall_at_10'] * 100:.1f}%`",
        f"- **Plan Structural Accuracy:** `{summary['plan_structural_accuracy'] * 100:.1f}%`",
        f"- **Plan Exact-Match Accuracy:** `{summary['plan_exact_match_accuracy'] * 100:.1f}%`",
        "",
        "## Category Breakdown",
        "",
        "| Category | Total | Passed | Failed | Pass Rate |",
        "| :--- | ---: | ---: | ---: | ---: |",
    ]
    for cat, stats in sorted(summary["category_breakdown"].items()):
        rate = stats["pass_rate"] * 100.0
        lines.append(
            f"| `{cat}` | {stats['total']} | {stats['passed']} | {stats['failed']} | {rate:.1f}% |"
        )

    lines.extend(
        [
            "",
            "## Question-by-Question Results (All 65 Golden Questions)",
            "",
            "| ID | Category | Intent | Status | Expected | Actual | Recall@10 | Notes |",
            "| :--- | :--- | :--- | :--- | ---: | ---: | :--- | :--- |",
        ]
    )
    for r in summary["results"]:
        status = "PASS" if r["passed"] else "FAIL"
        r10_str = f"{r['recall_at_10'] * 100:.0f}%" if r.get("recall_at_10") is not None else "N/A"
        err_note = "; ".join(r["errors"]) if r["errors"] else "OK"
        lines.append(
            f"| `{r['id']}` | `{r['category']}` | `{r['intent']}` | **{status}** | "
            f"{r['expected_row_count']} | {r['actual_row_count']} | {r10_str} | {err_note} |"
        )

    lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run golden benchmark evaluation.")
    parser.add_argument(
        "--golden-only",
        action="store_true",
        help="Use golden YAML plans directly instead of running QueryPlanner.",
    )
    args = parser.parse_args()
    summary = run_evaluation(use_planner=not args.golden_only)
    print(
        f"Evaluation complete: Overall {summary['overall_passed']}/{summary['overall_evaluated']} "
        f"({summary['overall_pass_rate'] * 100:.1f}%) | "
        f"Deterministic {summary['deterministic_passed']}/{summary['deterministic_evaluated']} | "
        f"Qualitative R@5={summary['qualitative_recall_at_5'] * 100:.1f}% R@10={summary['qualitative_recall_at_10'] * 100:.1f}%"
    )


if __name__ == "__main__":
    main()
