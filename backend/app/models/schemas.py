"""Pydantic request/response schemas."""
from pydantic import BaseModel


class ExperimentOut(BaseModel):
    id: int
    name: str
    platform: str | None = None
    fuel: str | None = None
    oxygen_pct: float | None = None
    pressure_kpa: float | None = None
    flame_spread_rate: float | None = None
    summary: str | None = None

    model_config = {"from_attributes": True}


class RiskQuery(BaseModel):
    oxygen_pct: float
    pressure_kpa: float
    material: str
    flow_velocity_cms: float = 0.0


class RiskResult(BaseModel):
    risk_score: float
    risk_level: str
    explanation: str


class ChatRequest(BaseModel):
    question: str


class ChatResponse(BaseModel):
    answer: str
    sources: list[str] = []
