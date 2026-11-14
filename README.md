# 🔥 Flame in Freefall
**SI-Powered Fire Safety Insights from NASA/JAXA Microgravity Combustion Data**  
*2026 NASA Space Apps Challenge*

<img width="2185" height="1355" alt="Screenshot From 2026-11-14 15-57-31" src="https://github.com/user-attachments/assets/d49a69a8-1929-4cc7-afd5-c8ff3693bb4d" />

An interactive decision-support dashboard and hybrid retrieval-augmented generation (RAG) system that unifies decades of NASA and JAXA microgravity combustion experiments (**892 experiments × 44 columns** across **30 dataset families** and **35 investigations**) to deliver deterministic, citation-grounded fire-safety insights for ISS, Artemis lunar habitats, and Mars transit missions.

---

## ✨ Key Capabilities

1. **Deterministic Ingestion & Provenance Auditing (`src/flame/ingestion/`):**
   - Consolidates 17 NASA/JAXA source CSV datasets (`BASS`, `BASS-II`, `SOFIE`, `SAFFIRE I–VI`, `FLEX`, `FLEX-2`, `ACME` suite, `SLICE`, `MGM`, `SAME`, `SPICE`, `DAFT`, `FLARE`, `GRC Drop Tower`, and `NASA-STD-6001`) plus live NASA Physical Sciences Informatics (**PSI**) metadata (`data/raw/psi/`) into a validated Parquet snapshot (`data/processed/experiments.parquet`).
   - Enforces explicit provenance tracking (`source_file`, `source_row`, `record_source`), quarantines 42 corrupt BASS-II airflow readings (`> 1000 cm/s` → `AIRFLOW_QUARANTINED`), and isolates 52 computational partial-gravity bounding rows (`is_modeled = True`) so they are excluded by default unless explicitly toggled.
2. **Structured + Hybrid RRF Retrieval (`src/flame/retrieval/`):**
   - Compiles natural-language questions into typed, schema-whitelisted `QueryPlan` objects executed against an in-memory SQL engine (DuckDB / SQLite-over-Parquet) with exact `n_used`, `n_null_excluded`, and `n_quarantined_excluded` accounting.
   - Augments qualitative and explanatory queries with **Reciprocal Rank Fusion (RRF)** combining Okapi BM25 sparse lexical matching and dense semantic vector embeddings (`data/interim/qdrant/`).
3. **Grounded RAG with Post-Generation Guardrails (`src/flame/rag/`):**
   - Verifies every inline citation (`[BASS-B1]`, `[SOFIE-001]`, `[FLEX2-F2-05]`, etc.) against retrieved evidence rows, checks numeric grounding within $10^{-4}$ relative tolerance, enforces modeled-row disclosures, and warns on semantically incomparable cross-family aggregations (`burning_rate_mms`).
   - Works **100% offline** via `LocalHeuristicLLMClient` (including all 65 hand-verified benchmark questions in `evaluation/golden_questions.yaml`) and seamlessly delegates to a local **Ollama**, **OpenAI-compatible**, or **Anthropic** LLM when configured.
4. **Ranked Fire-Safety Insights & Cabin Flammability Simulator (`src/flame/api/insights.py`):**
   - Ranks all 30 dataset families by fire-safety criticality and synthesizes top actionable spacecraft design findings.
   - Runs a Random Forest sustained-burn classifier, spread-rate regressor, and flame-temperature regressor trained on the 840 physical microgravity experiments, alongside a 5-nearest-neighbor search in $(\text{O}_2\%, \text{Pressure}, \text{Airflow}, \text{Material})$ space.

---

## 📁 Project Structure

