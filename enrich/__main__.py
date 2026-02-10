import asyncio
import logging
import sys
import uuid

import pandas as pd
from google.cloud import bigquery

from enrich.config import EnrichConfig
from enrich.wikipedia import enrich_species_batch

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def main() -> int:
    config = EnrichConfig.from_env()
    client = bigquery.Client(project=config.project_id)

    # Query species missing enrichment data
    query = f"""
        SELECT species
        FROM `{config.full_table_id}`
        WHERE Common_name IS NULL OR Image_URL IS NULL
        LIMIT {config.batch_size}
    """
    logger.info("Querying species to enrich from %s", config.full_table_id)
    df = client.query(query).to_dataframe()

    if df.empty:
        logger.info("No species to enrich")
        return 0

    species_names = df["species"].tolist()
    logger.info("Enriching %d species via Wikipedia", len(species_names))

    results = asyncio.run(enrich_species_batch(species_names))

    # Filter out results where both fields are None
    enriched = [(name, common, img) for name, common, img in results if common is not None or img is not None]
    logger.info("Got enrichment data for %d/%d species", len(enriched), len(species_names))

    if not enriched:
        logger.info("No enrichment results to write")
        return 0

    # Upload to a temp table, then MERGE into the species table
    enriched_df = pd.DataFrame(enriched, columns=["species", "Common_name", "Image_URL"])
    temp_table_id = f"{config.project_id}.{config.bigquery_dataset}._temp_enrichment_{uuid.uuid4().hex[:8]}"

    logger.info("Loading enrichment data to temp table %s", temp_table_id)
    job_config = bigquery.LoadJobConfig(write_disposition="WRITE_TRUNCATE")
    client.load_table_from_dataframe(enriched_df, temp_table_id, job_config=job_config).result()

    # MERGE enrichment data into species table
    merge_query = f"""
        MERGE `{config.full_table_id}` AS target
        USING `{temp_table_id}` AS source
        ON target.species = source.species
        WHEN MATCHED THEN
            UPDATE SET
                target.Common_name = COALESCE(source.Common_name, target.Common_name),
                target.Image_URL = COALESCE(source.Image_URL, target.Image_URL)
    """
    logger.info("Merging enrichment data into %s", config.full_table_id)
    client.query(merge_query).result()

    # Clean up temp table
    client.delete_table(temp_table_id, not_found_ok=True)
    logger.info("Enrichment complete")
    return 0


if __name__ == "__main__":
    sys.exit(main())
