"""DuckDB-backed experiment store for deterministic retrieval over the Parquet snapshot."""

from __future__ import annotations

import json
import math
import sqlite3
from pathlib import Path
from types import TracebackType
from typing import Any

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field

try:
    import duckdb
except ImportError:
    duckdb = None  # type: ignore[assignment]

from flame.config import Settings, get_settings
from flame.retrieval.catalog import FieldCatalog, build_field_catalog
from flame.retrieval.errors import ExecutionError
from flame.retrieval.structured import RetrievalResult, execute_plan
from flame.schemas.query_plan import QueryPlan


def _median_list(values: list[float]) -> float | None:
    if not values:
        return None
    s = sorted(values)
    n = len(s)
    mid = n // 2
    if n % 2 == 1:
        return float(s[mid])
    return float((s[mid - 1] + s[mid]) / 2.0)


class _MedianAgg:
    def __init__(self) -> None:
        self.vals: list[float] = []

    def step(self, value: Any) -> None:
        if value is not None:
            try:
                f = float(value)
                if not math.isnan(f):
                    self.vals.append(f)
            except (ValueError, TypeError):
                pass

    def finalize(self) -> float | None:
        return _median_list(self.vals)


class _SQLiteCompatConn:
    """In-memory SQLite wrapper exposing the same execute/fetchall/cursor API as DuckDB."""

    def __init__(self, parquet_path: Path, table_name: str = "experiments") -> None:
        self._conn = sqlite3.connect(":memory:", check_same_thread=False)
        self._conn.create_aggregate("MEDIAN", 1, _MedianAgg)
        self._conn.create_function(
            "list_contains",
            2,
            lambda flags_json, item: (
                item in json.loads(flags_json)
                if isinstance(flags_json, str) and flags_json.startswith("[")
                else False
            ),
        )
        df = pd.read_parquet(parquet_path)
        df = df.copy()
        if "data_quality_flags" in df.columns:
            df["data_quality_flags"] = df["data_quality_flags"].apply(
                lambda x: json.dumps(list(x)) if hasattr(x, "__iter__") and not isinstance(x, str) else "[]"
            )
        if "is_modeled" in df.columns:
            df["is_modeled"] = df["is_modeled"].astype(int)
        df.to_sql(table_name, self._conn, index=False, if_exists="replace")

    def cursor(self) -> _SQLiteCompatCursor:
        return _SQLiteCompatCursor(self._conn.cursor())

    def close(self) -> None:
        self._conn.close()


class _SQLiteCompatCursor:
    def __init__(self, cur: sqlite3.Cursor) -> None:
        self._cur = cur

    @staticmethod
    def _rewrite_sql(sql: str, params: list[Any] | None = None) -> tuple[str, list[Any]]:
        bound = list(params) if params is not None else []
        # Rewrite DuckDB `WHERE experiment_id IN (SELECT unnest(?))`
        if "SELECT unnest(?)" in sql and bound and isinstance(bound[0], (list, tuple)):
            ids = list(bound[0])
            placeholders = ", ".join("?" for _ in ids) if ids else "NULL"
            sql = sql.replace("SELECT unnest(?)", placeholders)
            bound = ids + bound[1:]
        # Rewrite ILIKE -> LIKE (SQLite LIKE is case-insensitive for ASCII)
        sql = sql.replace(" ILIKE ", " LIKE ")
        # Rewrite is_modeled = FALSE / TRUE
        sql = sql.replace("is_modeled = FALSE", "is_modeled = 0").replace(
            "is_modeled = TRUE", "is_modeled = 1"
        ).replace("is_modeled = true", "is_modeled = 1").replace("is_modeled = false", "is_modeled = 0")
        return sql, bound

    def execute(self, sql: str, params: list[Any] | None = None) -> _SQLiteCompatCursor:
        rewritten, bound = self._rewrite_sql(sql, params)
        self._cur.execute(rewritten, bound)
        return self

    def fetchall(self) -> list[tuple[Any, ...]]:
        return self._cur.fetchall()

    def fetchone(self) -> tuple[Any, ...] | None:
        return self._cur.fetchone()

    @property
    def description(self) -> Any:
        return self._cur.description

    def close(self) -> None:
        self._cur.close()


