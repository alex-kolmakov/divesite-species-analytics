"""WRiMS (World Register of Introduced Marine Species): where each species is alien, and how invasive.

Invasiveness depends on place (lionfish: invasive in the Caribbean, native in the Red Sea), so this
source keeps one row per species x Marine Regions area, plus each area's boundary for dbt to join
dive sites against.

- Species list: WRiMS as indexed by GBIF (public API; the WoRMS bulk export needs extra permission).
- Distributions: WoRMS REST /AphiaDistributionsByAphiaID (public), Alien records only.
- Boundaries: Marine Regions REST, WKT per MRGID.
"""

import asyncio
import json
import logging
import os
import re
from pathlib import Path
from typing import Any

import aiohttp
import pandas as pd
import requests
import shapely
from shapely import wkt as shapely_wkt

from ingest.config import Config
from ingest.upload import upload_to_gcs

logger = logging.getLogger(__name__)

WRIMS_GBIF_DATASET = "0a2eaf0c-5504-4f48-a47f-c94229029dc8"
GBIF_SPECIES_SEARCH = "https://api.gbif.org/v1/species/search"
WORMS_DISTRIBUTIONS = "https://www.marinespecies.org/rest/AphiaDistributionsByAphiaID/{aphia_id}"
MARINE_REGIONS_GEOMETRY = "https://www.marineregions.org/rest/getGazetteerGeometries.jsonld/{mrgid}/"
MARINE_REGIONS_RECORD = "https://www.marineregions.org/rest/getGazetteerRecordByMRGID.json/{mrgid}/"
# Places without a boundary (harbours, cities, islands: Hong Kong, Cape Town, Kerguelen) fall back to
# their gazetteer bounding box, or to a radius around their point.
POINT_RADIUS_DEGREES = 0.25  # ~25 km
# WoRMS REST answers 429 at 8 parallel requests (2026-10-06); 3 with a short pause each holds.
MAX_CONCURRENT = 3
REQUEST_PAUSE_SECONDS = 0.2
REQUEST_ATTEMPTS = 6
# Boundaries run to 38 MB of WKT (North Atlantic). ~1 km is plenty to place a dive site in a sea
# area; dbt also allows a few km for shore sites.
SIMPLIFY_DEGREES = 0.01
GRADED_INVASIVE = ["Invasive", "Of concern"]
MAX_MISSING_REGIONS = 0.05  # fail the run if more than 5% of boundaries can't be fetched or parsed

APHIA_ID = re.compile(r"marinespecies\.org:taxname:(\d+)")
MRGID = re.compile(r"mrgid/(\d+)")
CRS_PREFIX = re.compile(r"^\s*<[^>]*>\s*")


def list_wrims_species() -> pd.DataFrame:
    """Accepted WRiMS species from GBIF, with their WoRMS AphiaID."""
    rows, offset = [], 0
    while True:
        params: dict[str, Any] = {"datasetKey": WRIMS_GBIF_DATASET, "rank": "SPECIES", "limit": 1000, "offset": offset}
        resp = requests.get(GBIF_SPECIES_SEARCH, params=params, timeout=60)
        resp.raise_for_status()
        page = resp.json()
        for r in page["results"]:
            match = APHIA_ID.search(r.get("taxonID") or "")
            if match and r.get("taxonomicStatus") == "ACCEPTED" and r.get("canonicalName"):
                rows.append({"aphia_id": int(match.group(1)), "species": r["canonicalName"]})
        offset += 1000
        if page["endOfRecords"]:
            break
    return pd.DataFrame(rows).drop_duplicates(subset="aphia_id")


