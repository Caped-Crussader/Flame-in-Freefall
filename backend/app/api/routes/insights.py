"""Rankings, risk prediction and summarized safety insights."""
from fastapi import APIRouter

from backend.app.models.schemas import RiskQuery, RiskResult
from backend.app.services import ranking, risk_model

router = APIRouter()


@router.get("/ranking")
def get_ranking(top_k: int = 10):
    return ranking.rank_findings(top_k=top_k)


@router.post("/risk", response_model=RiskResult)
def predict_risk(query: RiskQuery):
    return risk_model.predict(query)
