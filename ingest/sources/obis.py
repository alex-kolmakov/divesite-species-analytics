import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import boto3
import duckdb
from botocore import UNSIGNED
from botocore.config import Config as BotoConfig

from ingest.config import Config
from ingest.upload import upload_to_gcs

logger = logging.getLogger(__name__)

S3_BUCKET = "obis-open-data"
S3_PREFIX = "occurrence/"

OBIS_COLUMNS = [
    "interpreted.species AS species",
    "interpreted.individualCount AS individualCount",
    "interpreted.eventDate AS eventDate",
    "interpreted.eventTime AS eventTime",
    "interpreted.date_year AS year",
    'interpreted."month" AS month',
    'interpreted."day" AS day',
    "interpreted.decimalLongitude AS decimalLongitude",
    "interpreted.decimalLatitude AS decimalLatitude",
]

OBIS_WHERE = (
    "WHERE interpreted.species IS NOT NULL"
    " AND interpreted.decimalLatitude IS NOT NULL"
    " AND interpreted.decimalLongitude IS NOT NULL"
)

DOWNLOAD_WORKERS = 16
BATCH_SIZE = int(os.environ.get("OBIS_BATCH_SIZE", "1"))


def _s3_client():
    return boto3.client("s3", region_name="us-east-1", config=BotoConfig(signature_version=UNSIGNED))


def _download_batch(keys: list[str], download_dir: str) -> list[str]:
    """Download S3 files in parallel with boto3. Returns local paths."""

    def _dl(key: str) -> str:
        local_path = os.path.join(download_dir, key.rsplit("/", 1)[-1])
        _s3_client().download_file(S3_BUCKET, key, local_path)
        return local_path

    paths = []
    with ThreadPoolExecutor(max_workers=DOWNLOAD_WORKERS) as pool:
        futures = {pool.submit(_dl, key): key for key in keys}
        for future in as_completed(futures):
            try:
                paths.append(future.result())
            except Exception as e:
                logger.warning("Download failed %s: %s", futures[future], e)
    return paths


def _list_s3_keys() -> list[str]:
    """List all parquet file keys in the OBIS S3 bucket."""
    paginator = _s3_client().get_paginator("list_objects_v2")
    keys = [
        obj["Key"]
        for page in paginator.paginate(Bucket=S3_BUCKET, Prefix=S3_PREFIX)
        for obj in page.get("Contents", [])
        if obj["Key"].endswith(".parquet")
    ]
    keys.sort()
    return keys


def ingest_obis(config: Config) -> None:
    """Download OBIS parquet from S3 in parallel batches, process with DuckDB."""
    download_dir = os.path.join(config.temp_dir, "obis_dl")
    parts_dir = os.path.join(config.temp_dir, "obis_parts")
    output_path = os.path.join(config.temp_dir, "obis.parquet")
    for d in [download_dir, parts_dir]:
        os.makedirs(d, exist_ok=True)

    columns_sql = ", ".join(OBIS_COLUMNS)
    select_query = f"SELECT {columns_sql} FROM read_parquet($1) {OBIS_WHERE}"

    # Phase 1: List S3 objects
    logger.info("Listing OBIS parquet files on S3...")
    keys = _list_s3_keys()
    batches = [keys[i : i + BATCH_SIZE] for i in range(0, len(keys), BATCH_SIZE)]
    logger.info("Found %d files → %d batches of %d", len(keys), len(batches), BATCH_SIZE)

    # Phase 2: Download → process → delete per batch
    t_start = time.time()
    total_downloaded = 0

    for batch_idx, batch_keys in enumerate(batches):
        t_batch = time.time()

        local_files = _download_batch(batch_keys, download_dir)
        total_downloaded += len(local_files)
        dl_time = time.time() - t_batch

        if not local_files:
            logger.warning("Batch %d: no files downloaded, skipping", batch_idx)
            continue

        part_path = os.path.join(parts_dir, f"part_{batch_idx:04d}.parquet")
        con = duckdb.connect()
        con.sql(f"SET temp_directory = '{config.temp_dir}';")
        con.sql(f"COPY ({select_query}) TO '{part_path}' (FORMAT PARQUET, CODEC 'ZSTD')", params=[local_files])
        con.close()

        for f in local_files:
            Path(f).unlink(missing_ok=True)

        part_mb = Path(part_path).stat().st_size / 1_000_000
        elapsed = time.time() - t_start
        logger.info(
            "Batch %d/%d: %d files → %.1f MB | dl=%.0fs | %d/%d done, %.0fs elapsed",
            batch_idx + 1,
            len(batches),
            len(local_files),
            part_mb,
            dl_time,
            total_downloaded,
            len(keys),
            elapsed,
        )

    # Phase 3: Merge parts
    part_files = sorted(Path(parts_dir).glob("*.parquet"))
    logger.info("Merging %d parts...", len(part_files))
    con = duckdb.connect()
    con.sql(f"SET temp_directory = '{config.temp_dir}';")
    con.sql(
        "COPY (SELECT * FROM read_parquet($1)) TO $2 (FORMAT PARQUET, CODEC 'ZSTD')",
        params=[[str(p) for p in part_files], output_path],
    )
    con.close()

    for p in part_files:
        p.unlink(missing_ok=True)
    Path(parts_dir).rmdir()
    Path(download_dir).rmdir()

    file_mb = Path(output_path).stat().st_size / 1_000_000
    logger.info("Final: %.1f MB", file_mb)

    # Phase 4: Upload to GCS
    upload_to_gcs(output_path, config.gcs_bucket, "obis.parquet", project=config.project_id)
    Path(output_path).unlink(missing_ok=True)

    logger.info("OBIS ingestion complete in %.0fs", time.time() - t_start)
