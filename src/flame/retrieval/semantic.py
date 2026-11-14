"""Row-level document builder and hybrid semantic (SentenceTransformer / LSA) + BM25 index integration.

Supports:
1. Pre-installed `sentence-transformers` (`BAAI/bge-small-en-v1.5` / `all-MiniLM-L6-v2`) dense 384-d neural embeddings
   combined with lexical TF-IDF + Okapi BM25 via Reciprocal Rank Fusion (RRF, k=60).
2. Automatic air-gapped fallback to scikit-learn dense SVD/TF-IDF + Okapi BM25 when local HuggingFace model
   weights are not yet cached on disk.
"""

from __future__ import annotations

import json
import logging
import math
import re
from collections import Counter
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import normalize

try:
    from sentence_transformers import SentenceTransformer
except ImportError:
    SentenceTransformer = None  # type: ignore[assignment,misc]

from flame.config import Settings, get_settings
from flame.schemas.query_plan import FilterOperator, QueryPlan

logger = logging.getLogger("flame.retrieval.semantic")

COLLECTION_NAME = "experiments"
METADATA_FILE = "semantic_meta.json"
LOCAL_INDEX_FILE = "local_hybrid_index.joblib"

_TOKEN_RE = re.compile(r"[a-z0-9]+(?:[-.][a-z0-9]+)*")
_ST_MODEL_CACHE: dict[str, Any] = {}


def _tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


def _load_sentence_transformer(model_name: str, allow_download: bool = False) -> Any | None:
    """Load SentenceTransformer from local HuggingFace cache (or download if allow_download=True)."""
    if SentenceTransformer is None:
        return None
    if model_name in _ST_MODEL_CACHE:
        return _ST_MODEL_CACHE[model_name]

    # Try local cache first so sandboxed/offline execution never hangs on network timeouts
    try:
        model = SentenceTransformer(model_name, local_files_only=True)
        _ST_MODEL_CACHE[model_name] = model
        return model
    except Exception:
        if not allow_download:
            return None

    try:
        model = SentenceTransformer(model_name, local_files_only=False)
        _ST_MODEL_CACHE[model_name] = model
        return model
    except Exception as err:
        logger.warning("Could not load SentenceTransformer '%s': %s", model_name, err)
        return None


def build_document_text(row: dict[str, Any] | pd.Series) -> str:
    """Build a row-level retrieval document combining conditions and free-text notes."""
    eid = row.get("experiment_id", "")
    family = row.get("dataset_family", "")
    inv = row.get("investigation_id", "")
    fuel = row.get("fuel_material", "")
    category = row.get("material_category", "")
    gravity = row.get("gravity_condition", "")
    outcome = row.get("extinction_outcome", "")
    desc = row.get("sample_description", "")
    notes = row.get("notes", "")
    hw = row.get("facility_hardware", "")

    return (
        f"Experiment {eid}: family={family}, investigation={inv}, fuel={fuel}, "
        f"category={category}, gravity={gravity}, outcome={outcome}, hardware={hw}. "
        f"Description: {desc}. Notes: {notes}"
    )


