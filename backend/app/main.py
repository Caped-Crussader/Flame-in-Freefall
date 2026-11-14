"""FastAPI entrypoint. Run: uvicorn backend.app.main:app --reload --port 8000"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api.routes import experiments, insights, chat
from backend.app.core.config import settings

app = FastAPI(title=settings.APP_NAME, version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8501"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(experiments.router, prefix="/api/experiments", tags=["experiments"])
app.include_router(insights.router, prefix="/api/insights", tags=["insights"])
app.include_router(chat.router, prefix="/api/chat", tags=["chat"])


@app.get("/health")
def health():
    return {"status": "ok"}
