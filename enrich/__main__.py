import asyncio
import logging
import sys
import uuid

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


def _enrich_batch(species_names: list[str]) -> list[tuple]:
    """Run the 3-phase enrichment for a batch of species names."""
    # Phase 1: GBIF common names
    logger.info("  Phase 1/3: GBIF common names for %d species...", len(species_names))
    common_names = asyncio.run(get_common_names(species_names))

    # Phase 2: Wikipedia REST API (description + image)
    logger.info("  Phase 2/3: Wikipedia descriptions + images...")
    wikipedia_data = asyncio.run(get_wikipedia_data(species_names))

    # Phase 3: Wikidata images for species Wikipedia didn't cover
    species_without_image = [
        name for name in species_names
        if name not in wikipedia_data or wikipedia_data[name][1] is None
    ]
    wikidata_images: dict[str, str] = {}
    if species_without_image:
        logger.info("  Phase 3/3: Wikidata fallback images for %d species...", len(species_without_image))
        wikidata_images = asyncio.run(get_wikidata_images(species_without_image))

    # Merge results
    enriched = []
    for name in species_names:
        common = common_names.get(name)
        wp_desc, wp_img = wikipedia_data.get(name, (None, None))
        wd_img = wikidata_images.get(name)
        img = wp_img or wd_img
        if common is not None or wp_desc is not None or img is not None:
            enriched.append((name, common, wp_desc, img))

    return enriched


def main() -> int:
    config = EnrichConfig.from_env()
    client = bigquery.Client(project=config.project_id)

    batch_num = 0
    total_enriched = 0

    while True:
        batch_num += 1
        query = f"""
            SELECT species
            FROM `{config.full_table_id}`
            WHERE common_name IS NULL AND description IS NULL AND image_url IS NULL
            LIMIT {config.batch_size}
        """
        df = client.query(query).to_dataframe()

        if df.empty:
            break

        species_names = df["species"].tolist()
        logger.info("Batch %d: enriching %d species...", batch_num, len(species_names))

        enriched = _enrich_batch(species_names)

        logger.info(
            "Batch %d: %d/%d enriched (common=%d, desc=%d, img=%d)",
            batch_num, len(enriched), len(species_names),
            sum(1 for _, c, _, _ in enriched if c),
            sum(1 for _, _, d, _ in enriched if d),
            sum(1 for _, _, _, i in enriched if i),
        )

        if not enriched:
            logger.info("Batch %d: no results, stopping", batch_num)
            break

        # Upload to temp table and MERGE
        enriched_df = pd.DataFrame(enriched, columns=["species", "common_name", "description", "image_url"])
        temp_table_id = f"{config.project_id}.{config.bigquery_dataset}._temp_enrichment_{uuid.uuid4().hex[:8]}"

        job_config = bigquery.LoadJobConfig(write_disposition="WRITE_TRUNCATE")
        client.load_table_from_dataframe(enriched_df, temp_table_id, job_config=job_config).result()

        merge_query = f"""
            MERGE `{config.full_table_id}` AS target
            USING `{temp_table_id}` AS source
            ON target.species = source.species
            WHEN MATCHED THEN
                UPDATE SET
                    target.common_name = COALESCE(source.common_name, target.common_name),
                    target.description = COALESCE(source.description, target.description),
                    target.image_url = COALESCE(source.image_url, target.image_url)
        """
        client.query(merge_query).result()
        client.delete_table(temp_table_id, not_found_ok=True)

        total_enriched += len(enriched)
        logger.info("Batch %d complete. Total enriched so far: %d", batch_num, total_enriched)

        # If we got fewer than batch_size, we've processed all remaining species
        if len(species_names) < config.batch_size:
            break

    logger.info("Enrichment complete: %d species enriched in %d batches", total_enriched, batch_num)
    return 0


if __name__ == "__main__":
    sys.exit(main())
