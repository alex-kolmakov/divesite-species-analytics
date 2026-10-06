import logging
import os
from pathlib import Path

import pandas as pd
from dwca.read import DwCAReader

from ingest.config import Config
from ingest.download import download
from ingest.upload import upload_to_gcs

logger = logging.getLogger(__name__)

TAXON_COLUMNS = ["id", "scientificName", "kingdom", "phylum", "class", "genus", "specificEpithet", "taxonRank"]


def build_redlist(taxa: pd.DataFrame, distribution: pd.DataFrame) -> pd.DataFrame:
    """One row per Red List taxon with its global category and a bare species name.

    scientificName carries the author ("Calocedrus rupestris Aver., Hiep & L.K.Phan"), so it never
    equals the bare names in occurrences; canonicalName ("Calocedrus rupestris") is what to join on.
    The category (Least Concern ... Critically Endangered) lives in the distribution extension,
    one global row per taxon; categories are lower-cased because the source mixes cases.
    """
    df = taxa[TAXON_COLUMNS].copy()
    is_species = df["taxonRank"].str.lower().eq("species") & df["genus"].notna() & df["specificEpithet"].notna()
    df["canonicalName"] = df["genus"].str.cat(df["specificEpithet"], sep=" ").where(is_species)

    status = distribution[["coreid", "threatStatus"]].drop_duplicates(subset="coreid")
    status = status.rename(columns={"coreid": "id"})
    df = df.merge(status, on="id", how="left")
    df["threatStatus"] = df["threatStatus"].str.strip().str.lower()
    return df


def ingest_iucn(config: Config) -> None:
    """Download the IUCN Red List DwCA, attach each taxon's category, write parquet, upload to GCS."""
    os.makedirs(config.temp_dir, exist_ok=True)
    zip_path = os.path.join(config.temp_dir, "iucn.zip")
    parquet_path = os.path.join(config.temp_dir, "redlist.parquet")

    download(config.iucn_redlist_url, zip_path)

    with DwCAReader(zip_path) as dwca:
        taxa = dwca.pd_read(dwca.descriptor.core.file_location, dtype=str)  # pyrefly: ignore[missing-attribute]
        distribution = dwca.pd_read("distribution.txt", dtype=str)

    df = build_redlist(taxa, distribution)
    logger.info(
        "IUCN: %d taxa, %d with a species name, categories: %s",
        len(df),
        df["canonicalName"].notna().sum(),
        df["threatStatus"].value_counts().to_dict(),
    )
    df.to_parquet(parquet_path, engine="pyarrow", compression="snappy", index=False)
    upload_to_gcs(parquet_path, config.gcs_bucket, "redlist.parquet", project=config.project_id)

    for f in [zip_path, parquet_path]:
        Path(f).unlink(missing_ok=True)

    logger.info("IUCN ingestion complete")
