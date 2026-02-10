import asyncio
import logging
import random

import aiohttp
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

MAX_RETRIES = 2
INITIAL_BACKOFF = 1

HEADERS = {
    "User-Agent": ("MarineSpeciesAnalytics/1.0 (https://github.com/marine-species-analytics; educational project)"),
}


async def get_species_info(
    scientific_name: str,
    session: aiohttp.ClientSession,
) -> tuple[str | None, str | None]:
    """Search Wikipedia for a species and return (common_name, image_url)."""
    retries = 0
    backoff = INITIAL_BACKOFF

    while retries <= MAX_RETRIES:
        try:
            await asyncio.sleep(random.uniform(1, 2))

            # Search for the species page
            search_url = (
                f"https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch={scientific_name}&format=json"
            )
            async with session.get(search_url) as resp:
                if resp.status != 200:
                    return None, None
                search_data = await resp.json()

            results = search_data.get("query", {}).get("search", [])
            if not results:
                return None, None

            page_title = results[0]["title"]

            # Fetch page info (image + extract)
            page_url = (
                "https://en.wikipedia.org/w/api.php"
                f"?action=query&titles={page_title}"
                "&prop=pageimages|extracts&format=json&pithumbsize=1024&exintro"
            )
            async with session.get(page_url) as resp:
                if resp.status != 200:
                    return None, None
                page_data = await resp.json()

            pages = page_data.get("query", {}).get("pages", {})
            if not pages:
                return None, None

            page_info = next(iter(pages.values()))

            # Extract common name from intro text
            common_name = None
            extract_text = page_info.get("extract", "")
            if extract_text:
                common_name = BeautifulSoup(extract_text, "html.parser").get_text().strip()

            image_url = page_info.get("thumbnail", {}).get("source")

            return common_name, image_url

        except aiohttp.ClientConnectionError:
            retries += 1
            await asyncio.sleep(backoff)
            backoff *= 2
        except Exception:
            logger.debug("Error fetching info for %s", scientific_name, exc_info=True)
            return None, None

    return None, None


async def enrich_species_batch(
    species_names: list[str],
) -> list[tuple[str, str | None, str | None]]:
    """Enrich a batch of species names with Wikipedia info.

    Returns list of (species_name, common_name, image_url) tuples.
    """
    async with aiohttp.ClientSession(headers=HEADERS) as session:
        tasks = [get_species_info(name, session) for name in species_names]
        results = await asyncio.gather(*tasks)

    return [
        (name, common_name, image_url) for name, (common_name, image_url) in zip(species_names, results, strict=True)
    ]
