from fastapi.testclient import TestClient

from backend.app.main import app

client = TestClient(app)


def test_health():
    assert client.get("/health").json() == {"status": "ok"}


def test_risk():
    r = client.post("/api/insights/risk", json={"oxygen_pct": 34, "pressure_kpa": 56.5, "material": "Cotton"})
    assert r.status_code == 200
    assert r.json()["risk_level"] in {"LOW", "MEDIUM", "HIGH"}
