# Golden Benchmark Evaluation Report

- **Evaluated At:** `2026-11-14T10:58:42.204405+00:00`
- **Snapshot SHA-256:** `4b3139dc07546aa01ab89b3a0b02411a25c02be681275b9619bda57aba7b33cf`
- **Planner Mode:** `QueryPlanner (LocalHeuristicLLMClient)`
- **Overall 65-Question Score:** **65 / 65** (`100.0%`)
- **Deterministic SQL & Boundary Pass Rate (50 Qs):** **50 / 50** (`100.0%`)
- **Qualitative Hybrid RRF Recall@5 / Recall@10 (15 Qs):** `97.8%` / `100.0%`
- **Plan Structural Accuracy:** `100.0%`
- **Plan Exact-Match Accuracy:** `100.0%`

## Category Breakdown

| Category | Total | Passed | Failed | Pass Rate |
| :--- | ---: | ---: | ---: | ---: |
| `aggregation` | 15 | 15 | 0 | 100.0% |
| `explain_experiment` | 8 | 8 | 0 | 100.0% |
| `lookup` | 15 | 15 | 0 | 100.0% |
| `out_of_scope` | 6 | 6 | 0 | 100.0% |
| `qualitative` | 21 | 21 | 0 | 100.0% |

## Question-by-Question Results (All 65 Golden Questions)