def build_local_hybrid_index(
    df: pd.DataFrame,
    model_name: str = "BAAI/bge-small-en-v1.5",
    allow_download: bool = False,
) -> dict[str, Any]:
    """Build a hybrid index (SentenceTransformer neural dense + LSA/TF-IDF + Okapi BM25) for all rows."""
    docs = [build_document_text(row) for _, row in df.iterrows()]
    tokenized = [_tokenize(d) for d in docs]
    doc_lens = [len(t) for t in tokenized]
    avgdl = sum(doc_lens) / max(1, len(doc_lens))

    # 1. Document frequencies for Okapi BM25
    df_counts: Counter[str] = Counter()
    tf_list: list[Counter[str]] = []
    for toks in tokenized:
        c = Counter(toks)
        tf_list.append(c)
        for term in c:
            df_counts[term] += 1

    # 2. Word + bigram TF-IDF + SVD dense vectors
    tfidf = TfidfVectorizer(
        ngram_range=(1, 2),
        max_features=12000,
        sublinear_tf=True,
        stop_words="english",
    )
    tfidf_mat = tfidf.fit_transform(docs)
    n_comp = min(192, tfidf_mat.shape[0] - 1, tfidf_mat.shape[1] - 1)
    svd = TruncatedSVD(n_components=n_comp, random_state=42)
    dense_vecs = normalize(svd.fit_transform(tfidf_mat))

    # 3. Optional SentenceTransformer 384-d neural embeddings when cached/available
    st_model = _load_sentence_transformer(model_name, allow_download=allow_download)
    st_vecs: np.ndarray | None = None
    dense_backend = "tfidf-svd"
    if st_model is not None:
        try:
            st_vecs = np.asarray(
                st_model.encode(docs, normalize_embeddings=True, show_progress_bar=False),
                dtype=np.float32,
            )
            dense_backend = f"sentence-transformers ({model_name})"
            logger.info("Encoded %d documents with SentenceTransformer (%s)", len(docs), model_name)
        except Exception as err:
            logger.warning("SentenceTransformer encoding failed (%s); using TF-IDF/SVD.", err)
            st_vecs = None

    records = []
    for _, row in df.iterrows():
        rec = {}
        for col in df.columns:
            val = row[col]
            if hasattr(val, "tolist"):
                val = val.tolist()
            rec[col] = val
        records.append(rec)

    return {
        "records": records,
        "docs": docs,
        "tf_list": tf_list,
        "doc_lens": doc_lens,
        "avgdl": avgdl,
        "df_counts": df_counts,
        "n_docs": len(docs),
        "tfidf": tfidf,
        "svd": svd,
        "tfidf_mat": tfidf_mat,
        "dense_vecs": dense_vecs,
        "st_vecs": st_vecs,
        "embedding_model": model_name,
        "dense_backend": dense_backend,
    }


