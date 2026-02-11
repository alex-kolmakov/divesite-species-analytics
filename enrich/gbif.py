import asyncio
import logging
import random

import aiohttp

logger = logging.getLogger(__name__)

MAX_CONCURRENT = 20  # GBIF API is generous with rate limits
MAX_RETRIES = 3
INITIAL_BACKOFF = 2

GBIF_API = "https://api.gbif.org/v1"

HEADERS = {
    "User-Agent": "MarineSpeciesAnalytics/1.0 (https://github.com/marine-species-analytics; educational project)",
}


async def _get_common_name(
    scientific_name: str,
    session: aiohttp.ClientSession,
    semaphore: asyncio.Semaphore,
) -> str | None:
    """Look up English common name via GBIF species match + vernacular names."""
    async with semaphore:
        backoff = INITIAL_BACKOFF

        for _attempt in range(MAX_RETRIES + 1):
            try:
                # Step 1: match scientific name to get usageKey
                async with session.get(
                    f"{GBIF_API}/species/match",
                    params={"name": scientific_name},
                ) as resp:
                    if resp.status == 429:
                        await asyncio.sleep(backoff + random.uniform(0, 1))
                        backoff *= 2
                        continue
                    if resp.status != 200:
                        return None
                    match = await resp.json()

                key = match.get("usageKey")
                rank = match.get("rank")
                if not key or rank != "SPECIES":
                    return None

                # Step 2: fetch English vernacular names
                async with session.get(
                    f"{GBIF_API}/species/{key}/vernacularNames",
                    params={"limit": 100},
                ) as resp:
                    if resp.status == 429:
                        await asyncio.sleep(backoff + random.uniform(0, 1))
                        backoff *= 2
                        continue
                    if resp.status != 200:
                        return None
                    data = await resp.json()

                eng_names = [r["vernacularName"] for r in data.get("results", []) if r.get("language") == "eng"]
                return eng_names[0] if eng_names else None

            except aiohttp.ClientError:
                await asyncio.sleep(backoff)
                backoff *= 2
            except Exception:
                logger.debug("GBIF error for %s", scientific_name, exc_info=True)
                return None

        return None


async def get_common_names(
    species_names: list[str],
) -> dict[str, str]:
    """Batch-fetch English common names from GBIF for a list of species.

    Returns dict mapping scientific_name -> common_name.
    """
    semaphore = asyncio.Semaphore(MAX_CONCURRENT)

    async with aiohttp.ClientSession(headers=HEADERS) as session:
        tasks = [_get_common_name(name, session, semaphore) for name in species_names]
        results = await asyncio.gather(*tasks)

    found = {name: common for name, common in zip(species_names, results, strict=True) if common is not None}
    logger.info("GBIF: got common names for %d/%d species", len(found), len(species_names))
    return found