| ID | Category | Intent | Status | Expected | Actual | Recall@10 | Notes |
| :--- | :--- | :--- | :--- | ---: | ---: | :--- | :--- |
| `q01` | `lookup` | `lookup` | **PASS** | 157 | 157 | N/A | OK |
| `q02` | `lookup` | `lookup` | **PASS** | 59 | 59 | N/A | OK |
| `q03` | `lookup` | `lookup` | **PASS** | 8 | 8 | N/A | OK |
| `q04` | `lookup` | `lookup` | **PASS** | 61 | 61 | N/A | OK |
| `q05` | `lookup` | `lookup` | **PASS** | 23 | 23 | N/A | OK |
| `q06` | `lookup` | `lookup` | **PASS** | 42 | 42 | N/A | OK |
| `q07` | `lookup` | `lookup` | **PASS** | 88 | 88 | N/A | OK |
| `q08` | `lookup` | `lookup` | **PASS** | 186 | 186 | N/A | OK |
| `q09` | `lookup` | `lookup` | **PASS** | 18 | 18 | N/A | OK |
| `q10` | `lookup` | `lookup` | **PASS** | 42 | 42 | N/A | OK |
| `q11` | `lookup` | `lookup` | **PASS** | 145 | 145 | N/A | OK |
| `q12` | `lookup` | `lookup` | **PASS** | 463 | 463 | N/A | OK |
| `q13` | `lookup` | `lookup` | **PASS** | 1 | 1 | N/A | OK |
| `q14` | `lookup` | `lookup` | **PASS** | 52 | 52 | N/A | OK |
| `q15` | `lookup` | `lookup` | **PASS** | 12 | 12 | N/A | OK |
| `q16` | `aggregation` | `aggregate` | **PASS** | 1 | 1 | N/A | OK |
| `q17` | `aggregation` | `aggregate` | **PASS** | 1 | 1 | N/A | OK |
| `q18` | `aggregation` | `aggregate` | **PASS** | 1 | 1 | N/A | OK |
| `q19` | `aggregation` | `aggregate` | **PASS** | 1 | 1 | N/A | OK |
| `q20` | `aggregation` | `aggregate` | **PASS** | 1 | 1 | N/A | OK |
| `q21` | `aggregation` | `aggregate` | **PASS** | 1 | 1 | N/A | OK |
| `q22` | `aggregation` | `aggregate` | **PASS** | 1 | 1 | N/A | OK |
| `q23` | `aggregation` | `aggregate` | **PASS** | 1 | 1 | N/A | OK |
| `q24` | `aggregation` | `aggregate` | **PASS** | 1 | 1 | N/A | OK |
| `q25` | `aggregation` | `aggregate` | **PASS** | 1 | 1 | N/A | OK |
| `q26` | `aggregation` | `aggregate` | **PASS** | 1 | 1 | N/A | OK |
| `q27` | `aggregation` | `aggregate` | **PASS** | 1 | 1 | N/A | OK |
| `q28` | `aggregation` | `aggregate` | **PASS** | 1 | 1 | N/A | OK |
| `q29` | `aggregation` | `aggregate` | **PASS** | 1 | 1 | N/A | OK |
| `q30` | `aggregation` | `aggregate` | **PASS** | 3 | 3 | N/A | OK |
| `q31` | `explain_experiment` | `explain_experiment` | **PASS** | 1 | 1 | N/A | OK |
| `q32` | `explain_experiment` | `explain_experiment` | **PASS** | 1 | 1 | N/A | OK |
| `q33` | `explain_experiment` | `explain_experiment` | **PASS** | 1 | 1 | N/A | OK |
| `q34` | `explain_experiment` | `explain_experiment` | **PASS** | 1 | 1 | N/A | OK |
| `q35` | `explain_experiment` | `explain_experiment` | **PASS** | 1 | 1 | N/A | OK |
| `q36` | `explain_experiment` | `explain_experiment` | **PASS** | 1 | 1 | N/A | OK |
| `q37` | `explain_experiment` | `explain_experiment` | **PASS** | 1 | 1 | N/A | OK |
| `q38` | `explain_experiment` | `explain_experiment` | **PASS** | 1 | 1 | N/A | OK |
| `q39` | `qualitative` | `qualitative` | **PASS** | 0 | 109 | 100% | OK |
| `q40` | `qualitative` | `qualitative` | **PASS** | 0 | 109 | 100% | OK |
| `q41` | `qualitative` | `qualitative` | **PASS** | 0 | 110 | 100% | OK |
| `q42` | `qualitative` | `qualitative` | **PASS** | 0 | 110 | 100% | OK |
| `q43` | `qualitative` | `qualitative` | **PASS** | 0 | 110 | 100% | OK |
| `q44` | `qualitative` | `qualitative` | **PASS** | 0 | 110 | 100% | OK |
| `q45` | `out_of_scope` | `out_of_scope` | **PASS** | 0 | 0 | N/A | OK |
| `q46` | `out_of_scope` | `out_of_scope` | **PASS** | 0 | 0 | N/A | OK |
| `q47` | `out_of_scope` | `out_of_scope` | **PASS** | 0 | 0 | N/A | OK |
| `q48` | `out_of_scope` | `out_of_scope` | **PASS** | 0 | 0 | N/A | OK |
| `q49` | `out_of_scope` | `out_of_scope` | **PASS** | 0 | 0 | N/A | OK |
| `q50` | `out_of_scope` | `out_of_scope` | **PASS** | 0 | 0 | N/A | OK |
| `q51` | `qualitative` | `qualitative` | **PASS** | 2 | 107 | 100% | OK |
| `q52` | `qualitative` | `qualitative` | **PASS** | 1 | 109 | 100% | OK |
| `q53` | `qualitative` | `qualitative` | **PASS** | 1 | 109 | 100% | OK |
| `q54` | `qualitative` | `qualitative` | **PASS** | 1 | 105 | 100% | OK |
| `q55` | `qualitative` | `qualitative` | **PASS** | 1 | 100 | 100% | OK |
| `q56` | `qualitative` | `qualitative` | **PASS** | 3 | 102 | 100% | OK |
| `q57` | `qualitative` | `qualitative` | **PASS** | 1 | 104 | 100% | OK |
| `q58` | `qualitative` | `qualitative` | **PASS** | 1 | 104 | 100% | OK |
| `q59` | `qualitative` | `qualitative` | **PASS** | 1 | 107 | 100% | OK |
| `q60` | `qualitative` | `qualitative` | **PASS** | 4 | 110 | 100% | OK |
| `q61` | `qualitative` | `qualitative` | **PASS** | 2 | 109 | 100% | OK |
| `q62` | `qualitative` | `qualitative` | **PASS** | 3 | 107 | 100% | OK |
| `q63` | `qualitative` | `qualitative` | **PASS** | 1 | 108 | 100% | OK |
| `q64` | `qualitative` | `qualitative` | **PASS** | 1 | 105 | 100% | OK |
| `q65` | `qualitative` | `qualitative` | **PASS** | 1 | 100 | 100% | OK |