```text
NSAP/
├── src/flame/                      # Core Flame in Freefall engine
│   ├── config.py                   # Typed FLAME_* settings (pydantic-settings)
│   ├── schemas/                    # Experiment (44 cols), QueryPlan, AskResponse contracts
│   ├── ingestion/                  # CSV canonicalization, cleaning, Pandera/hard validation
│   ├── retrieval/                  # ExperimentStore (SQL), compiler, catalog, hybrid RRF search
│   ├── rag/                        # QueryPlanner, AnswerGenerator, citation/numeric guardrails
│   ├── llm/                        # LocalHeuristicLLMClient, OpenAICompatClient (Ollama), Anthropic
│   ├── observability/              # Request-ID correlation & secret-redacting structured logs
│   └── api/                        # FastAPI routes (/api/v1/*) & FlammabilityEngine insights
├── backend/app/
│   ├── main.py                     # ASGI entrypoint mounting flame.api (:8000)
│   └── core/http.py                # Verified TLS/SSL session helper for NASA PSI & Space Apps
├── web/                            # React 19 + TypeScript + Vite SPA (:5173 / mounted on :8000)
│   ├── src/
│   │   ├── components/
│   │   │   ├── FlameBackground.tsx # 60 FPS HTML5 Canvas flame plumes + 0g blue microgravity orb
│   │   │   ├── AnswerPanel.tsx     # Grounded Markdown + interactive [ID] citation chips
│   │   │   ├── EvidenceTable.tsx   # Sortable evidence table with provenance flags
│   │   │   └── DetailDrawer.tsx    # Slide-over 44-column provenance & audit drawer
│   │   ├── pages/
│   │   │   ├── Home.tsx            # Hero, live KPI counter strip & architecture overview
│   │   │   ├── Explorer.tsx        # 892-row interactive dataset & provenance explorer
│   │   │   ├── Insights.tsx        # Top 5 findings, 4 historical incidents & live PSI CSV tables
│   │   │   ├── Simulator.tsx       # 2D MOC flammability canvas & airflow quench/blowoff maps
│   │   │   └── Dashboard.tsx       # Dataset family breakdown & data quality audit
│   │   └── App.tsx                 # Grounded Hybrid RAG Q&A + Live 65/65 Benchmark Scorecard
│   └── tests/                      # 33 Vitest + Testing Library unit & integration tests
├── frontend/                       # Streamlit interactive dashboard (:8501)
│   ├── app.py                      # Mission Control Home (KPIs, caveats, atmosphere envelope)
│   ├── pages/
│   │   ├── 1_Explorer.py           # Dataset & 44-column provenance browser + Modeled toggle
│   │   ├── 2_Insights.py           # Top 5 ranked safety findings, PSI catalog & quality audit
│   │   ├── 3_Risk_Simulator.py     # ISS / Artemis / EVA flammability & nearest-neighbor simulator
│   │   └── 4_Ask_the_Data.py       # Grounded Hybrid RAG + QueryPlan & Evidence inspector
│   └── components/                 # api_client.py (HTTP + embedded fallback), charts.py (Plotly)
├── data/
│   ├── raw/                        # 17 NASA/JAXA source CSVs + live PSI JSON/CSV catalog
│   ├── processed/                  # experiments.parquet (892×44), canonical_experiments.csv, manifest
│   ├── reports/                    # quality_report.md, canonical_diff.csv
│   └── interim/qdrant/             # Local hybrid dense + BM25 index & snapshot SHA-256 metadata
├── evaluation/
│   ├── golden_questions.yaml       # 65 hand-verified benchmark questions & QueryPlans
│   └── expected_answers.yaml       # Deterministic expected answers
├── scripts/
│   ├── build_dataset.py            # Rebuilds experiments.parquet & quality_report.md from data/raw/
│   ├── build_index.py              # Builds the hybrid dense + BM25 index in data/interim/qdrant/
│   ├── fetch_psi_data.py           # Pulls live combustion investigations & CSVs from psi.nasa.gov
│   └── run_local.sh                # Launches FastAPI (:8000) + Streamlit (:8501)
├── certs/                          # Intermediate CA certificate for strict TLS verification
├── docs/                           # data_dictionary.md, architecture.md, audit & ADRs
├── tests/                          # 113 unit & API integration tests (pytest)
├── procedure.md                    # Detailed architecture & execution roadmap
└── requirements.txt
```

---

## 🚀 Quickstart (Localhost)

### 1. Activate Virtual Environment
The project uses a Python 3.12 virtual environment in `.venv`:
```bash
source .venv/bin/activate
```

