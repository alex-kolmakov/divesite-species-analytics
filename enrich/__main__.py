import argparse
import asyncio
import json
import logging
import sys
from dataclasses import dataclass
from pathlib import Path

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

CHECKPOINT_DIR = Path("/tmp/enrich_checkpoints")

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


def _get_initial_stats(client: bigquery.Client, species_table: str, enrichment_table: str) -> dict:
    """Get initial stats ONCE at start. Returns dict with all counts."""
    # Empty string '' means "tried but not found" — exclude from counts
    query = f"""
        SELECT
            (SELECT COUNT(*) FROM `{species_table}`) AS total_species,
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
    return {
        "total_species": row.total_species,
        "fully_enriched": row.fully_enriched,
        "with_any_data": row.with_any_data,
    }


def _fetch_work_list(
    client: bigquery.Client,
    species_table: str,
    enrichment_table: str,
    *,
    new_only: bool = False,
) -> list[SpeciesRow]:
    """
    STAGE 1: Fetch ALL species that need enrichment ONCE.
    Returns complete work list to process locally.
    """
    if new_only:
        query = f"""
            SELECT s.species, NULL AS common_name, NULL AS description,
                   NULL AS image_url, TRUE AS is_new
            FROM `{species_table}` AS s
            LEFT JOIN `{enrichment_table}` AS e ON s.species = e.species
            WHERE e.species IS NULL
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
        """

    logger.info("Fetching work list from BigQuery (this runs ONCE)...")
    df = client.query(query).to_dataframe()

    if df.empty:
        return []

    work_list = [
        SpeciesRow(
            species=str(row["species"]),
            common_name=str(row["common_name"]) if pd.notna(row["common_name"]) else None,
            description=str(row["description"]) if pd.notna(row["description"]) else None,
            image_url=str(row["image_url"]) if pd.notna(row["image_url"]) else None,
            is_new=bool(row["is_new"]),
        )
        for _, row in df.iterrows()
    ]

    logger.info("Fetched %d species to enrich", len(work_list))
    return work_list


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


def _load_checkpoint(checkpoint_file: Path) -> tuple[list[SpeciesRow], int]:
    """Load checkpoint: returns (completed_species, last_batch_idx)."""
    if not checkpoint_file.exists():
        return [], 0

    with checkpoint_file.open("r") as f:
        data = json.load(f)

    completed = [
        SpeciesRow(
            species=s["species"],
            common_name=s["common_name"],
            description=s["description"],
            image_url=s["image_url"],
            is_new=s["is_new"],
        )
        for s in data["completed"]
    ]

    return completed, data["last_batch_idx"]


def _save_checkpoint(checkpoint_file: Path, completed: list[SpeciesRow], last_batch_idx: int) -> None:
    """Save checkpoint of completed work."""
    CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)

    data = {
        "completed": [
            {
                "species": s.species,
                "common_name": s.common_name,
                "description": s.description,
                "image_url": s.image_url,
                "is_new": s.is_new,
            }
            for s in completed
        ],
        "last_batch_idx": last_batch_idx,
    }

    with checkpoint_file.open("w") as f:
        json.dump(data, f)

    logger.info("  Checkpoint saved: %d species completed", len(completed))


def _upload_results(client: bigquery.Client, enrichment_table: str, enriched: list[SpeciesRow]) -> None:
    """
    STAGE 3: Upload ALL enriched species in a single MERGE operation.
    This runs ONCE at the end.
    """
    if not enriched:
        logger.info("No results to upload")
        return

    new_count = sum(1 for s in enriched if s.is_new)
    update_count = len(enriched) - new_count

    logger.info(
        "Uploading %d enriched species to BigQuery (%d new, %d updated)...", len(enriched), new_count, update_count
    )

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
    logger.info("Upload complete: %d species saved to BigQuery", len(enriched))


def main() -> int:
    parser = argparse.ArgumentParser(description="Enrich species with common names, descriptions, and images")
    parser.add_argument(
        "--new-only",
        action="store_true",
        help="Only enrich species not yet in the enrichment table (skip retrying partial rows)",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume from checkpoint if exists (automatically loads partial progress)",
    )
    parser.add_argument(
        "--checkpoint-only",
        action="store_true",
        help="Upload checkpointed results to BigQuery without processing new species",
    )
    args = parser.parse_args()

    config = EnrichConfig.from_env()
    client = bigquery.Client(project=config.project_id)

    enrichment_table = config.enrichment_table_id
    species_table = config.species_table_id

    checkpoint_file = CHECKPOINT_DIR / "enrichment_progress.json"

    _ensure_enrichment_table(client, enrichment_table)

    # STAGE 0: Load checkpoint if resuming
    completed_species = []
    start_batch_idx = 0

    if args.resume or args.checkpoint_only:
        if checkpoint_file.exists():
            completed_species, start_batch_idx = _load_checkpoint(checkpoint_file)
            logger.info(
                "Loaded checkpoint: %d species already completed (resuming from batch %d)",
                len(completed_species),
                start_batch_idx + 1,
            )
        else:
            logger.info("No checkpoint found, starting fresh")
            if args.checkpoint_only:
                logger.error("--checkpoint-only requires existing checkpoint file")
                return 1

    # If --checkpoint-only, just upload and exit
    if args.checkpoint_only:
        _upload_results(client, enrichment_table, completed_species)
        checkpoint_file.unlink()
        logger.info("Checkpoint uploaded and cleared")
        return 0

    # STAGE 1: Fetch work list ONCE from BigQuery
    stats = _get_initial_stats(client, species_table, enrichment_table)
    mode = "new only" if args.new_only else "new + retry partial"
    logger.info(
        "Initial stats (%s): %s total species | %s fully enriched | %s with some data",
        mode,
        f"{stats['total_species']:,}",
        f"{stats['fully_enriched']:,}",
        f"{stats['with_any_data']:,}",
    )

    work_list = _fetch_work_list(
        client,
        species_table,
        enrichment_table,
        new_only=args.new_only,
    )

    if not work_list:
        logger.info("No species need enrichment")
        return 0

    # Filter out already completed species if resuming
    if completed_species:
        completed_names = {s.species for s in completed_species}
        work_list = [s for s in work_list if s.species not in completed_names]
        logger.info("After filtering completed species: %d remaining to process", len(work_list))

    if not work_list:
        logger.info("All species in work list already completed in checkpoint")
        _upload_results(client, enrichment_table, completed_species)
        checkpoint_file.unlink()
        return 0

    # STAGE 2: Process locally in batches (NO BigQuery queries here)
    logger.info(
        "Starting local enrichment: %d species to process in batches of %d",
        len(work_list),
        config.batch_size,
    )

    batch_num = start_batch_idx
    total_to_process = len(work_list)

    for batch_start in range(0, len(work_list), config.batch_size):
        batch_num += 1
        batch = work_list[batch_start : batch_start + config.batch_size]

        new_count = sum(1 for s in batch if s.is_new)
        retry_count = len(batch) - new_count

        logger.info(
            "Batch %d/%d: %d species (%d new, %d retrying partial)",
            batch_num,
            (total_to_process + config.batch_size - 1) // config.batch_size,
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

        # Add to completed list
        completed_species.extend(enriched)

        # Save checkpoint after each batch
        _save_checkpoint(checkpoint_file, completed_species, batch_num)

        # Show accurate progress
        processed_count = len(completed_species)
        progress_pct = (processed_count / total_to_process * 100) if total_to_process else 0
        logger.info(
            "  Progress: %s/%s species processed (%.1f%%)",
            f"{processed_count:,}",
            f"{total_to_process:,}",
            progress_pct,
        )

    # STAGE 3: Upload all results in one MERGE operation
    logger.info("Local enrichment complete. Uploading results to BigQuery...")
    _upload_results(client, enrichment_table, completed_species)

    # Clear checkpoint after successful upload
    if checkpoint_file.exists():
        checkpoint_file.unlink()
        logger.info("Checkpoint cleared")

    # Final stats
    final_stats = _get_initial_stats(client, species_table, enrichment_table)
    logger.info(
        "Enrichment complete: %s/%s fully enriched, %s with some data",
        f"{final_stats['fully_enriched']:,}",
        f"{final_stats['total_species']:,}",
        f"{final_stats['with_any_data']:,}",
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
