# Flame-in-Freefall
Challenge is to create an interactive, super intelligence (SI) powered dashboard that summarizes, ranks, and interprets those findings to deliver fire safety insights for human space exploration.

## Project Structure
```
NSAP/
├── backend/                  # FastAPI API (localhost:8000)
│   └── app/
│       ├── main.py           # App entrypoint
│       ├── core/             # config.py (.env settings), database.py (SQLite)
│       ├── models/           # experiment.py (DB), schemas.py (Pydantic)
│       ├── api/routes/       # experiments.py, insights.py, chat.py
│       ├── services/         # ingestion, embeddings, llm, rag, ranking, risk_model
│       └── ml/               # train.py, features.py (flammability model)
├── frontend/                 # Streamlit dashboard (localhost:8501)
│   ├── app.py                # Home
│   ├── pages/                # Explorer, Insights, Risk Simulator, Ask the Data
│   ├── components/           # api_client.py, charts.py
│   └── assets/
├── data/
│   ├── raw/                  # NASA datasets / PDFs (not committed)
│   ├── processed/            # Cleaned data
│   └── vectorstore/          # Embeddings index
├── scripts/                  # ingest_data.py, run_local.sh
├── notebooks/                # EDA
├── tests/                    # pytest
├── docs/                     # architecture.md
├── requirements.txt
└── .env.example
```

## Run Locally
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python -m scripts.ingest_data          # create DB

# Terminal 1 – backend
uvicorn backend.app.main:app --reload --port 8000
# Terminal 2 – frontend
cd frontend && streamlit run app.py
```
Or run both: `bash scripts/run_local.sh`

- Dashboard: http://localhost:8501
- API docs: http://localhost:8000/docs

Optional local LLM: install [Ollama](https://ollama.com) and `ollama pull llama3.1`.
