import asyncio
import logging
import os
from pathlib import Path
from typing import Any

import aiohttp
import pandas as pd

from ingest.config import Config
from ingest.upload import upload_to_gcs

logger = logging.getLogger(__name__)


async def _fetch_json(
    session: aiohttp.ClientSession,
    url: str,
    datakey: str | None = None,
) -> tuple[int, Any]:
    """Fetch JSON from a URL, optionally extracting a sub-key."""
    async with session.get(url) as response:
        data = await response.json()
        extracted = data[datakey] if datakey and datakey in data else data
        return response.status, extracted


async def _fetch_all_guide_data(
    session: aiohttp.ClientSession,
    base_url: str,
) -> list[dict[str, Any]]:
    """Fetch paginated dive guide data until 404 or empty."""
    all_data: list[dict[str, Any]] = []
    page = 1
    while True:
        url = f"{base_url}?page={page}&page_size=1000"
        status, data = await _fetch_json(session, url, datakey="results")
        if status == 404 or not data:
            break
        logger.info("Guide page %d: %d results", page, len(data))
        all_data.extend(data)
        page += 1
    return all_data


async def _fetch_map_segment(
    session: aiohttp.ClientSession,
    base_url: str,
    top_right: str,
    bottom_left: str,
) -> tuple[int, Any]:
    """Fetch a single map grid segment."""
    url = f"{base_url}?top_right={top_right}&bottom_left={bottom_left}"
    return await _fetch_json(session, url)


async def _get_divesites(
    guide_url: str,
    map_url: str,
) -> pd.DataFrame:
    """Fetch all dive sites by combining guide and map APIs."""
    lat_size = 20
    lon_size = 20

    async with aiohttp.ClientSession() as session:
        guide_data = await _fetch_all_guide_data(session, guide_url)
        logger.info("Fetched %d guide records", len(guide_data))

        segments = [
            (f"{lat + lat_size},{lon + lon_size}", f"{lat},{lon}")
            for lat in range(-90, 90, lat_size)
            for lon in range(-340, 340, lon_size)
        ]
        logger.info("Fetching %d map segments", len(segments))

        tasks = [_fetch_map_segment(session, map_url, tr, bl) for tr, bl in segments]
        map_results = await asyncio.gather(*tasks)

    # Merge guide and map data
    map_records = []
    for _, data in map_results:
        if isinstance(data, list):
            map_records.extend(data)

    map_df = pd.DataFrame(map_records)
    guide_df = pd.DataFrame(guide_data)

    merged = pd.merge(map_df, guide_df, on="id", how="outer")

    # Clean: drop rows without essential fields, drop images column
    merged = merged.dropna(subset=["latitude", "longitude", "title"])
    if "images" in merged.columns:
        merged = merged.drop(columns=["images"])

    logger.info("Merged dive sites: %d rows", len(merged))
    return merged


def ingest_divesites(config: Config) -> None:
    """Scrape PADI dive sites, write to parquet, upload to GCS."""
    os.makedirs(config.temp_dir, exist_ok=True)
    parquet_path = os.path.join(config.temp_dir, "divesites.parquet")

    df = asyncio.run(_get_divesites(config.base_padi_guide_url, config.base_padi_map_url))

    df.to_parquet(parquet_path, engine="pyarrow", compression="snappy", index=False)
    logger.info("Wrote %d dive sites to %s", len(df), parquet_path)

    upload_to_gcs(parquet_path, config.gcs_bucket, "divesites.parquet", project=config.project_id)

    Path(parquet_path).unlink(missing_ok=True)
    logger.info("Divesites ingestion complete")
