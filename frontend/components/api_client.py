"""Small HTTP client for the FastAPI backend."""
import os
import requests

API_URL = os.getenv("API_URL", "http://localhost:8000")


def health() -> bool:
    try:
        return requests.get(f"{API_URL}/health", timeout=2).ok
    except requests.RequestException:
        return False


def get(path: str, **params):
    return requests.get(f"{API_URL}{path}", params=params, timeout=30).json()


def post(path: str, payload: dict):
    return requests.post(f"{API_URL}{path}", json=payload, timeout=120).json()
