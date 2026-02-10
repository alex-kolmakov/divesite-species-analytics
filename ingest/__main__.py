import argparse
import logging
import sys
import time

from ingest.config import Config
from ingest.sources.divesites import ingest_divesites
from ingest.sources.gisd import ingest_gisd
from ingest.sources.iucn import ingest_iucn
from ingest.sources.obis import ingest_obis
from ingest.sources.worms import ingest_worms

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

SOURCES = {
    "obis": ingest_obis,
    "iucn": ingest_iucn,
    "gisd": ingest_gisd,
    "worms": ingest_worms,
    "divesites": ingest_divesites,
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Marine data ingestion pipeline")
    parser.add_argument(
        "--source",
        default="all",
        help="Source(s) to ingest: 'all' or comma-separated list (obis,iucn,gisd,worms,divesites)",
    )
    args = parser.parse_args()

    config = Config.from_env()

    if args.source == "all":
        sources_to_run = list(SOURCES.keys())
    else:
        sources_to_run = [s.strip() for s in args.source.split(",")]
        invalid = [s for s in sources_to_run if s not in SOURCES]
        if invalid:
            logger.error("Unknown sources: %s. Available: %s", invalid, list(SOURCES.keys()))
            return 1

    logger.info("Starting ingestion for: %s", sources_to_run)
    failures = []

    for source_name in sources_to_run:
        logger.info("─── %s ───", source_name.upper())
        start = time.time()
        try:
            SOURCES[source_name](config)
            elapsed = time.time() - start
            logger.info("✓ %s completed in %.1fs", source_name, elapsed)
        except Exception:
            elapsed = time.time() - start
            logger.exception("✗ %s failed after %.1fs", source_name, elapsed)
            failures.append(source_name)

    if failures:
        logger.error("Failed sources: %s", failures)
        return 1

    logger.info("All sources ingested successfully")
    return 0


if __name__ == "__main__":
    sys.exit(main())
