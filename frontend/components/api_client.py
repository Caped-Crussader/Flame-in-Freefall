"""HTTP client for the Flame in Freefall FastAPI backend (/api/v1/*) with direct fallback."""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

import requests

ROOT_DIR = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

API_URL = os.getenv("API_URL", "http://localhost:8000")

_LOCAL_CLIENT = None


def _get_inprocess_client():
    """Fallback to FastAPI TestClient if uvicorn isn't running in a separate terminal."""
    global _LOCAL_CLIENT
    if _LOCAL_CLIENT is None:
        from fastapi.testclient import TestClient
        from backend.app.main import app

        _LOCAL_CLIENT = TestClient(app)
    return _LOCAL_CLIENT


def health() -> dict[str, Any]:
    try:
        r = requests.get(f"{API_URL}/api/v1/ready", timeout=2)
        if r.ok:
            data = r.json()
            data["mode"] = "http"
            return data
    except requests.RequestException:
        pass
    try:
        r = _get_inprocess_client().get("/api/v1/ready")
        data = r.json()
        data["mode"] = "embedded"
        return data
    except Exception as e:
        return {"status": "offline", "error": str(e), "mode": "offline"}


def get(path: str, **params: Any) -> Any:
    full_path = path if path.startswith("/api/") else f"/api/v1{path}"
    try:
        r = requests.get(f"{API_URL}{full_path}", params=params, timeout=30)
        if r.ok:
            return r.json()
    except requests.RequestException:
        pass
    return _get_inprocess_client().get(full_path, params=params).json()


def post(path: str, payload: dict[str, Any]) -> Any:
    full_path = path if path.startswith("/api/") else f"/api/v1{path}"
    try:
        r = requests.post(f"{API_URL}{full_path}", json=payload, timeout=120)
        if r.ok:
            return r.json()
    except requests.RequestException:
        pass
    return _get_inprocess_client().post(full_path, json=payload).json()