class DatasetVersionInfo(BaseModel):
    """Dataset version and provenance information loaded from the manifest."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    git_commit: str | None = Field(
        default=None, description="Git commit hash when the snapshot was generated."
    )
    generated_at: str | None = Field(
        default=None, description="ISO timestamp of snapshot generation."
    )
    parquet_path: str = Field(description="Filesystem path of the Parquet snapshot.")
    manifest_path: str | None = Field(
        default=None, description="Filesystem path of provenance manifest."
    )
    parquet_sha256: str | None = Field(
        default=None, description="SHA256 checksum of the Parquet snapshot."
    )
    total_rows: int = Field(default=0, description="Total rows in the snapshot.")
    raw_rebuild_rows: int = Field(default=0, description="Rows rebuilt from raw sources.")
    canonical_legacy_rows: int = Field(
        default=0, description="Rows carried from legacy canonical data."
    )
    flags: dict[str, int] = Field(default_factory=dict, description="Quality flag counts.")
    source_policy: dict[str, list[str]] = Field(
        default_factory=dict, description="Mapping of source policies to dataset families."
    )


class ExperimentStore:
    """Thread-safe, read-only DuckDB store querying the validated Parquet snapshot.

    Maintains one master DuckDB connection and creates a fresh cursor for each
    query request to avoid serializing queries across threads.
    """

    def __init__(
        self,
        parquet_path: Path | str | None = None,
        manifest_path: Path | str | None = None,
        *,
        settings: Settings | None = None,
    ) -> None:
        cfg = settings or get_settings()
        self.parquet_path = Path(parquet_path) if parquet_path else cfg.dataset_output_path
        self.manifest_path = Path(manifest_path) if manifest_path else cfg.provenance_manifest_path

        if not self.parquet_path.is_file():
            raise FileNotFoundError(f"Parquet snapshot not found: {self.parquet_path}")

        self._table_name = "experiments"
        if duckdb is not None:
            # Open one DuckDB connection in memory and create a read-only view over Parquet
            self._conn: Any = duckdb.connect(database=":memory:")
            parquet_posix = self.parquet_path.as_posix()
            self._conn.execute(
                f"CREATE VIEW {self._table_name} AS SELECT * FROM read_parquet('{parquet_posix}')"
            )
        else:
            self._conn = _SQLiteCompatConn(self.parquet_path, table_name=self._table_name)

        # Load dataset version information from the provenance manifest
        self._dataset_version = self._load_manifest_version()
        self._catalog: FieldCatalog | None = None

    def _load_manifest_version(self) -> DatasetVersionInfo:
        """Load and parse provenance manifest metadata if available."""
        if not self.manifest_path.is_file():
            # If no manifest, count rows directly from DuckDB
            cur = self._conn.cursor()
            try:
                res = cur.execute(f"SELECT COUNT(*) FROM {self._table_name}").fetchone()
                row_count = int(res[0]) if res is not None else 0
            finally:
                cur.close()

            return DatasetVersionInfo(
                parquet_path=str(self.parquet_path),
                total_rows=row_count,
            )

        try:
            with self.manifest_path.open("r", encoding="utf-8") as f:
                data: dict[str, Any] = json.load(f)
        except Exception:
            return DatasetVersionInfo(
                parquet_path=str(self.parquet_path),
                manifest_path=str(self.manifest_path),
            )

        row_counts = data.get("row_counts", {})
        total_rows = int(row_counts.get("total", 0))
        raw_rebuild_rows = int(row_counts.get("raw_rebuild", 0))
        canonical_legacy_rows = int(row_counts.get("canonical_legacy", 0))
        flags = {str(k): int(v) for k, v in data.get("flags", {}).items()}
        source_policy = {
            str(k): [str(x) for x in v]
            for k, v in data.get("source_policy", {}).items()
            if isinstance(v, list)
        }

        # Look up parquet sha256 if present in outputs section
        outputs = data.get("outputs", {})
        sha256_val = outputs.get("parquet_sha256") if isinstance(outputs, dict) else None

        return DatasetVersionInfo(
            git_commit=data.get("git_commit"),
            generated_at=data.get("generated_at"),
            parquet_path=str(self.parquet_path),
            manifest_path=str(self.manifest_path),
            parquet_sha256=sha256_val,
            total_rows=total_rows,
            raw_rebuild_rows=raw_rebuild_rows,
            canonical_legacy_rows=canonical_legacy_rows,
            flags=flags,
            source_policy=source_policy,
        )

    @property
    def dataset_version(self) -> DatasetVersionInfo:
        """Structured version and provenance metadata from the manifest."""
        return self._dataset_version

    @property
    def catalog(self) -> FieldCatalog:
        """Cached field catalog describing all snapshot columns, types, and values."""
        if self._catalog is None:
            cur = self.get_cursor()
            try:
                self._catalog = build_field_catalog(cur, table_name=self._table_name)
            finally:
                cur.close()
        return self._catalog

    def get_cursor(self) -> Any:
        """Create a fresh cursor from the underlying connection."""
        return self._conn.cursor()

    def execute_plan(self, plan: QueryPlan) -> RetrievalResult:
        """Execute a QueryPlan using a fresh cursor per request."""
        cur = self.get_cursor()
        try:
            return execute_plan(cur, plan, table_name=self._table_name)
        except Exception as err:
            db_err = (duckdb.Error, RuntimeError) if duckdb is not None else (sqlite3.Error, RuntimeError)
            if isinstance(err, db_err):
                raise ExecutionError(f"Database execution failed: {err}") from err
            raise
        finally:
            cur.close()

    def close(self) -> None:
        """Close the underlying DuckDB connection."""
        self._conn.close()

    def __enter__(self) -> ExperimentStore:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self.close()


__all__ = [
    "DatasetVersionInfo",
    "ExperimentStore",
]
