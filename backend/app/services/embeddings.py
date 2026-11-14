"""Chunk documents, embed them and store in a local vector store (data/vectorstore)."""


def build_index():
    # TODO: chunk text -> sentence-transformers embeddings -> ChromaDB/FAISS
    raise NotImplementedError


def search(query: str, k: int = 5):
    # TODO: similarity search
    return []
