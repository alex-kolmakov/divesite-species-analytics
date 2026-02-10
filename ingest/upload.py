import logging
from pathlib import Path

from google.cloud import storage

logger = logging.getLogger(__name__)


def upload_to_gcs(
    local_path: str | Path,
    bucket_name: str,
    gcs_path: str,
    project: str | None = None,
    chunk_size: int = 5 * 1024 * 1024,
) -> None:
    """Upload a file to GCS with chunked resumable upload."""
    local_path = Path(local_path)
    if not local_path.exists():
        raise FileNotFoundError(f"File not found: {local_path}")

    size_mb = local_path.stat().st_size / (1024 * 1024)
    logger.info("Uploading %s (%.1f MB) -> gs://%s/%s", local_path, size_mb, bucket_name, gcs_path)

    client = storage.Client(project=project)
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(gcs_path)
    blob.chunk_size = chunk_size

    blob.upload_from_filename(str(local_path))

    logger.info("Upload complete: gs://%s/%s", bucket_name, gcs_path)
