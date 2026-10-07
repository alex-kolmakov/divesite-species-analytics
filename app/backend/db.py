"""DuckDB in-memory database — loads Parquet from GCS or local files at startup."""

import logging
import tempfile
from pathlib import Path

import duckdb

from .config import config

logger = logging.getLogger(__name__)

# Module-level connection — initialised by `init_db()` during app lifespan.
_conn: duckdb.DuckDBPyConnection | None = None

# Tables live in a compressed in-memory catalog: ~80 MB instead of ~570 MB uncompressed for the
# 4M (site, species) rows. The memory limit and two threads keep the parquet load under ~360 MB
# (measured 2026-10-06), so it fits a small Cloud Run instance.
CATALOG = "app"
MEMORY_LIMIT = "300MB"
THREADS = 2


def get_conn() -> duckdb.DuckDBPyConnection:
    """Return a per-call cursor for thread-safe concurrent reads."""
    if _conn is None:
        raise RuntimeError("Database not initialised — call init_db() first")
    cur = _conn.cursor()
    cur.execute(f"USE {CATALOG}")  # USE is per connection, and every cursor is a new one
    return cur


def fetch_dicts(sql: str, params: list[object] | None = None) -> list[dict]:
    """Run a query and return rows as dicts keyed by column name."""
    cur = get_conn().execute(sql, params or [])
    columns = [d[0] for d in cur.description]
    return [dict(zip(columns, row, strict=True)) for row in cur.fetchall()]


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
            # One folder per table (`bq extract` splits large tables into parts). The trailing
            # slash matters: without it "divesite_species" also matches "divesite_species_detail".
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
        files = sorted((data_dir / table).glob("*.parquet"))
        if not files:
            logger.warning("Local parquet not found: %s/*.parquet", data_dir / table)
            continue
        globs = ", ".join(f"'{p}'" for p in files)
        _conn.execute(f"CREATE TABLE {table} AS SELECT * FROM read_parquet([{globs}])")
        rows = _conn.execute(f"SELECT count(*) FROM {table}").fetchone()
        logger.info("Loaded %s: %s rows", table, rows[0] if rows else "?")


def init_db() -> None:
    """Initialise DuckDB and load all tables."""
    global _conn  # noqa: PLW0603
    _conn = duckdb.connect(":memory:")
    _conn.execute(f"SET memory_limit = '{MEMORY_LIMIT}'")
    _conn.execute(f"SET threads = {THREADS}")
    _conn.execute(f"ATTACH ':memory:' AS {CATALOG} (COMPRESS)")
    _conn.execute(f"USE {CATALOG}")
    logger.info("DuckDB initialised (compressed in-memory catalog %s)", CATALOG)

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