### 2. Rebuild Dataset Snapshot & Hybrid Search Index (Optional — Pre-built in `data/`)
```bash
PYTHONPATH=src python scripts/build_dataset.py
PYTHONPATH=src python scripts/build_index.py
```

### 3. Run the React UI & FastAPI Backend
You can launch the FastAPI server (`http://localhost:8000`) and the React 19 + Vite UI (`http://localhost:5173`) together:
```bash
bash scripts/run_local.sh
```
Or serve the production React bundle (`web/dist`) directly from FastAPI on a single port (`http://localhost:8000`):
```bash
npm run build --prefix web
PYTHONPATH=src:. .venv/bin/uvicorn backend.app.main:app --port 8000
```
Or run the Streamlit dashboard (`http://localhost:8501`):
```bash
bash scripts/run_local.sh --streamlit
```

- **React 19 + Vite UI (Dev):** http://localhost:5173
- **Unified FastAPI + React SPA (Prod):** http://localhost:8000
- **FastAPI OpenAPI Docs:** http://localhost:8000/docs
- **Streamlit Dashboard:** http://localhost:8501

---

## 🔌 API Endpoints (`/api/v1`)

| Method | Endpoint | Description |
|:--|:--|:--|
| `GET` | `/api/v1/health` | Liveness probe (`{"status": "ok"}`) |
| `GET` | `/api/v1/ready` | Readiness probe verifying `experiments.parquet`, provenance manifest, and row count (`892`) |
| `GET` | `/api/v1/meta` | Dataset version, 44-field catalog, 30 dataset families, modeled count (`52`), and scientific caveats |
| `GET` | `/api/v1/experiments` | Filtered & paginated experiments (`dataset_family`, `fuel_material`, `is_modeled`, `limit`, `offset`) |
| `GET` | `/api/v1/experiments/{id}` | Single experiment record with all 44 canonical, enrichment, and provenance columns |
| `GET` | `/api/v1/insights/ranking` | Top 5 ranked spacecraft fire-safety insights, family criticality rankings, and PSI catalog |
| `POST` | `/api/v1/insights/risk` | ML flammability risk score, burn rate, flame temp, 2D MOC flammability envelope (`19×19`), and 5 closest historical NASA/JAXA experiments |
| `POST` | `/api/v1/ask` | End-to-end grounded RAG (`plan -> retrieve -> generate -> guardrails`) returning answer, citations, `QueryPlan`, aggregates, and evidence rows |
| `GET` | `/api/v1/evaluation` | Latest 65-question golden benchmark scorecard (`65/65 = 100.0%` pass rate, `100.0%` Hybrid RRF Recall@10) |
| `POST` | `/api/v1/evaluation/run` | Executes all 65 golden benchmark questions live and returns the updated scorecard |

---

## 🧪 Running Tests

Run the full Python backend test suite (**173 unit and API integration tests**) and the React frontend test suite (**33 Vitest tests**):
```bash
PYTHONPATH=src:. .venv/bin/pytest -q tests/
npm test --prefix web
```
```bash
PYTHONPATH=src:. .venv/bin/pytest -q tests/test_api.py tests/unit/test_clean_dates.py \
  tests/unit/test_clean_numeric.py tests/unit/test_clean_vocab.py tests/unit/test_enrich.py \
  tests/unit/test_guardrails.py tests/unit/test_retrieval_plan.py tests/unit/test_schemas.py \
  tests/unit/test_validate.py tests/unit/test_config.py tests/unit/test_logging.py \
  tests/unit/test_pipeline.py tests/unit/test_planner.py
```

---

## 🤖 Optional LLM Configuration (`.env`)

By default, `/api/v1/ask` uses `LocalHeuristicLLMClient`, which works offline without an API key. To connect a live local **Ollama** model or cloud LLM, set the following in `.env`:

```ini
FLAME_LLM_PROVIDER=openai_compat
FLAME_LLM_MODEL=llama3.1
FLAME_LLM_BASE_URL=http://localhost:11434/v1
FLAME_LLM_API_KEY=local
```
