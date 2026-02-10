import os
import tempfile
from dataclasses import dataclass, field


@dataclass
class Config:
    project_id: str
    gcs_bucket: str
    iucn_redlist_url: str
    gisd_url: str
    worms_url_template: str
    base_padi_guide_url: str
    base_padi_map_url: str
    worms_login: str = ""
    worms_password: str = ""
    temp_dir: str = field(default_factory=lambda: os.path.join(tempfile.gettempdir(), "marine-data"))

    @classmethod
    def from_env(cls) -> "Config":
        def require(key: str) -> str:
            val = os.environ.get(key)
            if not val:
                raise OSError(f"Missing required environment variable: {key}")
            return val.strip("'\"")

        def optional(key: str, default: str = "") -> str:
            return os.environ.get(key, default).strip("'\"")

        return cls(
            project_id=require("PROJECT_ID"),
            gcs_bucket=require("GCS_BUCKET"),
            iucn_redlist_url=require("IUCN_REDLIST_URL"),
            gisd_url=require("GISD_URL"),
            worms_url_template=require("WORMS_URL_TEMPLATE"),
            base_padi_guide_url=require("BASE_PADI_GUIDE_URL"),
            base_padi_map_url=require("BASE_PADI_MAP_URL"),
            worms_login=optional("WORMS_LOGIN"),
            worms_password=optional("WORMS_PASSWORD"),
            temp_dir=optional("TEMP_DIR", os.path.join(tempfile.gettempdir(), "marine-data")),
        )
