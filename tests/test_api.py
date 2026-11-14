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
    assert len(rank_body["historical_incidents"]) == 4
    assert len(rank_body["psi_dossiers"]) >= 3
    assert len(rank_body["psi_experimental_tables"]) >= 3

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
    env = risk_body["envelope"]
    assert len(env["pressure_grid_kpa"]) == 19
    assert len(env["oxygen_grid_pct"]) == 19
    assert len(env["risk_matrix"]) == 19
    assert len(env["moc_0g_o2_pct"]) == 19
    assert len(env["moc_1g_std6001_o2_pct"]) == 19
    assert len(env["airflow_risk_matrix"]) == 19

    # Priority 3: Physics-informed diagnostics & 90% prediction interval bounds
    phys = risk_body["physics_diagnostics"]
    assert phys["oxygen_partial_pressure_kpa"] > 18.0
    assert phys["moc_0g_limit_o2_pct"] < phys["moc_1g_std6001_limit_o2_pct"]
    assert phys["peclet_transport_factor"] > 0.0
    assert len(phys["transport_regime"]) > 5

    unc = risk_body["uncertainty"]
    assert len(unc["burning_rate_ci90_mms"]) == 2
    assert unc["burning_rate_ci90_mms"][0] <= unc["burning_rate_ci90_mms"][1]
    assert len(unc["flame_temp_ci90_k"]) == 2
    assert unc["flame_temp_ci90_k"][0] <= unc["flame_temp_ci90_k"][1]
    assert unc["confidence_level"] in {"HIGH", "MODERATE", "EXPLORATORY"}

    # Priority 2: Detection, Suppression & Post-Fire Cleanup Advisor (SAME, DAFT, SLICE, SAFFIRE)
    det = risk_body["detection_suppression"]
    assert det["smoke_cmd_0g_um"] > det["smoke_cmd_1g_um"]
    assert 0.0 < det["photoelectric_sensitivity"] <= 1.0
    assert 0.0 < det["ionization_sensitivity"] <= 1.0
    assert len(det["extinguishant_options"]) == 4
    assert det["estimated_peak_co_ppm"] > 0.0
    assert len(det["post_fire_cleanup_steps"]) == 4
    assert len(det["evidence_experiments"]) >= 4

    # Priority 5: Exportable Mission Safety Dossier (Markdown + Print-Ready PDF/HTML)
    r_dossier = client.post(
        "/api/v1/insights/dossier",
        json={
            "oxygen_pct": 34.0,
            "pressure_kpa": 56.5,
            "airflow_velocity_cms": 10.0,
            "fuel_material": "SIBAL (Cotton-Fiberglass Blend)",
        },
    )
    assert r_dossier.status_code == 200
    d_body = r_dossier.json()
    assert d_body["dossier_id"].startswith("IGNIS-CERT-")
    assert "SPACECRAFT & HABITAT FIRE-SAFETY CERTIFICATION DOSSIER" in d_body["markdown_report"]
    assert "<svg" in d_body["html_printable"]


def test_evaluation_scorecard():
    r_eval = client.get("/api/v1/evaluation")
    assert r_eval.status_code == 200
    body = r_eval.json()
    assert body["overall_evaluated"] == 65
    assert body["overall_passed"] == 65
    assert body["overall_pass_rate"] == 1.0
    assert body["qualitative_recall_at_10"] == 1.0


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
    assert len(b2["literature"]) >= 2


def test_literature_endpoint():
    r = client.get(
        "/api/v1/literature",
        params={"q": "Saffire exploration atmosphere 34% O2", "limit": 4},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["total"] >= 30
    assert len(body["items"]) == 4
    assert any("PSI" in item["doc_id"] or "LIT" in item["doc_id"] for item in body["items"])
