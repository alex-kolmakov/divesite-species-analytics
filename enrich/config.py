import os
from dataclasses import dataclass


@dataclass
class EnrichConfig:
    project_id: str
    bigquery_dataset: str
    batch_size: int = 500
    # Results are merged into BigQuery every this many species, so a killed job loses little
    flush_size: int = 2000
    # A field that found nothing is tried again after this many days
    retry_days: int = 90

    @classmethod
    def from_env(cls) -> "EnrichConfig":
        def require(key: str) -> str:
            val = os.environ.get(key)
            if not val:
                raise OSError(f"Missing required environment variable: {key}")
            return val.strip("'\"")

        return cls(
            project_id=require("PROJECT_ID"),
            bigquery_dataset=require("BIGQUERY_DATASET"),
            batch_size=int(os.environ.get("ENRICH_BATCH_SIZE", "500")),
            flush_size=int(os.environ.get("ENRICH_FLUSH_SIZE", "2000")),
            retry_days=int(os.environ.get("ENRICH_RETRY_DAYS", "90")),
        )

    @property
    def target_species_table_id(self) -> str:
        """The species the app shows: every species recorded near a dive site, with its site count."""
        return f"{self.project_id}.{self.bigquery_dataset}.species_summary"

    @property
    def enrichment_table_id(self) -> str:
        return f"{self.project_id}.{self.bigquery_dataset}.species_enrichment"
