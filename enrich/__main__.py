"""Enrich the species the app shows with a common name, a description and a credited image.

Sources, in order:
- common name: the title of the species' Wikipedia article when that is a common name ("Whale
  shark"), else the English name most GBIF checklists use
- description: Wikipedia summary (genus pages and disambiguations rejected, one-line stubs flagged)
- image: the Wikipedia article's image, else Wikidata's, both via Commons (thumbnail, artist,
  license); else a photo from a GBIF occurrence record (field observations first). Only licenses
  in enrich.licenses.ALLOWED are kept, always with credit.

Work list: species in species_summary (most widespread first) with no enrichment row, rows never
processed by this pipeline (attempted_at NULL), and rows with a missing field last tried more than
ENRICH_RETRY_DAYS ago. Results are merged every ENRICH_FLUSH_SIZE species.

    python -m enrich                 # the work list above
    python -m enrich --common-names  # choose the common name again, nothing else
"""

import argparse
import asyncio
import logging
import sys
import uuid
from dataclasses import asdict, dataclass
from datetime import UTC, datetime

import pandas as pd
from google.api_core.exceptions import ServerError
from google.api_core.retry import Retry, if_exception_type
from google.auth.exceptions import TransportError
from google.cloud import bigquery

from enrich.commons import ImageInfo, get_commons_images
from enrich.config import EnrichConfig
from enrich.gbif import OccurrenceImage, get_common_names, get_occurrence_images, match_species
from enrich.wikidata import get_wikidata_files
from enrich.wikipedia import WikiPage, get_wikipedia_pages

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# A merge holds up to ENRICH_FLUSH_SIZE species of lookups: ride out a network blip instead of losing them
FLUSH_RETRY = Retry(predicate=if_exception_type(ConnectionError, TransportError, ServerError), deadline=600)

