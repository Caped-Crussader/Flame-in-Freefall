"""Predict flammability risk for given cabin conditions (O2 %, pressure, material, flow)."""
from backend.app.models.schemas import RiskQuery


def predict(q: RiskQuery) -> dict:
    # TODO: load trained model from backend/app/ml/artifacts
    score = min(1.0, (q.oxygen_pct / 21.0) * 0.5)  # placeholder heuristic
    level = "HIGH" if score > 0.66 else "MEDIUM" if score > 0.33 else "LOW"
    return {"risk_score": score, "risk_level": level, "explanation": "Placeholder heuristic."}
