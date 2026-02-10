import os
from dataclasses import dataclass


@dataclass
class EnrichConfig:
    project_id: str
    bigquery_dataset: str
    species_table: str = "species"
    batch_size: int = 500

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
            species_table=os.environ.get("SPECIES_TABLE", "species"),
            batch_size=int(os.environ.get("ENRICH_BATCH_SIZE", "500")),
        )

    @property
    def full_table_id(self) -> str:
        return f"{self.project_id}.{self.bigquery_dataset}.{self.species_table}"
