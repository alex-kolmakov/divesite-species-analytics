"""Application configuration from environment variables."""

import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Config:
    """App settings — falls back to local dev defaults."""

    gcs_bucket: str = field(default_factory=lambda: os.environ.get("GCS_BUCKET", ""))
    export_prefix: str = field(default_factory=lambda: os.environ.get("EXPORT_PREFIX", "app-export"))
    port: int = field(default_factory=lambda: int(os.environ.get("PORT", "8080")))
    local_data_dir: str = field(default_factory=lambda: os.environ.get("LOCAL_DATA_DIR", "data"))

    # The three tables the UI needs
    tables: tuple[str, ...] = (
        "species_divesite_summary",
        "divesite_species_detail",
        "divesite_summary",
    )

    @property
    def use_gcs(self) -> bool:
        """True when GCS_BUCKET is set (production); False for local dev."""
        return bool(self.gcs_bucket)


config = Config()