ENRICHMENT_SCHEMA = [
    bigquery.SchemaField("species", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("common_name", "STRING"),
    bigquery.SchemaField("common_name_source", "STRING"),
    bigquery.SchemaField("description", "STRING"),
    bigquery.SchemaField("description_source", "STRING"),
    bigquery.SchemaField("description_is_stub", "BOOL"),
    bigquery.SchemaField("image_url", "STRING"),
    bigquery.SchemaField("image_source", "STRING"),
    bigquery.SchemaField("image_page_url", "STRING"),
    bigquery.SchemaField("image_credit", "STRING"),
    bigquery.SchemaField("image_license", "STRING"),
    bigquery.SchemaField("image_license_url", "STRING"),
    # When this pipeline last processed the row; NULL = never (legacy rows) or the lookup failed
    bigquery.SchemaField("attempted_at", "TIMESTAMP"),
]

# Staging-only columns: which fields this run actually refreshed
STAGING_EXTRA = [
    bigquery.SchemaField("refresh_common", "BOOL"),
    bigquery.SchemaField("refresh_text_and_image", "BOOL"),
]


@dataclass
class WorkItem:
    species: str
    has_common_name: bool


@dataclass
class Result:
    species: str
    common_name: str | None = None
    common_name_source: str | None = None
    description: str | None = None
    description_source: str | None = None
    description_is_stub: bool | None = None
    image_url: str | None = None
    image_source: str | None = None
    image_page_url: str | None = None
    image_credit: str | None = None
    image_license: str | None = None
    image_license_url: str | None = None
    attempted_at: datetime | None = None
    refresh_common: bool = False
    refresh_text_and_image: bool = True


def _prepare_table(client: bigquery.Client, table_id: str) -> None:
    """Create the table, add any new columns, and turn the old '' (tried, nothing) markers into NULL."""
    client.create_table(bigquery.Table(table_id, schema=ENRICHMENT_SCHEMA), exists_ok=True)
    existing = {f.name for f in client.get_table(table_id).schema}
    for field in ENRICHMENT_SCHEMA:
        if field.name not in existing:
            client.query(f"ALTER TABLE `{table_id}` ADD COLUMN IF NOT EXISTS {field.name} {field.field_type}").result()
            logger.info("Added column %s", field.name)
    client.query(
        f"""
        UPDATE `{table_id}`
        SET common_name = NULLIF(common_name, ''),
            description = NULLIF(description, ''),
            image_url = NULLIF(image_url, '')
        WHERE common_name = '' OR description = '' OR image_url = ''
        """
    ).result()


def work_list_query(
    target_table: str, enrichment_table: str, *, new_only: bool, limit: int | None, legacy_table: bool = False
) -> str:
    """Species to enrich, most widespread first. A legacy table (no attempted_at yet) is all unprocessed."""
    if new_only:
        condition = "e.species IS NULL"
    elif legacy_table:
        condition = "TRUE"
    else:
        condition = """
            e.species IS NULL
            OR e.attempted_at IS NULL
            OR (
                e.attempted_at < TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL @retry_days DAY)
                AND (e.common_name IS NULL OR e.description IS NULL OR e.image_url IS NULL)
            )"""
    return f"""
        SELECT t.species, e.common_name IS NOT NULL AS has_common_name
        FROM `{target_table}` AS t
        LEFT JOIN `{enrichment_table}` AS e ON t.species = e.species
        WHERE {condition}
        ORDER BY t.total_sites DESC, t.species
        {f"LIMIT {int(limit)}" if limit else ""}
    """


def common_name_work_list_query(target_table: str, enrichment_table: str, limit: int | None) -> str:
    """Species whose common name can change: those with a name or a Wikipedia article.

    The rest had no English name in GBIF and no article to take a title from.
    """
    return f"""
        SELECT t.species
        FROM `{target_table}` AS t
        JOIN `{enrichment_table}` AS e ON t.species = e.species
        WHERE e.common_name IS NOT NULL OR e.description IS NOT NULL
        ORDER BY t.total_sites DESC, t.species
        {f"LIMIT {int(limit)}" if limit else ""}
    """


def _fetch_work_list(
    client: bigquery.Client, config: EnrichConfig, *, new_only: bool, limit: int | None
) -> list[WorkItem]:
    columns = {f.name for f in client.get_table(config.enrichment_table_id).schema}
    query = work_list_query(
        config.target_species_table_id,
        config.enrichment_table_id,
        new_only=new_only,
        limit=limit,
        legacy_table="attempted_at" not in columns,
    )
    job_config = bigquery.QueryJobConfig(
        query_parameters=[bigquery.ScalarQueryParameter("retry_days", "INT64", config.retry_days)]
    )
    df = client.query(query, job_config=job_config).to_dataframe()
    return [WorkItem(species=str(r.species), has_common_name=bool(r.has_common_name)) for r in df.itertuples()]


def _set_common_name(result: Result, page: WikiPage | None, gbif_name: str | None) -> None:
    result.refresh_common = True
    if page and page.common_name:
        result.common_name, result.common_name_source = page.common_name, "wikipedia"
    elif gbif_name:
        result.common_name, result.common_name_source = gbif_name, "gbif"


async def common_name_batch(species: list[str]) -> list[Result]:
    """Choose the common name of every species again; descriptions and images are left alone."""
    keys = await match_species(species)
    gbif_names, (pages, wiki_errors) = await asyncio.gather(get_common_names(keys), get_wikipedia_pages(species))
    if wiki_errors:
        # Mostly rate limits, which have passed by the time the rest of the batch is done
        retried, wiki_errors = await get_wikipedia_pages(sorted(wiki_errors))
        pages.update(retried)
    results = []
    for name in species:
        r = Result(species=name, refresh_text_and_image=False)
        # Without Wikipedia's answer the choice can't be made: keep the stored name
        if name not in wiki_errors:
            _set_common_name(r, pages.get(name), gbif_names.get(name))
        results.append(r)
    return results


def _set_image(result: Result, image: ImageInfo | OccurrenceImage, source: str) -> None:
    result.image_url = image.image_url
    result.image_source = source
    result.image_page_url = image.page_url
    result.image_credit = image.credit
    result.image_license = image.license
    result.image_license_url = image.license_url


async def enrich_batch(batch: list[WorkItem], *, occurrence_photos: bool = True) -> list[Result]:
    """Look every species in the batch up in all sources; see the module docstring for the order."""
    names = [w.species for w in batch]
    now = datetime.now(UTC)

    keys = await match_species(names)
    need_common = {w.species: keys[w.species] for w in batch if not w.has_common_name and w.species in keys}
    common_names, (pages, wiki_errors) = await asyncio.gather(get_common_names(need_common), get_wikipedia_pages(names))

    without_file = [n for n in names if n not in wiki_errors and not (n in pages and pages[n].file_title)]
    wikidata_files = await get_wikidata_files(without_file) if without_file else {}

    file_titles = [p.file_title for p in pages.values() if p.file_title] + list(wikidata_files.values())
    commons, commons_failed = await get_commons_images(file_titles) if file_titles else ({}, set())

    results: dict[str, Result] = {}
    for w in batch:
        r = Result(species=w.species, attempted_at=now)
        page = pages.get(w.species)
        if not w.has_common_name and w.species not in wiki_errors:
            _set_common_name(r, page, common_names.get(w.species))
        wiki_file = page.file_title if page else None
        wikidata_file = wikidata_files.get(w.species)
        if w.species in wiki_errors or wiki_file in commons_failed or wikidata_file in commons_failed:
            # A lookup failed: keep what's stored and leave the row eligible for the next run
            r.refresh_text_and_image, r.attempted_at = False, None
            results[w.species] = r
            continue
        if page and page.description:
            r.description, r.description_source, r.description_is_stub = page.description, "wikipedia", page.is_stub
        if wiki_file and wiki_file in commons:
            _set_image(r, commons[wiki_file], "wikipedia")
        elif wikidata_file and wikidata_file in commons:
            _set_image(r, commons[wikidata_file], "wikidata")
        results[w.species] = r

    still_missing = {
        s: keys[s] for s, r in results.items() if r.refresh_text_and_image and not r.image_url and s in keys
    }
    if still_missing and occurrence_photos:
        images, occurrence_failed = await get_occurrence_images(still_missing)
        for species, image in images.items():
            _set_image(results[species], image, "gbif_occurrence")
        for species in occurrence_failed:
            # Same as above: not "no photo", so don't record the species as tried
            results[species].refresh_text_and_image, results[species].attempted_at = False, None

    return [results[w.species] for w in batch]


def merge_query(enrichment_table: str, staging_table: str) -> str:
    """Upsert staging into the enrichment table, touching only the fields this run refreshed."""
    text_image_cols = [
        "description",
        "description_source",
        "description_is_stub",
        "image_url",
        "image_source",
        "image_page_url",
        "image_credit",
        "image_license",
        "image_license_url",
    ]
    sets = [
        "common_name = IF(s.refresh_common, s.common_name, t.common_name)",
        "common_name_source = IF(s.refresh_common, s.common_name_source,"
        " COALESCE(t.common_name_source, IF(t.common_name IS NOT NULL, 'gbif', NULL)))",
        *(f"{c} = IF(s.refresh_text_and_image, s.{c}, t.{c})" for c in text_image_cols),
        "attempted_at = IF(s.refresh_text_and_image, s.attempted_at, t.attempted_at)",
    ]
    columns = [f.name for f in ENRICHMENT_SCHEMA]
    set_clause = ",\n            ".join(sets)
    return f"""
        MERGE `{enrichment_table}` AS t
        USING `{staging_table}` AS s
        ON t.species = s.species
        WHEN MATCHED THEN UPDATE SET
            {set_clause}
        WHEN NOT MATCHED THEN INSERT ({", ".join(columns)})
            VALUES ({", ".join(f"s.{c}" for c in columns)})
    """


def _flush(client: bigquery.Client, enrichment_table: str, results: list[Result]) -> None:
    if not results:
        return
    staging = f"{enrichment_table}_staging_{uuid.uuid4().hex[:8]}"
    df = pd.DataFrame([asdict(r) for r in results])
    job_config = bigquery.LoadJobConfig(write_disposition="WRITE_TRUNCATE", schema=ENRICHMENT_SCHEMA + STAGING_EXTRA)
    try:
        client.load_table_from_dataframe(df, staging, job_config=job_config).result(retry=FLUSH_RETRY)
        client.query(merge_query(enrichment_table, staging), retry=FLUSH_RETRY).result()
    finally:
        client.delete_table(staging, not_found_ok=True)
    logger.info("Merged %d species into %s", len(results), enrichment_table)


def _coverage(client: bigquery.Client, config: EnrichConfig) -> None:
    rows = client.query(
        f"""
        SELECT
            COUNT(*) AS species,
            COUNTIF(e.common_name IS NOT NULL) AS common_name,
            COUNTIF(e.description IS NOT NULL AND NOT IFNULL(e.description_is_stub, FALSE)) AS description,
            COUNTIF(e.description_is_stub) AS stub,
            COUNTIF(e.image_url IS NOT NULL) AS image,
            COUNTIF(e.image_source = 'gbif_occurrence') AS image_from_occurrences,
            COUNTIF(e.image_url IS NOT NULL AND e.image_credit IS NULL) AS image_without_credit
        FROM `{config.target_species_table_id}` AS t
        LEFT JOIN `{config.enrichment_table_id}` AS e USING (species)
        """
    ).result()
    row = next(iter(rows))
    logger.info("Coverage of species at dive sites: %s", dict(row.items()))


def summarize(results: list[Result]) -> dict[str, int]:
    return {
        "processed": len(results),
        "common_name": sum(1 for r in results if r.common_name),
        "description": sum(1 for r in results if r.description and not r.description_is_stub),
        "stub": sum(1 for r in results if r.description_is_stub),
        "image_wikipedia": sum(1 for r in results if r.image_source == "wikipedia"),
        "image_wikidata": sum(1 for r in results if r.image_source == "wikidata"),
        "image_gbif_occurrence": sum(1 for r in results if r.image_source == "gbif_occurrence"),
        "common_name_wikipedia": sum(1 for r in results if r.common_name_source == "wikipedia"),
        "lookup_failed": sum(1 for r in results if not (r.refresh_text_and_image or r.refresh_common)),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Enrich species shown at dive sites with names, descriptions and images"
    )
    parser.add_argument("--new-only", action="store_true", help="Only species with no enrichment row yet")
    parser.add_argument("--limit", type=int, help="Process at most this many species (most widespread first)")
    parser.add_argument("--dry-run", action="store_true", help="Look species up but write nothing to BigQuery")
    parser.add_argument(
        "--no-occurrence-photos",
        action="store_true",
        help="Skip the GBIF occurrence photo fallback (its search API throttles long runs)",
    )
    parser.add_argument("--skip", type=int, default=0, help="Skip the first N species, to resume a stopped run")
    parser.add_argument(
        "--common-names",
        action="store_true",
        help="Choose the common name again for species with a name or an article; nothing else changes",
    )
    args = parser.parse_args()

    config = EnrichConfig.from_env()
    client = bigquery.Client(project=config.project_id)
    if not args.dry_run:
        _prepare_table(client, config.enrichment_table_id)

    if args.common_names:
        query = common_name_work_list_query(config.target_species_table_id, config.enrichment_table_id, args.limit)
        rows = client.query(query).result()
        work = [WorkItem(species=str(r.species), has_common_name=False) for r in rows]
        logger.info("Work list: %d species (common names only)", len(work))
    else:
        work = _fetch_work_list(client, config, new_only=args.new_only, limit=args.limit)
        logger.info(
            "Work list: %d species (%s)",
            len(work),
            "new only" if args.new_only else "new, unprocessed and due for retry",
        )
    work = work[args.skip :]
    if not work:
        return 0

    pending: list[Result] = []
    totals: list[Result] = []
    for start in range(0, len(work), config.batch_size):
        batch = work[start : start + config.batch_size]
        if args.common_names:
            results = asyncio.run(common_name_batch([w.species for w in batch]))
        else:
            results = asyncio.run(enrich_batch(batch, occurrence_photos=not args.no_occurrence_photos))
        pending.extend(results)
        totals.extend(results)
        logger.info("Batch %d-%d of %d: %s", start + 1, start + len(batch), len(work), summarize(results))
        if not args.dry_run and len(pending) >= config.flush_size:
            _flush(client, config.enrichment_table_id, pending)
            pending = []

    if args.dry_run:
        logger.info("Dry run, nothing written. Totals: %s", summarize(totals))
        for r in totals[:5]:
            logger.info(
                "  %s | %s | %s | %s %s", r.species, r.common_name, r.image_source, r.image_license, r.image_credit
            )
        return 0

    _flush(client, config.enrichment_table_id, pending)
    logger.info("Totals: %s", summarize(totals))
    _coverage(client, config)
    return 0


if __name__ == "__main__":
    sys.exit(main())
