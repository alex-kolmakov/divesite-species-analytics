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
) -> Path:
    """Stream-download a file with progress reporting."""
    filepath = Path(filename)
    filepath.parent.mkdir(parents=True, exist_ok=True)

    logger.info("Downloading %s -> %s", url, filepath)

    with open(filepath, "wb") as f, requests.get(url, stream=True, auth=auth, timeout=300) as r:
        r.raise_for_status()
        total = int(r.headers.get("content-length", 0))

        with tqdm(desc=url.split("/")[-1], total=total or None, unit="B", unit_scale=True, unit_divisor=1024) as pb:
            for chunk in r.iter_content(chunk_size=chunk_size):
                f.write(chunk)
                pb.update(len(chunk))

        if total and pb.n != total:
            raise ValueError(f"Size mismatch: expected {total} bytes, got {pb.n}")

    logger.info("Downloaded %.1f MB to %s", pb.n / 1_000_000, filepath)
    return filepath
