import logging
import os
from pathlib import Path

import duckdb

from ingest.config import Config
from ingest.upload import upload_to_gcs

logger = logging.getLogger(__name__)

# S3 bucket with OBIS open data (public, no credentials needed)
OBIS_S3_PATTERN = "s3://obis-open-data/occurrence/*.parquet"

# Columns to extract from the nested 'interpreted' struct
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


def ingest_obis(config: Config) -> None:
    """Query OBIS open data from S3, process with DuckDB, upload to GCS."""
    os.makedirs(config.temp_dir, exist_ok=True)
    output_path = os.path.join(config.temp_dir, "obis.parquet")

    columns_sql = ", ".join(OBIS_COLUMNS)

    logger.info("Querying OBIS data from S3 with DuckDB (memory_limit=2GB)")
    con = duckdb.connect()
    con.sql("INSTALL httpfs; LOAD httpfs;")
    con.sql("SET s3_region = 'us-east-1';")
    con.sql("PRAGMA memory_limit = '2GB';")

    query = f"""
    COPY (
        SELECT {columns_sql}
        FROM read_parquet('{OBIS_S3_PATTERN}')
        WHERE interpreted.species IS NOT NULL
          AND interpreted.decimalLatitude IS NOT NULL
          AND interpreted.decimalLongitude IS NOT NULL
    ) TO '{output_path}' (FORMAT PARQUET, CODEC 'ZSTD');
    """
    con.sql(query)
    con.close()

    result = duckdb.query(f"SELECT COUNT(*) FROM read_parquet('{output_path}')").fetchone()
    row_count = result[0] if result else 0
    logger.info("Processed %d rows into %s", row_count, output_path)

    # Upload processed parquet to GCS
    upload_to_gcs(output_path, config.gcs_bucket, "obis.parquet", project=config.project_id)

    # Cleanup
    Path(output_path).unlink(missing_ok=True)

    logger.info("OBIS ingestion complete")
