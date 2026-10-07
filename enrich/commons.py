"""Thumbnails, credit and license for Wikimedia Commons files.

Wikipedia and Wikidata point to a Commons file; Commons' imageinfo API returns an 800 px thumbnail
URL (JPEG/PNG even for SVG or TIFF originals) plus the artist and license needed to credit it.
"""

import asyncio
import html
import logging
import random
import re
from dataclasses import dataclass
from typing import Any

import aiohttp

from enrich.licenses import is_allowed, normalise_license
from enrich.wikipedia import HEADERS

logger = logging.getLogger(__name__)

API = "https://commons.wikimedia.org/w/api.php"
BATCH_SIZE = 50  # imageinfo accepts up to 50 titles per request
MAX_CONCURRENT = 1
MAX_RETRIES = 5
THUMB_WIDTH = 800

_TAG = re.compile(r"<[^>]+>")


@dataclass
class ImageInfo:
    image_url: str  # thumbnail to display
    page_url: str  # where the credit links to
    credit: str | None
    license: str
    license_url: str | None


def plain_text(value: str | None, limit: int = 200) -> str | None:
    """Strip the HTML Commons puts in artist fields and collapse whitespace."""
    if not value:
        return None
    text = re.sub(r"\s+", " ", html.unescape(_TAG.sub(" ", value))).strip()
    return text[:limit] or None


def parse_imageinfo(response: dict[str, Any]) -> dict[str, ImageInfo]:
    """Map each requested file title to its ImageInfo, skipping missing files and disallowed licenses."""
    query = response.get("query", {})
    # Commons normalises titles ("File:A_b.jpg" -> "File:A b.jpg"); map back to what was asked
    renamed = {n["to"]: n["from"] for n in query.get("normalized", [])}
    found: dict[str, ImageInfo] = {}
    for page in query.get("pages", {}).values():
        info = (page.get("imageinfo") or [None])[0]
        if not info or "missing" in page:
            continue
        meta = info.get("extmetadata", {})
        label = normalise_license(
            meta.get("LicenseShortName", {}).get("value") or meta.get("LicenseUrl", {}).get("value")
        )
        if not is_allowed(label) or not info.get("thumburl"):
            continue
        title = str(renamed.get(page["title"]) or page["title"])
        found[title.removeprefix("File:")] = ImageInfo(
            image_url=info["thumburl"],
            page_url=info.get("descriptionurl") or f"https://commons.wikimedia.org/wiki/{page['title']}",
            credit=plain_text(meta.get("Artist", {}).get("value")) or plain_text(meta.get("Credit", {}).get("value")),
            license=label or "",
            license_url=meta.get("LicenseUrl", {}).get("value"),
        )
    return found


async def _query_batch(
    titles: list[str],
    session: aiohttp.ClientSession,
    semaphore: asyncio.Semaphore,
) -> dict[str, ImageInfo] | None:
    """ImageInfo for a batch of files, or None if Commons didn't answer after retries.

    POST, one request at a time: concurrent requests got empty or error answers (2026-10-07),
    which used to read as "no usable image".
    """
    data = {
        "action": "query",
        "format": "json",
        "prop": "imageinfo",
        "iiprop": "url|extmetadata",
        "iiurlwidth": str(THUMB_WIDTH),
        "iiextmetadatafilter": "Artist|Credit|LicenseShortName|LicenseUrl",
        "titles": "|".join(f"File:{t}" for t in titles),
    }
    async with semaphore:
        backoff = 2.0
        for _attempt in range(MAX_RETRIES + 1):
            try:
                await asyncio.sleep(random.uniform(0.2, 0.5))
                async with session.post(API, data=data) as resp:
                    body = await resp.json(content_type=None) if resp.status == 200 else None
                    retry_after = resp.headers.get("Retry-After")
                if isinstance(body, dict) and "query" in body and "error" not in body:
                    return parse_imageinfo(body)
                wait = max(backoff, float(retry_after)) if retry_after and retry_after.isdigit() else backoff
                logger.debug("Commons batch failed (status %s), retrying in %.0fs", resp.status, wait)
                await asyncio.sleep(wait + random.uniform(0, 1))
            except (aiohttp.ClientError, TimeoutError, ValueError):
                await asyncio.sleep(backoff)
            backoff *= 2
        return None


async def get_commons_images(file_titles: list[str]) -> tuple[dict[str, ImageInfo], set[str]]:
    """ImageInfo for each Commons file the app may show, and the files whose lookup failed.

    A file in neither was found but has no allowed license or no thumbnail.
    """
    unique = list(dict.fromkeys(file_titles))
    semaphore = asyncio.Semaphore(MAX_CONCURRENT)
    found: dict[str, ImageInfo] = {}
    failed: set[str] = set()
    async with aiohttp.ClientSession(headers=HEADERS) as session:
        batches = [unique[i : i + BATCH_SIZE] for i in range(0, len(unique), BATCH_SIZE)]
        results = await asyncio.gather(*(_query_batch(b, session, semaphore) for b in batches))
    for batch, result in zip(batches, results, strict=True):
        if result is None:
            failed.update(batch)
        else:
            found.update(result)
    logger.info(
        "Commons: %d/%d files usable (allowed license, thumbnail), %d lookups failed",
        len(found),
        len(unique),
        len(failed),
    )
    return found, failed