def parse_distributions(aphia_id: int, species: str, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Alien records with a Marine Regions ID, one row each."""
    rows = []
    for r in records:
        if (r.get("establishmentMeans") or "").lower() != "alien":
            continue
        match = MRGID.search(r.get("locationID") or "")
        if not match:
            continue
        rows.append(
            {
                "aphia_id": aphia_id,
                "species": species,
                "mrgid": int(match.group(1)),
                "locality": r.get("locality"),
                # Invasive / Of concern / Uncertain / Not specified / null
                "invasiveness": r.get("invasiveness"),
                "record_status": r.get("recordStatus"),
                "quality_status": r.get("qualityStatus"),
            }
        )
    return rows


def parse_geometry(jsonld: str) -> str | None:
    """Union of the polygons in a Marine Regions geometry response, simplified, as WKT.

    A response holds one geometry per source, each prefixed with its CRS ("<http://...CRS84> POLYGON ...").
    """
    doc = json.loads(jsonld)
    shapes = []
    for g in doc.get("mr:hasGeometry", []):
        text = CRS_PREFIX.sub("", g.get("gsp:asWKT") or "")
        if not text:  # some sources carry only the CRS prefix
            continue
        try:
            shape = shapely_wkt.loads(text)
        except shapely.errors.GEOSException:
            logger.debug("Unparseable geometry (%d chars) skipped", len(text))
            continue
        if shape.geom_type in ("Polygon", "MultiPolygon"):
            shapes.append(shapely.make_valid(shape))
    if not shapes:
        return None
    merged = shapely.union_all(shapes).simplify(SIMPLIFY_DEGREES, preserve_topology=True)
    return merged.wkt


def fallback_geometry(record: dict[str, Any]) -> str | None:
    """Bounding box from a gazetteer record, else a radius around its point, as WKT.

    Some records have min/max swapped (Kerguelen: minLongitude 71.85, maxLongitude 66.77), so
    corners are sorted. A box that is a line or a point is replaced by the radius.
    """
    lats = [float(v) for v in (record.get("minLatitude"), record.get("maxLatitude")) if v is not None]
    lons = [float(v) for v in (record.get("minLongitude"), record.get("maxLongitude")) if v is not None]
    if len(lats) == 2 and len(lons) == 2 and lats[0] != lats[1] and lons[0] != lons[1]:
        return shapely.box(min(lons), min(lats), max(lons), max(lats)).wkt
    lat, lon = record.get("latitude"), record.get("longitude")
    if lat is None or lon is None:
        return None
    return shapely.Point(lon, lat).buffer(POINT_RADIUS_DEGREES).wkt


async def _get(
    session: aiohttp.ClientSession, sem: asyncio.Semaphore, url: str, timeout_seconds: float = 120
) -> str | None:
    """GET with retries. Returns the body, or None for 204/404 (nothing recorded).

    Backs off on errors, waiting at least as long as a 429's Retry-After asks.
    """
    for attempt in range(REQUEST_ATTEMPTS):
        wait = 2.0 * 2**attempt
        try:
            async with sem:
                await asyncio.sleep(REQUEST_PAUSE_SECONDS)
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=timeout_seconds)) as resp:
                    if resp.status in (204, 404):
                        return None
                    if resp.status == 429:
                        wait = max(wait, float(resp.headers.get("Retry-After", 0) or 0))
                    resp.raise_for_status()
                    return await resp.text()
        except (aiohttp.ClientError, TimeoutError) as e:
            if attempt == REQUEST_ATTEMPTS - 1:
                raise RuntimeError(f"{url} failed after {REQUEST_ATTEMPTS} attempts: {e}") from e
            logger.warning("%s: %s — retrying in %.0fs", url, e, wait)
            await asyncio.sleep(wait)
    return None


async def _fetch_distributions(species: pd.DataFrame) -> pd.DataFrame:
    sem = asyncio.Semaphore(MAX_CONCURRENT)
    async with aiohttp.ClientSession() as session:

        async def distributions(aphia_id: int, name: str) -> list[dict[str, Any]]:
            body = await _get(session, sem, WORMS_DISTRIBUTIONS.format(aphia_id=aphia_id))
            return parse_distributions(aphia_id, name, json.loads(body)) if body else []

        nested = await asyncio.gather(
            *(distributions(a, s) for a, s in zip(species["aphia_id"], species["species"], strict=True))
        )
    return pd.DataFrame([row for rows in nested for row in rows])


async def _fetch_regions(mrgids: list[int]) -> pd.DataFrame:
    """Boundary per area. An area that can't be fetched or parsed is logged and skipped."""
    sem = asyncio.Semaphore(MAX_CONCURRENT)
    failed: list[tuple[int, str]] = []
    async with aiohttp.ClientSession() as session:

        async def region(mrgid: int) -> dict[str, Any] | None:
            try:
                body = await _get(session, sem, MARINE_REGIONS_GEOMETRY.format(mrgid=mrgid), timeout_seconds=300)
                wkt = parse_geometry(body) if body else None
                if wkt:
                    return {"mrgid": mrgid, "wkt": wkt, "geometry_source": "boundary"}
                record = await _get(session, sem, MARINE_REGIONS_RECORD.format(mrgid=mrgid))
                wkt = fallback_geometry(json.loads(record)) if record else None
                if wkt:
                    return {"mrgid": mrgid, "wkt": wkt, "geometry_source": "bbox_or_point"}
                failed.append((mrgid, "no boundary, box or point"))
            except Exception as e:  # one broken area must not sink the rest
                failed.append((mrgid, f"{type(e).__name__}: {e}"[:200]))
            return None

        results = await asyncio.gather(*(region(m) for m in mrgids))

    regions = pd.DataFrame([r for r in results if r])
    for mrgid, err in failed:
        logger.warning("Marine Regions %d skipped: %s", mrgid, err)
    logger.info(
        "Marine Regions: %d of %d areas (%s), %d failed",
        len(regions),
        len(mrgids),
        regions["geometry_source"].value_counts().to_dict() if len(regions) else {},
        len(failed),
    )
    if len(regions) < (1 - MAX_MISSING_REGIONS) * len(mrgids):
        raise RuntimeError(f"Marine Regions: only {len(regions)} of {len(mrgids)} boundaries")
    return regions


def ingest_wrims(config: Config) -> None:
    """Fetch WRiMS alien distributions and their region boundaries, write two parquets, upload to GCS.

    The distributions (~10 min of throttled WoRMS calls) are checkpointed in temp_dir, so a rerun
    after a boundary failure starts from the boundaries.
    """
    os.makedirs(config.temp_dir, exist_ok=True)
    alien_path = os.path.join(config.temp_dir, "wrims.parquet")
    regions_path = os.path.join(config.temp_dir, "wrims_regions.parquet")

    if os.path.exists(alien_path):
        alien = pd.read_parquet(alien_path)
        logger.info("WRiMS: reusing checkpoint %s", alien_path)
    else:
        species = list_wrims_species()
        logger.info("WRiMS: %d accepted species", len(species))
        alien = asyncio.run(_fetch_distributions(species))
        alien.to_parquet(alien_path, engine="pyarrow", compression="zstd", index=False)
    logger.info("WRiMS: %d alien records for %d species", len(alien), alien["aphia_id"].nunique())

    # Only areas where a species is graded Invasive / Of concern are used downstream
    graded = alien[alien["invasiveness"].isin(GRADED_INVASIVE)]
    mrgids = sorted(int(m) for m in graded["mrgid"].unique())
    logger.info("Marine Regions: fetching %d areas (of %d with alien records)", len(mrgids), alien["mrgid"].nunique())
    regions = asyncio.run(_fetch_regions(mrgids))
    regions.to_parquet(regions_path, engine="pyarrow", compression="zstd", index=False)

    for path, name in [(alien_path, "wrims.parquet"), (regions_path, "wrims_regions.parquet")]:
        upload_to_gcs(path, config.gcs_bucket, name, project=config.project_id)
        Path(path).unlink(missing_ok=True)

    logger.info("WRiMS ingestion complete")
