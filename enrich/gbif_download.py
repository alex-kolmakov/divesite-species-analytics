"""Photos from GBIF occurrence records for every species still without an image, in one download.

GBIF's occurrence search throttles long runs and asks bulk users for a download instead, so the
backfill runs `python -m enrich --no-occurrence-photos` and this fills the gaps afterwards:

1. species at dive sites that the pipeline has processed and found no image for
2. their GBIF usage keys, in one download request: records of those taxa with a still image
3. per species the first photo with an allowed license, field observations before specimens
   (the same choice as enrich.gbif.pick_occurrence_image makes from a search page)
4. merged into the enrichment table, only where the image is still empty

    python -m enrich.gbif_download              # request, wait, read, merge
    python -m enrich.gbif_download --key <key>  # reuse a download that was already requested

Needs GBIF_USER and GBIF_PWD (a free gbif.org account). The download is listed publicly under that
account with a DOI.
"""

import argparse
import asyncio
import base64
import csv
import io
import json
import logging
import os
import sys
import tempfile
import time
import urllib.error
import urllib.request
import uuid
import zipfile
from collections import defaultdict
from dataclasses import asdict
from pathlib import Path
from typing import Any

import pandas as pd
from google.cloud import bigquery

from enrich.config import EnrichConfig
from enrich.gbif import GBIF_API, HEADERS, OccurrenceImage, match_species, pick_occurrence_image

logger = logging.getLogger(__name__)

POLL_SECONDS = 30
# Records kept per species and kind (field observation / other) while reading the archive: enough
# to find one with an allowed license without holding every record of a common species in memory
CANDIDATES = 50
MAX_ARCHIVE_GB = 30

FIELD_OBSERVATION = "HUMAN_OBSERVATION"

