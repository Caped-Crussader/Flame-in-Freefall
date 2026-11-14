"""Idempotent hybrid semantic + BM25 index builder for Flame in Freefall.

Indexes all records in data/processed/experiments.parquet into `data/interim/qdrant/`
with dense SVD/TF-IDF and Okapi BM25 sparse vectors, saving snapshot version metadata.
"""

from __future__ import annotations

import argparse
import json
import logging

import joblib
import pandas as pd

from flame.config import Settings, get_settings
from flame.retrieval.semantic import (
    LOCAL_INDEX_FILE,
    METADATA_FILE,
    build_local_hybrid_index,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("flame.scripts.build_index")


def build_semantic_index(
    settings: Settings | None = None,
    force_rebuild: bool = False,
) -> None:
    cfg = settings or get_settings()
    parquet_path = cfg.dataset_output_path
    if not parquet_path.exists():
        raise FileNotFoundError(f"Dataset snapshot not found at {parquet_path}")

    qdrant_dir = cfg.qdrant_path
    qdrant_dir.mkdir(parents=True, exist_ok=True)
    meta_path = qdrant_dir / METADATA_FILE
    idx_path = qdrant_dir / LOCAL_INDEX_FILE

    # Load manifest to get parquet sha256
    parquet_sha256 = None
    if cfg.provenance_manifest_path.exists():
        with open(cfg.provenance_manifest_path, encoding="utf-8") as f:
            manifest = json.load(f)
            parquet_sha256 = manifest.get("outputs", {}).get("parquet_sha256")

    if not force_rebuild and meta_path.exists() and idx_path.exists():
        with open(meta_path, encoding="utf-8") as f:
            existing_meta = json.load(f)
        if existing_meta.get("parquet_sha256") == parquet_sha256:
            logger.info("Semantic index is already up to date with dataset version.")
            return

    logger.info("Building hybrid semantic + BM25 index from %s...", parquet_path)
    df = pd.read_parquet(parquet_path)
    index_data = build_local_hybrid_index(
        df,
        model_name=cfg.embedding_model,
        allow_download=True,
    )
    joblib.dump(index_data, idx_path)

    meta = {
        "parquet_sha256": parquet_sha256,
        "embedding_model": cfg.embedding_model,
        "dense_backend": index_data.get("dense_backend", "tfidf-svd"),
        "sparse_model": cfg.sparse_model,
        "total_indexed": len(df),
    }
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)
    logger.info("Saved hybrid index (%d records) and metadata to %s", len(df), qdrant_dir)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build hybrid semantic + BM25 index.")
    parser.add_argument("--force", action="store_true", help="Force rebuild even if up to date.")
    args = parser.parse_args()
    build_semantic_index(force_rebuild=args.force)


if __name__ == "__main__":
    main()
