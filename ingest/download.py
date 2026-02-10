import logging
from pathlib import Path

import requests
from tqdm import tqdm

logger = logging.getLogger(__name__)


def download(
    url: str,
    filename: str | Path,
    auth: tuple[str, str] | None = None,
    chunk_size: int = 8192,
    progress_update_threshold: int = 1024 * 1024 * 10,
) -> Path:
    """Stream-download a file with progress reporting."""
    filepath = Path(filename)
    filepath.parent.mkdir(parents=True, exist_ok=True)

    logger.info("Downloading %s -> %s", url, filepath)

    with open(filepath, "wb") as f, requests.get(url, stream=True, auth=auth, timeout=300) as r:
        r.raise_for_status()
        total = int(r.headers.get("content-length", 0))

        tqdm_params = {
            "desc": url.split("/")[-1],
            "total": total or None,
            "unit": "B",
            "unit_scale": True,
            "unit_divisor": 1024,
        }
        total_downloaded = 0
        last_update = 0

        with tqdm(**tqdm_params) as pb:
            for chunk in r.iter_content(chunk_size=chunk_size):
                f.write(chunk)
                total_downloaded += len(chunk)
                if total_downloaded - last_update >= progress_update_threshold:
                    pb.update(total_downloaded - last_update)
                    last_update = total_downloaded

            # Flush remaining progress
            if total_downloaded > last_update:
                pb.update(total_downloaded - last_update)

        if total and total_downloaded != total:
            raise ValueError(f"Size mismatch: expected {total} bytes, got {total_downloaded}")

    logger.info("Downloaded %d bytes to %s", total_downloaded, filepath)
    return filepath
