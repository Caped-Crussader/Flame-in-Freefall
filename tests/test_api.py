"""Comprehensive test suite for the harvested Flame in Freefall API, ingestion, hybrid search, and insights."""
from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app.main import app

client = TestClient(app)


def test_health_and_ready():
    r_health = client.get("/api/v1/health")
    assert r_health.status_code == 200
    assert r_health.json()["status"] == "ok"

    r_ready = client.get("/api/v1/ready")
    assert r_ready.status_code == 200
    body = r_ready.json()
    assert body["status"] == "ready"
    assert body["dataset_loaded"] is True
    assert body["total_rows"] == 892


def test_meta_endpoint():
    r = client.get("/api/v1/meta")
    assert r.status_code == 200
    body = r.json()
    assert len(body["dataset_families"]) == 30
    assert body["modeled_rows_count"] == 52
    assert len(body["data_limitations"]) >= 4


def test_experiments_listing_and_detail():
    r = client.get("/api/v1/experiments", params={"dataset_family": "SOFIE", "limit": 5})
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 12
    assert len(body["items"]) == 5

    r_detail = client.get("/api/v1/experiments/SOFIE-001")
    assert r_detail.status_code == 200
    rec = r_detail.json()
    assert rec["experiment_id"] == "SOFIE-001"
    assert rec["dataset_family"] == "SOFIE"


def test_insights_ranking_and_risk_simulator():
    r_rank = client.get("/api/v1/insights/ranking")
    assert r_rank.status_code == 200
    rank_body = r_rank.json()
    assert len(rank_body["findings"]) == 5
    assert len(rank_body["family_rankings"]) >= 28

    r_risk = client.post(
        "/api/v1/insights/risk",
        json={
            "oxygen_pct": 34.0,
            "pressure_kpa": 56.5,
            "airflow_velocity_cms": 10.0,
            "fuel_material": "SIBAL (Cotton-Fiberglass Blend)",
        },
    )
    assert r_risk.status_code == 200
    risk_body = r_risk.json()
    assert risk_body["risk_level"] in {"LOW", "MODERATE", "HIGH", "CRITICAL"}
    assert len(risk_body["nearest_experiments"]) == 5


def test_ask_structured_and_qualitative():
    # 1. Structured lookup from golden set
    r1 = client.post(
        "/api/v1/ask",
        json={"question": "Which non-modeled experiments tested Methanol fuel in the FLEX dataset family?"},
    )
    assert r1.status_code == 200
    b1 = r1.json()
    assert b1["status"] == "answered"
    assert len(b1["evidence"]) == 50

    # 2. Qualitative hybrid search
    r2 = client.post(
        "/api/v1/ask",
        json={"question": "Which experiments studied radiative cool flames around 740 K?"},
    )
    assert r2.status_code == 200
    b2 = r2.json()
    assert b2["status"] == "answered"
    assert len(b2["evidence"]) > 0
