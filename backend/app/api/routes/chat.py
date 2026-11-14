"""RAG question answering over NASA combustion reports."""
from fastapi import APIRouter

from backend.app.models.schemas import ChatRequest, ChatResponse
from backend.app.services import rag

router = APIRouter()


@router.post("/", response_model=ChatResponse)
def ask(req: ChatRequest):
    return rag.answer(req.question)
