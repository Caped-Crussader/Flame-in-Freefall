"""Retrieval-augmented generation: retrieve relevant chunks, then ask the LLM."""
from backend.app.services import embeddings, llm


def answer(question: str) -> dict:
    hits = embeddings.search(question)
    context = "\n\n".join(h.get("text", "") for h in hits)
    prompt = (
        "You are a spacecraft fire-safety expert. Using only the NASA microgravity "
        f"combustion context below, answer the question.\n\nContext:\n{context}\n\nQuestion: {question}"
    )
    return {"answer": llm.generate(prompt), "sources": [h.get("source", "") for h in hits]}
