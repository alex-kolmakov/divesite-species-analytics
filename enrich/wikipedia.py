import asyncio
import logging
import random
import re
from dataclasses import dataclass
from urllib.parse import quote, unquote, urlparse

import aiohttp

from enrich.names import canonical_name, genus

logger = logging.getLogger(__name__)

MAX_CONCURRENT = 10
MAX_RETRIES = 3
INITIAL_BACKOFF = 2

UA = "MarineSpeciesAnalytics/1.0 (https://github.com/alex-kolmakov/divesite-species-analytics; educational project)"

HEADERS = {
    "User-Agent": UA,
    "Api-User-Agent": UA,
}

_SENTENCE_END = re.compile(r"(?<=[.!?])\s+(?=[A-Z])")
_DISAMBIGUATOR = re.compile(r"\s*\([^)]*\)$")
_SPECIES = re.compile(r"\bspecies\b", re.IGNORECASE)
_WIDER_GROUP = re.compile(r"\b(?:subgenus|genus|genera|tribe|subfamily|family|order|class|group)\b", re.IGNORECASE)
_STUB = re.compile(r"\bis an? (?:extinct )?(?:species|subspecies) of\b", re.IGNORECASE)


# Returned instead of a page when the lookup failed (rate limit, network) rather than missed
ERROR = "error"


@dataclass
class WikiPage:
    description: str | None
    is_stub: bool
    # Commons file name ("Pterois volitans Manado-e edit.jpg"); credit and thumbnail come from Commons
    file_title: str | None
    # The article's title when it is the species' common name ("Whale shark")
    common_name: str | None = None


def is_genus_page(species: str, canonical_title: str, extract: str = "") -> bool:
    """True when Wikipedia redirected the species to an article about its whole genus.

    A redirect to a common name is fine ("Acropora palmata" -> "Elkhorn coral"); a redirect to the
    genus ("Parapriacanthus ransonneti" -> "Parapriacanthus") describes several species. A
    monotypic genus is the exception: its article is about the one species ("Cryptodendrum is a
    genus ... It is monotypic with a single species, Cryptodendrum adhaesivum"), so it is kept when
    it says monotypic or names the species.
    """
    title = unquote(canonical_title).replace("_", " ").strip().lower()
    if title != genus(species).lower():
        return False
    text = extract.lower()
    return "monotypic" not in text and canonical_name(species).lower() not in text


def common_name_from_title(
    species: str, title: str, display_title: str, short_description: str, extract: str = ""
) -> str | None:
    """The article title, when the article is filed under the species' common name.

    Wikipedia names an article after the name most people use ("Rhincodon typus" redirects to
    "Whale shark") and sets scientific names in italics, so an italic title is not a common name.
    The article has to be about one species: its short description says so ("Species of fish";
    "Class of echinoderms" for a redirect to the wider group "Sea cucumber"), or its text names
    the species.
    """
    name = _DISAMBIGUATOR.sub("", title).strip()
    canonical = canonical_name(species).lower()
    if not name or "<i>" in display_title.lower() or name.lower() in (canonical, genus(species).lower()):
        return None
    about_one_species = bool(_SPECIES.search(short_description)) and not _WIDER_GROUP.search(short_description)
    if not about_one_species and canonical not in extract.lower():
        return None
    return name


def is_stub(description: str) -> bool:
    """One sentence saying only what the species is ("X is a species of sea snail in the family Y.")."""
    sentences = [s for s in _SENTENCE_END.split(description.strip()) if s]
    return len(sentences) <= 1 and bool(_STUB.search(description))


def commons_file_title(image_url: str | None) -> str | None:
    """The Commons file name behind a Wikipedia image URL, or None for a non-Commons file.

    Files under /wikipedia/en/ are local uploads, usually non-free "fair use" images that can't be
    reused, so they are skipped.
    """
    if not image_url:
        return None
    path = urlparse(image_url).path
    if "/wikipedia/commons/" not in path:
        return None
    parts = path.split("/wikipedia/commons/", 1)[1].split("/")
    if parts and parts[0] == "thumb":
        # thumb/a/ab/<file>/<width>px-<file>
        return unquote(parts[3]) if len(parts) >= 4 else None
    return unquote(parts[-1]) if parts else None


async def _get_page(
    species: str,
    session: aiohttp.ClientSession,
    semaphore: asyncio.Semaphore,
) -> WikiPage | str | None:
    """Wikipedia summary for a species by direct lookup (a 404 is a clean miss, not a wrong match).

    Returns the page, None for a real miss (no page, a genus page, a disambiguation), or ERROR when
    the lookup itself failed, so callers can keep what they already have instead of erasing it.
    """
    async with semaphore:
        backoff = INITIAL_BACKOFF
        page_title = canonical_name(species).replace(" ", "_")
        url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{quote(page_title)}"

        for attempt in range(MAX_RETRIES + 1):
            try:
                await asyncio.sleep(random.uniform(0.3, 0.8))

                async with session.get(url) as resp:
                    if resp.status == 404:
                        return None
                    if resp.status in (429, 403):
                        logger.debug("Wikipedia rate limited for %s (attempt %d)", species, attempt + 1)
                        await asyncio.sleep(backoff + random.uniform(0, 1))
                        backoff *= 2
                        continue
                    if resp.status != 200:
                        return ERROR
                    data = await resp.json()

                if data.get("type") == "disambiguation":
                    return None
                extract = data.get("extract") or ""
                if is_genus_page(species, data.get("titles", {}).get("canonical", ""), extract):
                    return None

                description = extract or None
                image = (data.get("originalimage") or data.get("thumbnail") or {}).get("source")
                return WikiPage(
                    description=description,
                    is_stub=bool(description) and is_stub(description),
                    file_title=commons_file_title(image),
                    common_name=common_name_from_title(
                        species,
                        data.get("title") or "",
                        data.get("displaytitle") or "",
                        data.get("description") or "",
                        extract,
                    ),
                )

            except aiohttp.ClientError:
                await asyncio.sleep(backoff)
                backoff *= 2
            except Exception:
                logger.debug("Wikipedia error for %s", species, exc_info=True)
                return ERROR

        return ERROR


async def get_wikipedia_pages(species_names: list[str]) -> tuple[dict[str, WikiPage], set[str]]:
    """Wikipedia summaries for a list of species, and the species whose lookup failed.

    Missing, genus and disambiguation pages are in neither.
    """
    semaphore = asyncio.Semaphore(MAX_CONCURRENT)

    async with aiohttp.ClientSession(headers=HEADERS) as session:
        tasks = [_get_page(name, session, semaphore) for name in species_names]
        results = await asyncio.gather(*tasks)

    found = {name: r for name, r in zip(species_names, results, strict=True) if isinstance(r, WikiPage)}
    errors = {name for name, r in zip(species_names, results, strict=True) if r == ERROR}
    logger.info("Wikipedia: pages for %d/%d species (%d lookups failed)", len(found), len(species_names), len(errors))
    return found, errors
