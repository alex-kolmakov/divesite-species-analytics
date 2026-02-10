import logging
import os
from pathlib import Path

from ingest.config import Config
from ingest.download import download
from ingest.dwca import parse_dwca_to_parquet
from ingest.upload import upload_to_gcs

logger = logging.getLogger(__name__)


def ingest_gisd(config: Config) -> None:
    """Download GISD invasive species DwCA, convert to parquet, upload to GCS."""
    os.makedirs(config.temp_dir, exist_ok=True)
    zip_path = os.path.join(config.temp_dir, "gisd.zip")
    parquet_path = os.path.join(config.temp_dir, "invasive.parquet")

    download(config.gisd_url, zip_path)
    parse_dwca_to_parquet(zip_path, parquet_path)
    upload_to_gcs(parquet_path, config.gcs_bucket, "invasive.parquet", project=config.project_id)

    for f in [zip_path, parquet_path]:
        Path(f).unlink(missing_ok=True)

    logger.info("GISD ingestion complete")
