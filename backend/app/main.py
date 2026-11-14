"""FastAPI entrypoint unifying `flame.api` and legacy routes.

Run:
    PYTHONPATH=src uvicorn backend.app.main:app --reload --port 8000
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from flame.api.main import app, create_app  # noqa: E402


@app.get("/health", tags=["Observability"])
def root_health() -> dict[str, str]:
    return {"status": "ok"}


__all__ = ["app", "create_app"]
