import asyncio
import logging
import random
from dataclasses import dataclass
from typing import Any, Literal

import aiohttp

from enrich.licenses import is_allowed, normalise_license
from enrich.names import canonical_name
from enrich.wikipedia import UA

logger = logging.getLogger(__name__)

MAX_CONCURRENT = 20  # the species endpoints are generous with rate limits
# Occurrence search is not: it answers bursts with 429 (Retry-After: 3). Paced one at a time it
# took 4 requests a second without a single 429 (measured 2026-10-07).
OCCURRENCE_CONCURRENT = 4
OCCURRENCE_INTERVAL = 0.25  # seconds between request starts
MAX_RETRIES = 5
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


class Pacer:
    """Spaces out request starts, and holds every request back after the API says to slow down."""

    def __init__(self, interval: float) -> None:
        self.interval = interval
        self.next_start = 0.0

    async def wait(self) -> None:
        now = asyncio.get_running_loop().time()
        start = max(now, self.next_start)
        self.next_start = start + self.interval
        await asyncio.sleep(start - now)

    def hold(self, seconds: float) -> None:
        self.next_start = max(self.next_start, asyncio.get_running_loop().time() + seconds)


async def _get_json(
    session: aiohttp.ClientSession, url: str, params: dict[str, Any], pacer: Pacer | None = None
) -> dict[str, Any] | None:
    """GET with backoff on 429, 5xx, timeouts and network errors. None when the lookup failed."""
    backoff = INITIAL_BACKOFF
    reason = "no attempt"
    for _attempt in range(MAX_RETRIES + 1):
        if pacer:
            await pacer.wait()
        try:
            async with session.get(url, params=params) as resp:
                if resp.status == 429 or resp.status >= 500:
                    reason = f"status {resp.status}"
                    retry_after = resp.headers.get("Retry-After", "")
                    wait = max(backoff, int(retry_after)) if retry_after.isdigit() else backoff
                    if pacer:
                        pacer.hold(wait)  # everyone waits, not just this request
                    else:
                        await asyncio.sleep(wait + random.uniform(0, 1))
                    backoff *= 2
                    continue
                if resp.status != 200:
                    reason = f"status {resp.status}"
                    break
                data = await resp.json()
                return data if isinstance(data, dict) else None
        except (aiohttp.ClientError, TimeoutError) as e:
            reason = type(e).__name__
            await asyncio.sleep(backoff)
            backoff *= 2
        except Exception:
            logger.debug("GBIF error for %s %s", url, params, exc_info=True)
            return None
    logger.debug("GBIF lookup failed (%s) for %s %s", reason, url, params)
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


async def get_occurrence_images(usage_keys: dict[str, int]) -> tuple[dict[str, OccurrenceImage], set[str]]:
    """A photo per species from GBIF occurrence records, and the species whose lookup failed.

    Field observations first, then specimens. A species with no usable photo is in neither.
    """
    semaphore = asyncio.Semaphore(OCCURRENCE_CONCURRENT)
    pacer = Pacer(OCCURRENCE_INTERVAL)

    async def one(session: aiohttp.ClientSession, key: int) -> OccurrenceImage | None | Literal[False]:
        """False when a lookup failed, None when GBIF has no usable photo."""
        for basis in ("HUMAN_OBSERVATION", None):
            params: dict[str, Any] = {"taxonKey": key, "mediaType": "StillImage", "limit": 20}
            if basis:
                params["basisOfRecord"] = basis
            async with semaphore:
                data = await _get_json(session, f"{GBIF_API}/occurrence/search", params, pacer)
            if data is None:
                return False
            image = pick_occurrence_image(data.get("results", []))
            if image:
                return image
        return None

    species = list(usage_keys)
    async with aiohttp.ClientSession(headers=HEADERS) as session:
        images = await asyncio.gather(*(one(session, usage_keys[s]) for s in species))
    found = {s: img for s, img in zip(species, images, strict=True) if img}
    failed = {s for s, img in zip(species, images, strict=True) if img is False}
    logger.info("GBIF: occurrence photos for %d/%d species (%d lookups failed)", len(found), len(species), len(failed))
    return found, failed