class SemanticRetriever:
    """Manages hybrid neural/dense vector + BM25 search with payload filtering and RRF fusion."""

    def __init__(
        self,
        client: Any | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.client = client
        self._local_index: dict[str, Any] | None = None

    def _get_local_index(self) -> dict[str, Any]:
        if self._local_index is None:
            idx_path = self.settings.qdrant_path / LOCAL_INDEX_FILE
            if idx_path.exists():
                self._local_index = joblib.load(idx_path)
            else:
                df = pd.read_parquet(self.settings.dataset_output_path)
                self._local_index = build_local_hybrid_index(
                    df, model_name=self.settings.embedding_model, allow_download=False
                )
                self.settings.qdrant_path.mkdir(parents=True, exist_ok=True)
                joblib.dump(self._local_index, idx_path)
        return self._local_index

    @property
    def dense_backend(self) -> str:
        """Return the active dense embedding backend name."""
        idx = self._get_local_index()
        return str(idx.get("dense_backend", "tfidf-svd"))

    @staticmethod
    def _matches_plan_filters(rec: dict[str, Any], plan: QueryPlan) -> bool:
        if not plan.include_modeled and bool(rec.get("is_modeled", False)):
            return False

        for f in plan.filters:
            val = rec.get(f.field)
            op = f.op
            target = f.value
            if op == FilterOperator.EQ:
                if val != target:
                    return False
            elif op == FilterOperator.IN and isinstance(target, (list, tuple, set)):
                if val not in target:
                    return False
            elif op == FilterOperator.GTE:
                if val is None or float(val) < float(target):
                    return False
            elif op == FilterOperator.LTE:
                if val is None or float(val) > float(target):
                    return False
            elif op == FilterOperator.BETWEEN and isinstance(target, (list, tuple)):
                if val is None or not (float(target[0]) <= float(val) <= float(target[1])):
                    return False
            elif op == FilterOperator.CONTAINS:
                if val is None or str(target).lower() not in str(val).lower():
                    return False
            elif op == FilterOperator.IS_NULL:
                if val is not None and not (isinstance(val, float) and math.isnan(val)):
                    return False
            elif op == FilterOperator.NOT_NULL:
                if val is None or (isinstance(val, float) and math.isnan(val)):
                    return False
        return True

    def search_hybrid(
        self,
        query_text: str,
        plan: QueryPlan,
        limit: int = 10,
    ) -> list[str]:
        """Perform hybrid RRF search (SentenceTransformer/LSA dense + BM25) and return ranked IDs."""
        idx = self._get_local_index()
        records: list[dict[str, Any]] = idx["records"]
        candidate_indices = [
            i for i, rec in enumerate(records) if self._matches_plan_filters(rec, plan)
        ]
        if not candidate_indices:
            return []

        # 1. Sparse Okapi BM25 scores
        q_tokens = _tokenize(query_text)
        n_docs = idx["n_docs"]
        avgdl = idx["avgdl"]
        df_counts: Counter[str] = idx["df_counts"]
        tf_list: list[Counter[str]] = idx["tf_list"]
        doc_lens: list[int] = idx["doc_lens"]
        k1 = 1.5
        b = 0.75

        bm25_scores: dict[int, float] = {}
        for i in candidate_indices:
            score = 0.0
            dl = doc_lens[i]
            tfs = tf_list[i]
            for qt in q_tokens:
                tf = tfs.get(qt, 0)
                if tf == 0:
                    continue
                df_q = df_counts.get(qt, 0)
                idf = math.log(1.0 + (n_docs - df_q + 0.5) / (df_q + 0.5))
                denom = tf + k1 * (1.0 - b + b * (dl / avgdl))
                score += idf * (tf * (k1 + 1.0)) / denom
            bm25_scores[i] = score

        # 2. Dense neural SentenceTransformer + LSA/TF-IDF cosine similarity scores
        tfidf: TfidfVectorizer = idx["tfidf"]
        svd: TruncatedSVD = idx["svd"]
        tfidf_mat = idx["tfidf_mat"]
        dense_vecs: np.ndarray = idx["dense_vecs"]
        st_vecs: np.ndarray | None = idx.get("st_vecs")
        emb_model_name = str(idx.get("embedding_model") or self.settings.embedding_model)

        q_tfidf = tfidf.transform([query_text])
        q_dense = normalize(svd.transform(q_tfidf))[0]
        lexical_cos = (tfidf_mat @ q_tfidf.T).toarray().ravel()
        semantic_cos = dense_vecs @ q_dense

        st_cos: np.ndarray | None = None
        if st_vecs is not None:
            st_model = _load_sentence_transformer(emb_model_name, allow_download=False)
            if st_model is not None:
                try:
                    q_st = np.asarray(
                        st_model.encode([query_text], normalize_embeddings=True, show_progress_bar=False)[0],
                        dtype=np.float32,
                    )
                    st_cos = st_vecs @ q_st
                except Exception:
                    st_cos = None

        if st_cos is not None:
            dense_scores: dict[int, float] = {
                i: float(0.55 * st_cos[i] + 0.30 * lexical_cos[i] + 0.15 * semantic_cos[i])
                for i in candidate_indices
            }
        else:
            dense_scores = {
                i: float(0.60 * lexical_cos[i] + 0.40 * semantic_cos[i]) for i in candidate_indices
            }

        # 3. Reciprocal Rank Fusion (RRF, k=60)
        bm25_ranked = sorted(candidate_indices, key=lambda i: bm25_scores[i], reverse=True)
        dense_ranked = sorted(candidate_indices, key=lambda i: dense_scores[i], reverse=True)

        rrf_k = 60.0
        rrf_scores: dict[int, float] = {i: 0.0 for i in candidate_indices}
        for rank, doc_idx in enumerate(bm25_ranked, start=1):
            if bm25_scores[doc_idx] > 0:
                rrf_scores[doc_idx] += 1.0 / (rrf_k + rank)
        for rank, doc_idx in enumerate(dense_ranked, start=1):
            if dense_scores[doc_idx] > 0:
                rrf_scores[doc_idx] += 1.0 / (rrf_k + rank)

        final_ranked = sorted(
            candidate_indices,
            key=lambda i: (rrf_scores[i], bm25_scores[i], dense_scores[i]),
            reverse=True,
        )[:limit]

        return [str(records[i]["experiment_id"]) for i in final_ranked]

    def verify_index_version(self, expected_sha256: str | None) -> bool:
        """Verify that index metadata matches the current Parquet snapshot version."""
        meta_path = self.settings.qdrant_path / METADATA_FILE
        if not meta_path.exists():
            return False
        try:
            with open(meta_path, encoding="utf-8") as f:
                data = json.load(f)
            return bool(data.get("parquet_sha256") == expected_sha256)
        except Exception:
            return False


__all__ = [
    "COLLECTION_NAME",
    "LOCAL_INDEX_FILE",
    "METADATA_FILE",
    "SemanticRetriever",
    "build_document_text",
    "build_local_hybrid_index",
]
