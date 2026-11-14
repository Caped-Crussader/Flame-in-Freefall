#!/usr/bin/env bash
# Start backend (8000) and frontend (8501) together.
set -e
cd "$(dirname "$0")/.."
source .venv/bin/activate
uvicorn backend.app.main:app --reload --port 8000 &
BACK=$!
trap "kill $BACK" EXIT
cd frontend && streamlit run app.py --server.port 8501
