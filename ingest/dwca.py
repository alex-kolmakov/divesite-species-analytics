import logging
from pathlib import Path

from dwca.read import DwCAReader

logger = logging.getLogger(__name__)


def parse_dwca_to_parquet(dwca_path: str | Path, output_path: str | Path) -> Path:
    """Parse a Darwin Core Archive zip into a Parquet file.

    No semantic transforms - just format conversion with snappy compression.
    """
    dwca_path = Path(dwca_path)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    logger.info("Parsing DwCA: %s", dwca_path)

    with DwCAReader(str(dwca_path)) as dwca:
        core_file = dwca.descriptor.core.file_location  # pyrefly: ignore[missing-attribute]
        logger.info("Core data file: %s", core_file)

        df = dwca.pd_read(core_file, parse_dates=True)
        logger.info("Parsed %d rows, %d columns", len(df), len(df.columns))

        df.to_parquet(str(output_path), engine="pyarrow", compression="snappy", index=False)

    logger.info("Wrote parquet: %s", output_path)
    return output_path
