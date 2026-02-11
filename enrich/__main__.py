import asyncio
import logging
import sys

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


def _ensure_enrichment_table(client: bigquery.Client, table_id: str) -> None:
    """Create the species_enrichment table if it doesn't exist."""
    table = bigquery.Table(table_id, schema=ENRICHMENT_SCHEMA)
    client.create_table(table, exists_ok=True)
    logger.info("Enrichment table ready: %s", table_id)


def _enrich_batch(species_names: list[str]) -> list[tuple]:
    """Run the 3-phase enrichment for a batch of species names.

    Returns a row for EVERY species (not just those with results), so all
    attempted species get recorded in the enrichment table and are never
    re-queried.
    """
    # Phase 1: GBIF common names
    logger.info("  Phase 1/3: GBIF common names for %d species...", len(species_names))
    common_names = asyncio.run(get_common_names(species_names))

    # Phase 2: Wikipedia REST API (description + image)
    logger.info("  Phase 2/3: Wikipedia descriptions + images...")
    wikipedia_data = asyncio.run(get_wikipedia_data(species_names))

    # Phase 3: Wikidata images for species Wikipedia didn't cover
    species_without_image = [
        name for name in species_names if name not in wikipedia_data or wikipedia_data[name][1] is None
    ]
    wikidata_images: dict[str, str] = {}
    if species_without_image:
        logger.info("  Phase 3/3: Wikidata fallback images for %d species...", len(species_without_image))
        wikidata_images = asyncio.run(get_wikidata_images(species_without_image))

    # Merge results — include ALL species so they're marked as attempted
    rows = []
    for name in species_names:
        common = common_names.get(name)
        wp_desc, wp_img = wikipedia_data.get(name, (None, None))
        wd_img = wikidata_images.get(name)
        img = wp_img or wd_img
        rows.append((name, common, wp_desc, img))

    return rows


def main() -> int:
    config = EnrichConfig.from_env()
    client = bigquery.Client(project=config.project_id)

    enrichment_table = config.enrichment_table_id
    species_table = config.species_table_id

    _ensure_enrichment_table(client, enrichment_table)

    batch_num = 0
    total_attempted = 0
    total_with_data = 0

    while True:
        batch_num += 1
        # Find species not yet in the enrichment table
        query = f"""
            SELECT s.species
            FROM `{species_table}` AS s
            LEFT JOIN `{enrichment_table}` AS e ON s.species = e.species
            WHERE e.species IS NULL
            LIMIT {config.batch_size}
        """
        df = client.query(query).to_dataframe()

        if df.empty:
            break

        species_names = df["species"].tolist()
        logger.info("Batch %d: enriching %d species...", batch_num, len(species_names))

        rows = _enrich_batch(species_names)
        with_data = sum(1 for _, c, d, i in rows if c or d or i)

        logger.info(
            "Batch %d: %d/%d with data (common=%d, desc=%d, img=%d)",
            batch_num,
            with_data,
            len(species_names),
            sum(1 for _, c, _, _ in rows if c),
            sum(1 for _, _, d, _ in rows if d),
            sum(1 for _, _, _, i in rows if i),
        )

        # Insert ALL attempted species (including those with no data)
        enriched_df = pd.DataFrame(rows, columns=["species", "common_name", "description", "image_url"])
        job_config = bigquery.LoadJobConfig(write_disposition="WRITE_APPEND")
        client.load_table_from_dataframe(enriched_df, enrichment_table, job_config=job_config).result()

        total_attempted += len(rows)
        total_with_data += with_data
        logger.info("Batch %d complete. %d attempted, %d with data", batch_num, total_attempted, total_with_data)

        if len(species_names) < config.batch_size:
            break

    logger.info(
        "Enrichment complete: %d species attempted, %d with data in %d batches",
        total_attempted,
        total_with_data,
        batch_num,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
