import asyncio
import logging
import random
from dataclasses import dataclass
from typing import Any

import aiohttp

from enrich.licenses import is_allowed, normalise_license
from enrich.names import canonical_name
from enrich.wikipedia import UA

logger = logging.getLogger(__name__)

MAX_CONCURRENT = 20  # GBIF API is generous with rate limits
MAX_RETRIES = 3
INITIAL_BACKOFF = 2

GBIF_API = "https://api.gbif.org/v1"

HEADERS = {
    "User-Agent": UA,
}


@dataclass
class OccurrenceImage:
    image_url: str
    page_url: str  # the GBIF occurrence page, where the photo and its record live
    credit: str | None
    license: str
    license_url: str | None


async def _get_json(session: aiohttp.ClientSession, url: str, params: dict[str, Any]) -> dict[str, Any] | None:
    """GET with backoff on 429 and network errors. None on any other failure."""
    backoff = INITIAL_BACKOFF
    for _attempt in range(MAX_RETRIES + 1):
        try:
            async with session.get(url, params=params) as resp:
                if resp.status == 429:
                    await asyncio.sleep(backoff + random.uniform(0, 1))
                    backoff *= 2
                    continue
                if resp.status != 200:
                    return None
                data = await resp.json()
                return data if isinstance(data, dict) else None
        except aiohttp.ClientError:
            await asyncio.sleep(backoff)
            backoff *= 2
        except Exception:
            logger.debug("GBIF error for %s %s", url, params, exc_info=True)
            return None
    return None


async def match_species(species_names: list[str]) -> dict[str, int]:
    """GBIF usage key per species, only for exact species-rank matches."""
    semaphore = asyncio.Semaphore(MAX_CONCURRENT)

    async def one(session: aiohttp.ClientSession, name: str) -> int | None:
        async with semaphore:
            match = await _get_json(session, f"{GBIF_API}/species/match", {"name": canonical_name(name)})
        if not match or match.get("rank") != "SPECIES":
            return None
        return match.get("usageKey")

    async with aiohttp.ClientSession(headers=HEADERS) as session:
        keys = await asyncio.gather(*(one(session, n) for n in species_names))
    found = {n: k for n, k in zip(species_names, keys, strict=True) if k}
    logger.info("GBIF: matched %d/%d species", len(found), len(species_names))
    return found


async def get_common_names(usage_keys: dict[str, int]) -> dict[str, str]:
    """English common name per species from GBIF vernacular names."""
    semaphore = asyncio.Semaphore(MAX_CONCURRENT)

    async def one(session: aiohttp.ClientSession, key: int) -> str | None:
        async with semaphore:
            data = await _get_json(session, f"{GBIF_API}/species/{key}/vernacularNames", {"limit": 100})
        names = [r["vernacularName"] for r in (data or {}).get("results", []) if r.get("language") == "eng"]
        return names[0] if names else None

    species = list(usage_keys)
    async with aiohttp.ClientSession(headers=HEADERS) as session:
        names = await asyncio.gather(*(one(session, usage_keys[s]) for s in species))
    found = {s: n for s, n in zip(species, names, strict=True) if n}
    logger.info("GBIF: common names for %d/%d species", len(found), len(species))
    return found


def display_url(url: str) -> str:
    """iNaturalist publishes originals (several MB); its 'medium' size is plenty for a card."""
    if "inaturalist" in url and "/original." in url:
        return url.replace("/original.", "/medium.")
    return url


def pick_occurrence_image(results: list[dict[str, Any]]) -> OccurrenceImage | None:
    """First photo in a GBIF occurrence search page with an allowed license and a usable URL."""
    for occ in results:
        for media in occ.get("media") or []:
            if not isinstance(media, dict) or media.get("type") != "StillImage":
                continue
            url = media.get("identifier") or ""
            fmt = (media.get("format") or "").lower()
            if not url.startswith(("http://", "https://")):
                continue
            if fmt and not fmt.startswith(("image/jpeg", "image/png", "image/jpg")):
                continue
            raw_license = media.get("license") or occ.get("license")
            label = normalise_license(raw_license)
            if not is_allowed(label):
                continue
            return OccurrenceImage(
                image_url=display_url(url),
                page_url=f"https://www.gbif.org/occurrence/{occ.get('key')}",
                # Photographer if named, else whoever holds or published the record
                credit=media.get("creator")
                or media.get("rightsHolder")
                or occ.get("recordedBy")
                or occ.get("institutionCode")
                or occ.get("datasetName"),
                license=label or "",
                license_url=raw_license if raw_license and raw_license.startswith("http") else None,
            )
    return None


async def get_occurrence_images(usage_keys: dict[str, int]) -> dict[str, OccurrenceImage]:
    """A photo per species from GBIF occurrence records: field observations first, then specimens."""
    semaphore = asyncio.Semaphore(MAX_CONCURRENT)

    async def one(session: aiohttp.ClientSession, key: int) -> OccurrenceImage | None:
        for basis in ("HUMAN_OBSERVATION", None):
            params: dict[str, Any] = {"taxonKey": key, "mediaType": "StillImage", "limit": 20}
            if basis:
                params["basisOfRecord"] = basis
            async with semaphore:
                data = await _get_json(session, f"{GBIF_API}/occurrence/search", params)
            image = pick_occurrence_image((data or {}).get("results", []))
            if image:
                return image
        return None

    species = list(usage_keys)
    async with aiohttp.ClientSession(headers=HEADERS) as session:
        images = await asyncio.gather(*(one(session, usage_keys[s]) for s in species))
    found = {s: img for s, img in zip(species, images, strict=True) if img}
    logger.info("GBIF: occurrence photos for %d/%d species", len(found), len(species))
    return found
