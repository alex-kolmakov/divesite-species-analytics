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

# Download 16 files at once, process in batches
DOWNLOAD_WORKERS = 16
# OBIS_BATCH_SIZE: 1 for local dev (fast feedback), 5+ for Cloud Run
BATCH_SIZE = int(os.environ.get("OBIS_BATCH_SIZE", "1"))


def _download_batch(keys: list[str], download_dir: str) -> list[str]:
    """Download a batch of S3 files in parallel. Returns local paths."""

    def _dl(key: str) -> str:
        local_file = os.path.join(download_dir, key.rsplit("/", 1)[-1])
        client = boto3.client("s3", region_name="us-east-1",
                              config=BotoConfig(signature_version=UNSIGNED))
        client.download_file(S3_BUCKET, key, local_file)
        return local_file

    paths = []
    with ThreadPoolExecutor(max_workers=DOWNLOAD_WORKERS) as pool:
        futures = {pool.submit(_dl, key): key for key in keys}
        for future in as_completed(futures):
            try:
                paths.append(future.result())
            except Exception as e:
                logger.warning("Download failed %s: %s", futures[future], e)
    return paths


def ingest_obis(config: Config) -> None:
    """Download OBIS parquet from S3 in parallel batches, process with DuckDB."""
    os.makedirs(config.temp_dir, exist_ok=True)
    output_path = os.path.join(config.temp_dir, "obis.parquet")
    download_dir = os.path.join(config.temp_dir, "obis_dl")
    parts_dir = os.path.join(config.temp_dir, "obis_parts")
    os.makedirs(download_dir, exist_ok=True)
    os.makedirs(parts_dir, exist_ok=True)

    columns_sql = ", ".join(OBIS_COLUMNS)
    where_clause = (
        "WHERE interpreted.species IS NOT NULL"
        " AND interpreted.decimalLatitude IS NOT NULL"
        " AND interpreted.decimalLongitude IS NOT NULL"
    )

    # --- Phase 1: List S3 objects ---
    logger.info("Listing OBIS parquet files on S3...")
    s3 = boto3.client("s3", region_name="us-east-1",
                      config=BotoConfig(signature_version=UNSIGNED))
    paginator = s3.get_paginator("list_objects_v2")
    keys = []
    for page in paginator.paginate(Bucket=S3_BUCKET, Prefix=S3_PREFIX):
        for obj in page.get("Contents", []):
            if obj["Key"].endswith(".parquet"):
                keys.append(obj["Key"])
    keys.sort()
    total_files = len(keys)
    batches = [keys[i:i + BATCH_SIZE] for i in range(0, total_files, BATCH_SIZE)]
    logger.info("Found %d files, split into %d batches of %d",
                total_files, len(batches), BATCH_SIZE)

    # --- Phase 2: Download batch → process → delete, repeat ---
    t_start = time.time()
    total_rows = 0
    total_downloaded = 0

    for batch_idx, batch_keys in enumerate(batches):
        t_batch = time.time()

        # Download this batch in parallel
        local_files = _download_batch(batch_keys, download_dir)
        total_downloaded += len(local_files)
        dl_time = time.time() - t_batch

        if not local_files:
            logger.warning("Batch %d: no files downloaded, skipping", batch_idx)
            continue

        # Process with DuckDB → part file
        part_path = os.path.join(parts_dir, f"part_{batch_idx:04d}.parquet")
        con = duckdb.connect()
        con.sql(f"SET temp_directory = '{config.temp_dir}';")

        file_list = [str(f) for f in local_files]
        result = con.sql(
            f"SELECT COUNT(*) FROM (SELECT {columns_sql} FROM read_parquet($1) {where_clause})",
            params=[file_list],
        ).fetchone()
        rows = result[0]

        con.sql(
            f"COPY (SELECT {columns_sql} FROM read_parquet($1) {where_clause}) "
            f"TO '{part_path}' (FORMAT PARQUET, CODEC 'ZSTD')",
            params=[file_list],
        )
        con.close()
        total_rows += rows
        proc_time = time.time() - t_batch - dl_time

        # Delete raw files to free disk
        for f in local_files:
            Path(f).unlink(missing_ok=True)

        part_mb = Path(part_path).stat().st_size / 1_000_000
        elapsed = time.time() - t_start
        logger.info(
            "Batch %d/%d: %d files -> %d rows (%.1f MB) | "
            "dl=%.0fs proc=%.0fs | %d/%d files done, %d total rows, %.0fs elapsed",
            batch_idx + 1, len(batches), len(local_files), rows, part_mb,
            dl_time, proc_time, total_downloaded, total_files, total_rows, elapsed,
        )

    # --- Phase 3: Merge parts ---
    part_files = sorted(Path(parts_dir).glob("*.parquet"))
    logger.info("Merging %d parts into final parquet...", len(part_files))
    merge_con = duckdb.connect()
    merge_con.sql(f"SET temp_directory = '{config.temp_dir}';")
    part_list = [str(p) for p in part_files]
    merge_con.sql(
        f"COPY (SELECT * FROM read_parquet($1)) TO '{output_path}' (FORMAT PARQUET, CODEC 'ZSTD')",
        params=[part_list],
    )
    merge_con.close()

    for p in part_files:
        p.unlink(missing_ok=True)
    Path(parts_dir).rmdir()
    Path(download_dir).rmdir()

    file_mb = Path(output_path).stat().st_size / 1_000_000
    logger.info("Final: %.1f MB (%d rows)", file_mb, total_rows)

    # --- Phase 4: Upload to GCS ---
    upload_to_gcs(output_path, config.gcs_bucket, "obis.parquet", project=config.project_id)
    Path(output_path).unlink(missing_ok=True)

    total_elapsed = time.time() - t_start
    logger.info("OBIS ingestion complete in %.0fs", total_elapsed)
