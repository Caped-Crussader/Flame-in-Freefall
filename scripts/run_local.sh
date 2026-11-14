#!/usr/bin/env bash
# Start backend (8000) and Streamlit frontend (8501) together.
set -e
cd "$(dirname "$0")/.."
export PYTHONPATH="$(pwd)/src:$(pwd)"
source .venv/bin/activate
uvicorn backend.app.main:app --reload --port 8000 &
BACK=$!
trap "kill $BACK" EXIT
streamlit run frontend/app.py --server.port 8501
