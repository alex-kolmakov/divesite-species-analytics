import logging
import os
from datetime import datetime
from pathlib import Path

from dateutil.relativedelta import relativedelta

from ingest.config import Config
from ingest.download import download
from ingest.dwca import parse_dwca_to_parquet
from ingest.upload import upload_to_gcs

logger = logging.getLogger(__name__)


def _build_worms_url(template: str, date: datetime) -> str:
    """Build WoRMS download URL for a given month."""
    return template.replace("{year}", str(date.year)).replace("{full_date}", date.strftime("%Y-%m-01"))


def ingest_worms(config: Config) -> None:
    """Download WoRMS DwCA (authenticated), convert to parquet, upload to GCS."""
    os.makedirs(config.temp_dir, exist_ok=True)
    zip_path = os.path.join(config.temp_dir, "worms.zip")
    parquet_path = os.path.join(config.temp_dir, "worms.parquet")

    auth = None
    if config.worms_login and config.worms_password:
        auth = (config.worms_login, config.worms_password)

    # Try current month, then previous months (WoRMS may not have this month's export yet)
    now = datetime.now()
    candidates = [now - relativedelta(months=i) for i in range(4)]
    downloaded = False
    for date in candidates:
        url = _build_worms_url(config.worms_url_template, date)
        logger.info("Trying WoRMS URL: %s", url)
        try:
            download(url, zip_path, auth=auth)
            downloaded = True
            break
        except Exception as e:
            logger.warning("WoRMS %s failed: %s", date.strftime("%Y-%m"), e)

    if not downloaded:
        raise RuntimeError("Could not download WoRMS from any recent month")

    parse_dwca_to_parquet(zip_path, parquet_path)
    upload_to_gcs(parquet_path, config.gcs_bucket, "worms.parquet", project=config.project_id)

    for f in [zip_path, parquet_path]:
        Path(f).unlink(missing_ok=True)

    logger.info("WoRMS ingestion complete")
