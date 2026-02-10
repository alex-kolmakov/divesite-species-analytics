import logging
import os
from datetime import datetime
from pathlib import Path

from ingest.config import Config
from ingest.download import download
from ingest.dwca import parse_dwca_to_parquet
from ingest.upload import upload_to_gcs

logger = logging.getLogger(__name__)


def ingest_worms(config: Config) -> None:
    """Download WoRMS DwCA (authenticated), convert to parquet, upload to GCS."""
    os.makedirs(config.temp_dir, exist_ok=True)
    zip_path = os.path.join(config.temp_dir, "worms.zip")
    parquet_path = os.path.join(config.temp_dir, "worms.parquet")

    # Format URL template with current date
    now = datetime.now()
    url = config.worms_url_template.replace("{year}", str(now.year)).replace("{full_date}", now.strftime("%Y-%m-01"))

    auth = None
    if config.worms_login and config.worms_password:
        auth = (config.worms_login, config.worms_password)

    download(url, zip_path, auth=auth)
    parse_dwca_to_parquet(zip_path, parquet_path)
    upload_to_gcs(parquet_path, config.gcs_bucket, "worms.parquet", project=config.project_id)

    for f in [zip_path, parquet_path]:
        Path(f).unlink(missing_ok=True)

    logger.info("WoRMS ingestion complete")