PHOTO_SCHEMA = [
    bigquery.SchemaField("species", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("image_url", "STRING"),
    bigquery.SchemaField("image_page_url", "STRING"),
    bigquery.SchemaField("image_credit", "STRING"),
    bigquery.SchemaField("image_license", "STRING"),
    bigquery.SchemaField("image_license_url", "STRING"),
]


def _call(url: str, *, auth: tuple[str, str] | None = None, body: dict[str, Any] | None = None) -> str:
    headers = dict(HEADERS)
    if auth:
        headers["Authorization"] = "Basic " + base64.b64encode(":".join(auth).encode()).decode()
    data = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode()
    request = urllib.request.Request(url, data=data, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            return response.read().decode()
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"GBIF {e.code} for {url}: {e.read().decode()[:500]}") from e


def species_without_image_query(target_table: str, enrichment_table: str, limit: int | None) -> str:
    """Species the pipeline has processed and found no image for, most widespread first."""
    return f"""
        SELECT t.species
        FROM `{target_table}` AS t
        JOIN `{enrichment_table}` AS e ON t.species = e.species
        WHERE e.attempted_at IS NOT NULL AND e.image_url IS NULL
        ORDER BY t.total_sites DESC, t.species
        {f"LIMIT {int(limit)}" if limit else ""}
    """


def download_request(creator: str, usage_keys: list[int]) -> dict[str, Any]:
    return {
        "creator": creator,
        "sendNotification": False,
        "format": "DWCA",
        "predicate": {
            "type": "and",
            "predicates": [
                {"type": "in", "key": "TAXON_KEY", "values": [str(k) for k in sorted(set(usage_keys))]},
                {"type": "equals", "key": "MEDIA_TYPE", "value": "StillImage"},
            ],
        },
    }


def request_download(usage_keys: list[int]) -> str:
    auth = (os.environ["GBIF_USER"], os.environ["GBIF_PWD"])
    # The request wants the account's username; GBIF_USER may be the email it logs in with
    creator = json.loads(_call(f"{GBIF_API}/user/login", auth=auth))["userName"]
    key = _call(f"{GBIF_API}/occurrence/download/request", auth=auth, body=download_request(creator, usage_keys))
    logger.info("Requested GBIF download %s for %d taxa", key, len(set(usage_keys)))
    return key.strip()


def wait_for_download(key: str) -> dict[str, Any]:
    """Poll until the download is ready. Returns its metadata (size, totalRecords, doi)."""
    while True:
        meta = json.loads(_call(f"{GBIF_API}/occurrence/download/{key}"))
        status = meta["status"]
        if status == "SUCCEEDED":
            logger.info(
                "Download %s ready: %s records, %.2f GB, doi %s",
                key,
                meta.get("totalRecords"),
                (meta.get("size") or 0) / 1e9,
                meta.get("doi"),
            )
            return meta
        if status not in ("PREPARING", "RUNNING", "SUSPENDED"):
            raise RuntimeError(f"GBIF download {key} ended as {status}")
        logger.info("Download %s is %s", key, status)
        time.sleep(POLL_SECONDS)


def fetch_archive(key: str, directory: Path) -> Path:
    path = directory / f"{key}.zip"
    request = urllib.request.Request(f"{GBIF_API}/occurrence/download/request/{key}.zip", headers=HEADERS)
    with urllib.request.urlopen(request, timeout=600) as response, path.open("wb") as out:
        while chunk := response.read(1 << 20):
            out.write(chunk)
    return path


def _rows(archive: zipfile.ZipFile, member: str):
    """Rows of a tab-separated archive member as dicts. GBIF writes no quoting."""
    csv.field_size_limit(sys.maxsize)
    with archive.open(member) as raw:
        reader = csv.reader(io.TextIOWrapper(raw, encoding="utf-8", newline=""), delimiter="\t", quoting=csv.QUOTE_NONE)
        header = next(reader)
        for row in reader:
            yield dict(zip(header, row, strict=False))


def read_photos(archive_path: Path, species_by_key: dict[int, list[str]]) -> dict[str, OccurrenceImage]:
    """The photo to show per species from a GBIF download archive.

    species_by_key maps the requested usage keys to our species names. A record belongs to a
    species when its taxon, accepted taxon or species key is one of them (GBIF returns synonyms).
    """
    # species → kind → records, in archive order
    records: dict[str, dict[bool, list[dict[str, Any]]]] = defaultdict(lambda: {True: [], False: []})
    by_id: dict[str, dict[str, Any]] = {}

    with zipfile.ZipFile(archive_path) as archive:
        for row in _rows(archive, "occurrence.txt"):
            names: list[str] = []
            for column in ("taxonKey", "acceptedTaxonKey", "speciesKey"):
                value = row.get(column) or ""
                names = species_by_key.get(int(value), []) if value.isdigit() else []
                if names:
                    break
            if not names:
                continue
            record = {
                "key": row["gbifID"],
                "license": row.get("license"),
                "recordedBy": row.get("recordedBy") or None,
                "institutionCode": row.get("institutionCode") or None,
                "datasetName": row.get("datasetName") or None,
                "media": [],
            }
            kind = row.get("basisOfRecord") == FIELD_OBSERVATION
            for name in names:
                if len(records[name][kind]) < CANDIDATES:
                    records[name][kind].append(record)
                    by_id[record["key"]] = record

        for row in _rows(archive, "multimedia.txt"):
            record = by_id.get(row["gbifID"])
            if record is not None:
                record["media"].append({k: v or None for k, v in row.items()})

    photos: dict[str, OccurrenceImage] = {}
    for name, kinds in records.items():
        image = pick_occurrence_image(kinds[True] + kinds[False])
        if image:
            photos[name] = image
    logger.info("GBIF download: photos for %d of %d species with records", len(photos), len(records))
    return photos


def photo_merge_query(enrichment_table: str, staging_table: str) -> str:
    """Fill the image of species that still have none. Never replaces an image."""
    columns = [f.name for f in PHOTO_SCHEMA if f.name != "species"]
    sets = ",\n            ".join(f"{c} = s.{c}" for c in columns)
    return f"""
        MERGE `{enrichment_table}` AS t
        USING `{staging_table}` AS s
        ON t.species = s.species
        WHEN MATCHED AND t.image_url IS NULL THEN UPDATE SET
            {sets},
            image_source = 'gbif_occurrence'
    """


def _merge(client: bigquery.Client, enrichment_table: str, photos: dict[str, OccurrenceImage]) -> None:
    rows = []
    for species, image in photos.items():
        fields = asdict(image)
        rows.append(
            {
                "species": species,
                "image_url": fields["image_url"],
                "image_page_url": fields["page_url"],
                "image_credit": fields["credit"],
                "image_license": fields["license"],
                "image_license_url": fields["license_url"],
            }
        )
    staging = f"{enrichment_table}_photos_{uuid.uuid4().hex[:8]}"
    job_config = bigquery.LoadJobConfig(write_disposition="WRITE_TRUNCATE", schema=PHOTO_SCHEMA)
    try:
        client.load_table_from_dataframe(pd.DataFrame(rows), staging, job_config=job_config).result()
        job = client.query(photo_merge_query(enrichment_table, staging))
        job.result()
        logger.info("Filled the image of %s species in %s", job.num_dml_affected_rows, enrichment_table)
    finally:
        client.delete_table(staging, not_found_ok=True)


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    parser = argparse.ArgumentParser(description="Fill missing species images from one GBIF occurrence download")
    parser.add_argument("--key", help="Reuse this GBIF download instead of requesting a new one")
    parser.add_argument("--limit", type=int, help="Only the first N species without an image (most widespread first)")
    parser.add_argument("--dry-run", action="store_true", help="Read the photos but write nothing to BigQuery")
    args = parser.parse_args()

    config = EnrichConfig.from_env()
    client = bigquery.Client(project=config.project_id)
    query = species_without_image_query(config.target_species_table_id, config.enrichment_table_id, args.limit)
    species = [str(r.species) for r in client.query(query).result()]
    logger.info("%d species without an image", len(species))
    if not species:
        return 0

    usage_keys = asyncio.run(match_species(species))
    species_by_key: dict[int, list[str]] = defaultdict(list)
    for name, usage_key in usage_keys.items():
        species_by_key[usage_key].append(name)

    key = args.key or request_download(list(species_by_key))
    meta = wait_for_download(key)
    if (meta.get("size") or 0) > MAX_ARCHIVE_GB * 1e9:
        raise RuntimeError(f"Download {key} is over {MAX_ARCHIVE_GB} GB; ask for fewer species (--limit)")

    with tempfile.TemporaryDirectory() as tmp:
        photos = read_photos(fetch_archive(key, Path(tmp)), species_by_key)

    if args.dry_run:
        logger.info("Dry run, nothing written")
        for name, image in list(photos.items())[:5]:
            logger.info("  %s | %s | %s | %s", name, image.license, image.credit, image.image_url)
        return 0
    if photos:
        _merge(client, config.enrichment_table_id, photos)
    return 0


if __name__ == "__main__":
    sys.exit(main())
