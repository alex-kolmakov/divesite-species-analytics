import asyncio
import logging
import random
from urllib.parse import quote

import aiohttp

logger = logging.getLogger(__name__)

MAX_CONCURRENT = 10
MAX_RETRIES = 3
INITIAL_BACKOFF = 2

UA = "MarineSpeciesAnalytics/1.0 (https://github.com/marine-species-analytics; educational project)"

HEADERS = {
    "User-Agent": UA,
    "Api-User-Agent": UA,
}


async def _get_species_summary(
    scientific_name: str,
    session: aiohttp.ClientSession,
    semaphore: asyncio.Semaphore,
) -> tuple[str | None, str | None]:
    """Fetch description and image URL from Wikipedia REST API.

    Uses direct page lookup by scientific name — returns 404 for no page
    (no risk of bad search matches).

    Returns (description, image_url).
    """
    async with semaphore:
        backoff = INITIAL_BACKOFF
        page_title = scientific_name.replace(" ", "_")
        url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{quote(page_title)}"

        for attempt in range(MAX_RETRIES + 1):
            try:
                await asyncio.sleep(random.uniform(0.3, 0.8))

                async with session.get(url) as resp:
                    if resp.status == 404:
                        return None, None
                    if resp.status in (429, 403):
                        logger.debug("Wikipedia rate limited for %s (attempt %d)", scientific_name, attempt + 1)
                        await asyncio.sleep(backoff + random.uniform(0, 1))
                        backoff *= 2
                        continue
                    if resp.status != 200:
                        return None, None
                    data = await resp.json()

                description = data.get("extract")
                image_url = data.get("originalimage", {}).get("source")

                return description, image_url

            except aiohttp.ClientError:
                await asyncio.sleep(backoff)
                backoff *= 2
            except Exception:
                logger.debug("Wikipedia error for %s", scientific_name, exc_info=True)
                return None, None

        return None, None


async def get_wikipedia_data(
    species_names: list[str],
) -> dict[str, tuple[str | None, str | None]]:
    """Fetch descriptions and images from Wikipedia REST API.

    Returns dict mapping scientific_name -> (description, image_url).
    """
    semaphore = asyncio.Semaphore(MAX_CONCURRENT)

    async with aiohttp.ClientSession(headers=HEADERS) as session:
        tasks = [_get_species_summary(name, session, semaphore) for name in species_names]
        results = await asyncio.gather(*tasks)

    found = {
        name: (desc, img)
        for name, (desc, img) in zip(species_names, results)
        if desc is not None or img is not None
    }
    logger.info("Wikipedia: got data for %d/%d species", len(found), len(species_names))
    return found
