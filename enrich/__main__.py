import argparse
import asyncio
import logging
import sys
from dataclasses import dataclass

import pandas as pd
from google.cloud import bigquery

from enrich.config import EnrichConfig
from enrich.gbif import get_common_names
from enrich.wikidata import get_wikidata_images
from enrich.wikipedia import get_wikipedia_data

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

ENRICHMENT_SCHEMA = [
    bigquery.SchemaField("species", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("common_name", "STRING"),
    bigquery.SchemaField("description", "STRING"),
    bigquery.SchemaField("image_url", "STRING"),
]


@dataclass
class SpeciesRow:
    species: str
    common_name: str | None
    description: str | None
    image_url: str | None
    is_new: bool  # True = not yet in enrichment table


def _ensure_enrichment_table(client: bigquery.Client, table_id: str) -> None:
    """Create the species_enrichment table if it doesn't exist."""
    table = bigquery.Table(table_id, schema=ENRICHMENT_SCHEMA)
    client.create_table(table, exists_ok=True)
    logger.info("Enrichment table ready: %s", table_id)


def _get_progress(client: bigquery.Client, species_table: str, enrichment_table: str) -> tuple[int, int, int]:
    """Return (total_species, fully_enriched, partially_enriched) counts."""
    # Empty string '' means "tried but not found" — exclude from counts
    query = f"""
        SELECT
            (SELECT COUNT(*) FROM `{species_table}`) AS total,
            (SELECT COUNT(*) FROM `{enrichment_table}`
             WHERE NULLIF(common_name, '') IS NOT NULL
               AND NULLIF(description, '') IS NOT NULL
               AND NULLIF(image_url, '') IS NOT NULL
            ) AS fully_enriched,
            (SELECT COUNT(*) FROM `{enrichment_table}`
             WHERE NULLIF(common_name, '') IS NOT NULL
                OR NULLIF(description, '') IS NOT NULL
                OR NULLIF(image_url, '') IS NOT NULL
            ) AS with_any_data
    """
    row = list(client.query(query).result())[0]
    return row.total, row.fully_enriched, row.with_any_data


def _fetch_batch(
    client: bigquery.Client,
    species_table: str,
    enrichment_table: str,
    batch_size: int,
    *,
    new_only: bool = False,
) -> list[SpeciesRow]:
    """Fetch species that need enrichment: unattempted + partially enriched."""
    if new_only:
        query = f"""
            SELECT s.species, NULL AS common_name, NULL AS description,
                   NULL AS image_url, TRUE AS is_new
            FROM `{species_table}` AS s
            LEFT JOIN `{enrichment_table}` AS e ON s.species = e.species
            WHERE e.species IS NULL
            LIMIT {batch_size}
        """
    else:
        query = f"""
            SELECT species, common_name, description, image_url, is_new
            FROM (
                SELECT e.species, e.common_name, e.description, e.image_url, FALSE AS is_new
                FROM `{enrichment_table}` AS e
                WHERE (e.common_name IS NULL OR e.description IS NULL OR e.image_url IS NULL)
                  AND (e.common_name IS NOT NULL OR e.description IS NOT NULL OR e.image_url IS NOT NULL)

                UNION ALL

                SELECT s.species, NULL AS common_name, NULL AS description, NULL AS image_url, TRUE AS is_new
                FROM `{species_table}` AS s
                LEFT JOIN `{enrichment_table}` AS e ON s.species = e.species
                WHERE e.species IS NULL
            )
            LIMIT {batch_size}
        """
    df = client.query(query).to_dataframe()
    if df.empty:
        return []
    return [
        SpeciesRow(
            species=str(row["species"]),
            common_name=str(row["common_name"]) if pd.notna(row["common_name"]) else None,
            description=str(row["description"]) if pd.notna(row["description"]) else None,
            image_url=str(row["image_url"]) if pd.notna(row["image_url"]) else None,
            is_new=bool(row["is_new"]),
        )
        for _, row in df.iterrows()
    ]


async def _enrich_batch_async(batch: list[SpeciesRow]) -> list[SpeciesRow]:
    """Run enrichment phases concurrently, only querying APIs for missing fields."""
    need_gbif = [s for s in batch if s.common_name is None]
    need_wiki = [s for s in batch if s.description is None or s.image_url is None]

    logger.info(
        "  API calls: %d need GBIF, %d need Wikipedia",
        len(need_gbif),
        len(need_wiki),
    )

    # Phase 1 + 2 concurrently
    gbif_coro = get_common_names([s.species for s in need_gbif]) if need_gbif else None
    wiki_coro = get_wikipedia_data([s.species for s in need_wiki]) if need_wiki else None

    common_names: dict[str, str] = {}
    wikipedia_data: dict[str, tuple[str | None, str | None]] = {}

    if gbif_coro and wiki_coro:
        common_names, wikipedia_data = await asyncio.gather(gbif_coro, wiki_coro)
    elif gbif_coro:
        common_names = await gbif_coro
    elif wiki_coro:
        wikipedia_data = await wiki_coro

    # Phase 3: Wikidata fallback for species still missing images
    need_wikidata = [
        s
        for s in need_wiki
        if s.image_url is None and (s.species not in wikipedia_data or wikipedia_data[s.species][1] is None)
    ]
    wikidata_images: dict[str, str] = {}
    if need_wikidata:
        logger.info("  Wikidata fallback for %d species...", len(need_wikidata))
        wikidata_images = await get_wikidata_images([s.species for s in need_wikidata])

    # Merge results into species rows
    # For retried species, replace remaining NULLs with '' to prevent infinite retries.
    # Empty string means "all APIs tried, nothing found" vs NULL = "not yet attempted".
    enriched = []
    for s in batch:
        common = common_names.get(s.species) or s.common_name
        wp_desc, wp_img = wikipedia_data.get(s.species, (None, None))
        wd_img = wikidata_images.get(s.species)
        final_common = common
        final_desc = wp_desc or s.description
        final_img = wp_img or wd_img or s.image_url
        if not s.is_new:
            # Mark exhausted fields so this species isn't retried
            final_common = final_common or ""
            final_desc = final_desc or ""
            final_img = final_img or ""
        enriched.append(
            SpeciesRow(
                species=s.species,
                common_name=final_common,
                description=final_desc,
                image_url=final_img,
                is_new=s.is_new,
            )
        )
    return enriched


def _save_results(client: bigquery.Client, enrichment_table: str, enriched: list[SpeciesRow]) -> None:
    """Upsert enriched species via staging table + MERGE (prevents duplicates)."""
    if not enriched:
        return

    new_count = sum(1 for s in enriched if s.is_new)
    update_count = len(enriched) - new_count

    temp_table = f"{enrichment_table}_staging"
    df = pd.DataFrame(
        [(s.species, s.common_name, s.description, s.image_url) for s in enriched],
        columns=["species", "common_name", "description", "image_url"],
    )
    job_config = bigquery.LoadJobConfig(
        write_disposition="WRITE_TRUNCATE",
        schema=ENRICHMENT_SCHEMA,
    )
    client.load_table_from_dataframe(df, temp_table, job_config=job_config).result()

    query = f"""
        MERGE `{enrichment_table}` AS target
        USING `{temp_table}` AS source
        ON target.species = source.species
        WHEN MATCHED THEN UPDATE SET
            common_name = COALESCE(source.common_name, target.common_name),
            description = COALESCE(source.description, target.description),
            image_url = COALESCE(source.image_url, target.image_url)
        WHEN NOT MATCHED THEN INSERT (species, common_name, description, image_url)
            VALUES (source.species, source.common_name, source.description, source.image_url)
    """
    client.query(query).result()
    client.delete_table(temp_table, not_found_ok=True)
    logger.info("  Saved %d species (%d new, %d updated)", len(enriched), new_count, update_count)


def main() -> int:
    parser = argparse.ArgumentParser(description="Enrich species with common names, descriptions, and images")
    parser.add_argument(
        "--new-only",
        action="store_true",
        help="Only enrich species not yet in the enrichment table (skip retrying partial rows)",
    )
    args = parser.parse_args()

    config = EnrichConfig.from_env()
    client = bigquery.Client(project=config.project_id)

    enrichment_table = config.enrichment_table_id
    species_table = config.species_table_id

    _ensure_enrichment_table(client, enrichment_table)

    # Get initial progress
    total_species, fully_enriched, with_any_data = _get_progress(client, species_table, enrichment_table)
    mode = "new only" if args.new_only else "new + retry partial"
    logger.info(
        "Starting enrichment (%s): %s total species | %s fully enriched | %s with some data",
        mode,
        f"{total_species:,}",
        f"{fully_enriched:,}",
        f"{with_any_data:,}",
    )

    batch_num = 0

    while True:
        batch_num += 1
        batch = _fetch_batch(
            client,
            species_table,
            enrichment_table,
            config.batch_size,
            new_only=args.new_only,
        )

        if not batch:
            break

        new_count = sum(1 for s in batch if s.is_new)
        retry_count = len(batch) - new_count
        logger.info(
            "Batch %d: %d species (%d new, %d retrying partial)",
            batch_num,
            len(batch),
            new_count,
            retry_count,
        )

        enriched = asyncio.run(_enrich_batch_async(batch))

        # Stats for this batch
        got_common = sum(1 for s in enriched if s.common_name)
        got_desc = sum(1 for s in enriched if s.description)
        got_img = sum(1 for s in enriched if s.image_url)
        with_data = sum(1 for s in enriched if s.common_name or s.description or s.image_url)

        logger.info(
            "  Results: %d/%d with data (common=%d, desc=%d, img=%d)",
            with_data,
            len(enriched),
            got_common,
            got_desc,
            got_img,
        )

        _save_results(client, enrichment_table, enriched)

        # Update and log total progress
        total_attempted = fully_enriched + (batch_num * config.batch_size)
        attempted_pct = min(100.0, total_attempted / total_species * 100) if total_species else 0
        logger.info(
            "  Progress: ~%s/%s attempted (%.1f%%)",
            f"{total_attempted:,}",
            f"{total_species:,}",
            attempted_pct,
        )

        if len(batch) < config.batch_size:
            break

    # Final stats
    total_species, fully_enriched, with_any_data = _get_progress(client, species_table, enrichment_table)
    logger.info(
        "Enrichment complete in %d batches: %s/%s fully enriched, %s with some data",
        batch_num,
        f"{fully_enriched:,}",
        f"{total_species:,}",
        f"{with_any_data:,}",
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
