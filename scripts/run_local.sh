#!/usr/bin/env bash
# Start FastAPI backend (:8000, also serving web/dist) and React Vite dev server (:5173).
# Pass --streamlit to also launch the Streamlit UI (:8501).
set -e
cd "$(dirname "$0")/.."
export PYTHONPATH="$(pwd)/src:$(pwd)"
source .venv/bin/activate

uvicorn backend.app.main:app --reload --port 8000 &
BACK=$!
trap "kill $BACK 2>/dev/null || true" EXIT

if [[ "${1:-}" == "--streamlit" ]]; then
  streamlit run frontend/app.py --server.port 8501
else
  npm run dev --prefix web
fi
