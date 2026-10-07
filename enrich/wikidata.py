import asyncio
import logging
import random
from urllib.parse import quote, unquote

import aiohttp

from enrich.names import canonical_name
from enrich.wikipedia import UA

logger = logging.getLogger(__name__)

MAX_CONCURRENT = 5
BATCH_SIZE = 50
MAX_RETRIES = 3
INITIAL_BACKOFF = 2

SPARQL_ENDPOINT = "https://query.wikidata.org/sparql"

HEADERS = {
    "User-Agent": UA,
    "Accept": "application/sparql-results+json",
}

SPARQL_TEMPLATE = """
SELECT ?scientificName ?image WHERE {{
  VALUES ?scientificName {{ {values} }}
  ?taxon wdt:P225 ?scientificName .
  ?taxon wdt:P18 ?image .
}}
"""


def file_title_from_filepath(url: str) -> str:
    """Commons file name from a Special:FilePath URL.

    "http://commons.wikimedia.org/wiki/Special:FilePath/Queen%20Angelfish.jpg" -> "Queen Angelfish.jpg"
    """
    return unquote(url.rsplit("/", 1)[-1]).replace("_", " ")


def _build_values_clause(names: list[str]) -> str:
    escaped = (name.replace("\\", "\\\\").replace('"', '\\"') for name in names)
    return " ".join(f'"{name}"' for name in escaped)


async def _query_sparql_batch(
    names: list[str],
    session: aiohttp.ClientSession,
    semaphore: asyncio.Semaphore,
) -> dict[str, str]:
    """Query Wikidata for image files. Returns dict of taxon name -> Commons file name."""
    async with semaphore:
        query = SPARQL_TEMPLATE.format(values=_build_values_clause(names))
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
                name = binding["scientificName"]["value"]
                raw_url = binding.get("image", {}).get("value", "")
                if raw_url and name not in results:
                    results[name] = file_title_from_filepath(raw_url)
            return results

        return {}


async def get_wikidata_files(species_names: list[str]) -> dict[str, str]:
    """Commons image file names from Wikidata, matched on the plain binomial.

    Returns dict mapping species (as given) -> Commons file name.
    """
    by_canonical: dict[str, list[str]] = {}
    for species in species_names:
        by_canonical.setdefault(canonical_name(species), []).append(species)
    canonical = list(by_canonical)

    semaphore = asyncio.Semaphore(MAX_CONCURRENT)
    found: dict[str, str] = {}

    async with aiohttp.ClientSession(headers=HEADERS) as session:
        tasks = [
            _query_sparql_batch(canonical[i : i + BATCH_SIZE], session, semaphore)
            for i in range(0, len(canonical), BATCH_SIZE)
        ]
        for result in await asyncio.gather(*tasks):
            for name, file_title in result.items():
                for species in by_canonical.get(name, []):
                    found[species] = file_title

    logger.info("Wikidata: images for %d/%d species", len(found), len(species_names))
    return found
