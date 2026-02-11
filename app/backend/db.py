"""DuckDB in-memory database — loads Parquet from GCS or local files at startup."""

import logging
import tempfile
from pathlib import Path

import duckdb

from .config import config

logger = logging.getLogger(__name__)

# Module-level connection — initialised by `init_db()` during app lifespan.
_conn: duckdb.DuckDBPyConnection | None = None


def get_conn() -> duckdb.DuckDBPyConnection:
    """Return the shared DuckDB connection (read-only queries only)."""
    if _conn is None:
        raise RuntimeError("Database not initialised — call init_db() first")
    return _conn


# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------

def _load_from_gcs() -> None:
    """Download Parquet files from GCS into DuckDB."""
    from google.cloud import storage  # lazy import — not needed in local dev

    client = storage.Client()
    bucket = client.bucket(config.gcs_bucket)
    assert _conn is not None

    with tempfile.TemporaryDirectory() as tmp:
        for table in config.tables:
            prefix = f"{config.export_prefix}/{table}/"
            blobs = list(bucket.list_blobs(prefix=prefix))
            if not blobs:
                logger.warning("No blobs found for %s (prefix=%s)", table, prefix)
                continue

            parquet_paths: list[str] = []
            for blob in blobs:
                if not blob.name.endswith(".parquet"):
                    continue
                local_path = Path(tmp) / blob.name.replace("/", "_")
                blob.download_to_filename(str(local_path))
                parquet_paths.append(str(local_path))

            if parquet_paths:
                globs = ", ".join(f"'{p}'" for p in parquet_paths)
                _conn.execute(f"CREATE TABLE {table} AS SELECT * FROM read_parquet([{globs}])")
                rows = _conn.execute(f"SELECT count(*) FROM {table}").fetchone()
                logger.info("Loaded %s: %s rows from %d files", table, rows[0] if rows else "?", len(parquet_paths))


def _load_from_local() -> None:
    """Load Parquet files from local data/ directory into DuckDB."""
    data_dir = Path(config.local_data_dir)
    assert _conn is not None

    for table in config.tables:
        path = data_dir / f"{table}.parquet"
        if not path.exists():
            logger.warning("Local parquet not found: %s", path)
            continue
        _conn.execute(f"CREATE TABLE {table} AS SELECT * FROM read_parquet('{path}')")
        rows = _conn.execute(f"SELECT count(*) FROM {table}").fetchone()
        logger.info("Loaded %s: %s rows", table, rows[0] if rows else "?")


def init_db() -> None:
    """Initialise DuckDB and load all tables."""
    global _conn  # noqa: PLW0603
    _conn = duckdb.connect(":memory:")
    logger.info("DuckDB initialised (in-memory)")

    if config.use_gcs:
        logger.info("Loading data from GCS bucket=%s prefix=%s", config.gcs_bucket, config.export_prefix)
        _load_from_gcs()
    else:
        logger.info("Loading data from local dir=%s", config.local_data_dir)
        _load_from_local()


def close_db() -> None:
    """Close DuckDB connection."""
    global _conn  # noqa: PLW0603
    if _conn is not None:
        _conn.close()
        _conn = None
        logger.info("DuckDB closed")
