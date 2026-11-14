# Architecture

```
NASA data (PSI, NTRS reports, CSV)  ->  scripts/ingest_data.py
        -> data/processed + SQLite (data/flame.db) + vector store (data/vectorstore)
        -> FastAPI backend (:8000)  [experiments | insights/ranking | insights/risk | chat (RAG)]
        -> Streamlit dashboard (:8501)
```
