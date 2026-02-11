import asyncio
import hashlib
import logging
import random
from urllib.parse import quote, unquote

import aiohttp

logger = logging.getLogger(__name__)

MAX_CONCURRENT = 5
BATCH_SIZE = 50
MAX_RETRIES = 3
INITIAL_BACKOFF = 2

SPARQL_ENDPOINT = "https://query.wikidata.org/sparql"

HEADERS = {
    "User-Agent": "MarineSpeciesAnalytics/1.0 (https://github.com/marine-species-analytics; educational project)",
    "Accept": "application/sparql-results+json",
}

SPARQL_TEMPLATE = """
SELECT ?scientificName ?image WHERE {{
  VALUES ?scientificName {{ {values} }}
  ?taxon wdt:P225 ?scientificName .
  ?taxon wdt:P18 ?image .
}}
"""


def commons_thumb_url(file_page_url: str, width: int = 800) -> str:
    """Convert a Wikimedia Commons Special:FilePath URL to a direct thumbnail URL.

    Input:  http://commons.wikimedia.org/wiki/Special:FilePath/Queen%20Angelfish.jpg
    Output: https://upload.wikimedia.org/wikipedia/commons/thumb/a/ab/Queen_Angelfish.jpg/800px-Queen_Angelfish.jpg
    """
    # Extract filename from URL
    filename = file_page_url.rsplit("/", 1)[-1]
    filename = unquote(filename).replace(" ", "_")

    md5 = hashlib.md5(filename.encode()).hexdigest()
    a, ab = md5[0], md5[:2]

    return (
        f"https://upload.wikimedia.org/wikipedia/commons/thumb/{a}/{ab}/{quote(filename)}/{width}px-{quote(filename)}"
    )


def _build_values_clause(names: list[str]) -> str:
    return " ".join(f'"{name}"' for name in names)


async def _query_sparql_batch(
    names: list[str],
    session: aiohttp.ClientSession,
    semaphore: asyncio.Semaphore,
) -> dict[str, str]:
    """Query Wikidata for image URLs. Returns dict of species_name -> image_url."""
    async with semaphore:
        values = _build_values_clause(names)
        query = SPARQL_TEMPLATE.format(values=values)
        url = f"{SPARQL_ENDPOINT}?query={quote(query)}"

        backoff = INITIAL_BACKOFF
        for attempt in range(MAX_RETRIES + 1):
            try:
                await asyncio.sleep(0.5 + random.uniform(0, 0.5))
                async with session.get(url) as resp:
                    if resp.status == 429:
                        retry_after = int(resp.headers.get("Retry-After", backoff))
                        logger.debug("Wikidata rate limited (attempt %d)", attempt + 1)
                        await asyncio.sleep(retry_after)
                        backoff *= 2
                        continue
                    if resp.status != 200:
                        logger.debug("Wikidata SPARQL returned %d", resp.status)
                        return {}
                    data = await resp.json()
            except aiohttp.ClientError:
                await asyncio.sleep(backoff)
                backoff *= 2
                continue

            results: dict[str, str] = {}
            for binding in data.get("results", {}).get("bindings", []):
                sci_name = binding["scientificName"]["value"]
                if sci_name in results:
                    continue
                raw_url = binding.get("image", {}).get("value", "")
                if raw_url:
                    results[sci_name] = commons_thumb_url(raw_url)
            return results

        return {}


async def get_wikidata_images(species_names: list[str]) -> dict[str, str]:
    """Batch-fetch image URLs from Wikidata for a list of species.

    Returns dict mapping species_name -> direct thumbnail URL.
    """
    semaphore = asyncio.Semaphore(MAX_CONCURRENT)
    all_results: dict[str, str] = {}

    async with aiohttp.ClientSession(headers=HEADERS) as session:
        tasks = []
        for i in range(0, len(species_names), BATCH_SIZE):
            batch = species_names[i : i + BATCH_SIZE]
            tasks.append(_query_sparql_batch(batch, session, semaphore))

        batch_results = await asyncio.gather(*tasks)
        for result in batch_results:
            all_results.update(result)

    logger.info("Wikidata: got images for %d/%d species", len(all_results), len(species_names))
    return all_results
