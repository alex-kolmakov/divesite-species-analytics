import asyncio
import json
import logging
import os
import re
from pathlib import Path
from typing import Any

import aiohttp
import pandas as pd
import requests

from ingest.config import Config
from ingest.upload import upload_to_gcs

logger = logging.getLogger(__name__)

SESSION_URL = "https://www.divessi.com/en/locator/divesites"
API_URL = "https://www.divessi.com/api/locationServices.php"
MULTIPART_BOUNDARY = "----WB"
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"

TILE_SIZE = 30  # degrees — 72 tiles cover the globe; subdivide saturated tiles
MAX_CONCURRENT = 4  # cap parallel requests to avoid rate limiting
SATURATION_LIMIT = 1000  # SSI caps tile results at this count


def _acquire_credentials() -> tuple[str, str]:
    """GET the SSI locator page and return a paired (PHPSESSID, ssi_auth_token).

    Both credentials must come from the same page load — a token from one session
    will not authenticate requests made with a PHPSESSID from another session.
    """
    session = requests.Session()
    resp = session.get(SESSION_URL, headers={"user-agent": USER_AGENT}, timeout=30)
    resp.raise_for_status()

    phpsessid = session.cookies.get("PHPSESSID")
    if not phpsessid:
        raise ValueError("PHPSESSID not found in SSI session cookies")

    match = re.search(r"SSI_APIKEY\s*=\s*'([^']+)'", resp.text)
    if not match:
        raise ValueError("SSI_APIKEY not found in page HTML — page structure may have changed")

    auth_token = match.group(1)
    logger.info("Acquired SSI credentials (session=%s…)", phpsessid[:8])
    return phpsessid, auth_token


def _make_tile_body(south: float, west: float, north: float, east: float) -> str:
    """Build the multipart/form-data body for a single tile request."""
    payload = json.dumps(
        {
            "type": "BOUNDS_CHANGED",
            "filter": {
                "targets": ["DiveSites"],
                "geoBounds": {"south": south, "west": west, "north": north, "east": east},
                "viewportCenter": {"lat": (south + north) / 2, "lng": (west + east) / 2},
            },
        }
    )
    return f'------WB\r\nContent-Disposition: form-data; name="request"\r\n\r\n{payload}\r\n------WB--\r\n'


def _extract_sites(response: dict[str, Any]) -> list[dict[str, Any]]:
    """Flatten site properties and text from a tile response into records."""
    elements = response.get("result", {}).get("elements", [])
    sites = []
    for el in elements:
        if el.get("ident") != "divesite":
            continue
        data = el.get("data", {})
        props = data.get("properties", {})
        text = data.get("text", {})
        sites.append({**props, **text})
    return sites


async def _fetch_tile(
    session: aiohttp.ClientSession,
    sem: asyncio.Semaphore,
    phpsessid: str,
    auth_token: str,
    south: float,
    west: float,
    north: float,
    east: float,
) -> dict[str, Any]:
    headers = {
        "content-type": f"multipart/form-data; boundary={MULTIPART_BOUNDARY}",
        "x-ssi-auth": auth_token,
        "Cookie": f"PHPSESSID={phpsessid}",
        "origin": "https://www.divessi.com",
        "referer": SESSION_URL,
        "user-agent": USER_AGENT,
    }
    async with sem:
        await asyncio.sleep(0.1)  # light throttle to avoid rate limiting
        async with session.post(API_URL, data=_make_tile_body(south, west, north, east), headers=headers) as resp:
            return await resp.json(content_type=None)


async def _fetch_all_tiles(
    phpsessid: str,
    auth_token: str,
    initial_tiles: list[tuple[float, float, float, float]],
) -> list[dict[str, Any]]:
    """Fetch all tiles iteratively, subdividing any that hit the 1000-result cap."""
    sem = asyncio.Semaphore(MAX_CONCURRENT)
    all_sites: list[dict[str, Any]] = []
    pending = list(initial_tiles)
    round_num = 1

    async with aiohttp.ClientSession() as session:
        while pending:
            logger.info("SSI round %d: fetching %d tile(s)", round_num, len(pending))
            tasks = [_fetch_tile(session, sem, phpsessid, auth_token, s, w, n, e) for s, w, n, e in pending]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            next_pending: list[tuple[float, float, float, float]] = []
            for tile, result in zip(pending, results, strict=True):
                s, w, n, e = tile
                if not isinstance(result, dict):
                    logger.warning("Tile (%.0f,%.0f)→(%.0f,%.0f) error: %s", s, w, n, e, result)
                    continue

                total = result.get("stats", {}).get("total", 0)
                sites = _extract_sites(result)

                if total >= SATURATION_LIMIT:
                    # Tile is capped — split into 4 sub-tiles and retry
                    mid_lat = (s + n) / 2
                    mid_lng = (w + e) / 2
                    next_pending.extend(
                        [
                            (s, w, mid_lat, mid_lng),
                            (s, mid_lng, mid_lat, e),
                            (mid_lat, w, n, mid_lng),
                            (mid_lat, mid_lng, n, e),
                        ]
                    )
                    logger.info(
                        "Tile (%.0f,%.0f)→(%.0f,%.0f) saturated (%d results) — subdividing into 4",
                        s,
                        w,
                        n,
                        e,
                        total,
                    )
                else:
                    all_sites.extend(sites)
                    logger.debug("Tile (%.0f,%.0f)→(%.0f,%.0f): %d sites", s, w, n, e, len(sites))

            pending = next_pending
            round_num += 1

    return all_sites


async def _get_ssi_divesites() -> pd.DataFrame:
    phpsessid, auth_token = _acquire_credentials()

    tiles: list[tuple[float, float, float, float]] = [
        (float(lat), float(lon), float(lat + TILE_SIZE), float(lon + TILE_SIZE))
        for lat in range(-90, 90, TILE_SIZE)
        for lon in range(-180, 180, TILE_SIZE)
    ]
    logger.info("SSI: %d initial tiles at %d°×%d° resolution", len(tiles), TILE_SIZE, TILE_SIZE)

    sites = await _fetch_all_tiles(phpsessid, auth_token, tiles)

    if not sites:
        logger.warning("SSI: no sites fetched — returning empty DataFrame")
        return pd.DataFrame()

    df = pd.DataFrame(sites)
    before = len(df)
    df = df.drop_duplicates(subset=["id"])
    logger.info("SSI: %d unique dive sites (from %d raw records)", len(df), before)
    return df


def ingest_ssi(config: Config) -> None:
    """Fetch all SSI dive sites, write to Parquet, and upload to GCS."""
    os.makedirs(config.temp_dir, exist_ok=True)
    parquet_path = os.path.join(config.temp_dir, "ssi_divesites.parquet")

    df = asyncio.run(_get_ssi_divesites())

    df.to_parquet(parquet_path, engine="pyarrow", compression="snappy", index=False)
    logger.info("Wrote %d SSI dive sites to %s", len(df), parquet_path)

    upload_to_gcs(parquet_path, config.gcs_bucket, "ssi_divesites.parquet", project=config.project_id)

    Path(parquet_path).unlink(missing_ok=True)
    logger.info("SSI dive sites ingestion complete")
