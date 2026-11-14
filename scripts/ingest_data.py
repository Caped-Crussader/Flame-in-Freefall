"""Pipeline: raw files -> processed data -> SQLite + vector index.
Run: python -m scripts.ingest_data
"""
from backend.app.core.database import Base, engine
from backend.app.models import experiment  # noqa: F401  (register model)


def main():
    Base.metadata.create_all(engine)
    print("DB tables created. TODO: ingestion + embeddings.build_index()")


if __name__ == "__main__":
    main()
