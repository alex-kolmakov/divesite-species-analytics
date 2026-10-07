"""Dive site explorer API — backed by DuckDB `divesite_summary`, `divesite_species` and `species_summary`.

Sites are addressed by `site_id` ('ssi:<id>' / 'padi:<id>'): names are not unique.
"""

from typing import Literal

from fastapi import APIRouter, HTTPException, Query

from ..db import fetch_dicts

router = APIRouter(prefix="/api/divesites", tags=["divesites"])

SITE_COLUMNS = """
    site_id, dive_site, latitude, longitude,
    country_iso3, avg_max_depth, avg_divetime,
    avg_visibility, avg_rating, logged_dives, site_source,
    total_species, recent_species, total_sightings,
    endangered_count, invasive_count, last_seen
"""

# Endangered is the species' global IUCN status; invasive is per site (WRiMS region of the site).
TYPE_FILTERS = {
    "endangered": "s.is_endangered",
    "invasive": "ds.is_invasive_here",
    "normal": "NOT s.is_endangered AND NOT ds.is_invasive_here",
}

SORTS = {
    "records": "ds.frequency_rank, ds.species",
    "recent": "ds.best_place_score DESC, ds.species",
}


@router.get("")
def list_divesites() -> list[dict]:
    """All dive sites with summary stats for initial map render."""
    return fetch_dicts(f"SELECT {SITE_COLUMNS} FROM divesite_summary ORDER BY total_species DESC")


@router.get("/{site_id}")
def divesite_detail(site_id: str) -> dict:
    """One dive site with its summary stats."""
    rows = fetch_dicts(f"SELECT {SITE_COLUMNS} FROM divesite_summary WHERE site_id = ?", [site_id])
    if not rows:
        raise HTTPException(status_code=404, detail=f"Dive site {site_id} not found")
    return rows[0]


@router.get("/{site_id}/species")
def divesite_species(
    site_id: str,
    type: Literal["all", "endangered", "invasive", "normal"] = Query("all"),
    sort: Literal["records", "recent"] = Query(
        "recent", description="records = most records; recent = days seen, weighted by recency"
    ),
    limit: int = Query(50, ge=1, le=500),
) -> list[dict]:
    """Species observed at a dive site, with labels, counts and when they were seen.

    Birds are left out: WoRMS lists seabirds as marine, but they aren't what a diver sees. They
    still appear on their own species pages.
    """
    conditions = ["ds.site_id = ?", "NOT ds.is_bird"]
    params: list[object] = [site_id]
    if type != "all":
        conditions.append(TYPE_FILTERS[type])

    sql = f"""
        SELECT ds.species, s.common_name, s.description, s.description_is_stub, s.image_url,
               s.image_credit, s.image_license, s.image_page_url,
               s.iucn_category, s.is_endangered,
               ds.invasiveness, ds.is_invasive_here,
               ds.sighting_count, ds.days_seen, ds.days_seen_recent,
               ds.first_seen, ds.last_seen, ds.months_seen,
               ds.frequency_rank
        FROM divesite_species AS ds
        JOIN species_summary AS s USING (species)
        WHERE {" AND ".join(conditions)}
        ORDER BY {SORTS[sort]}
        LIMIT ?
    """
    params.append(limit)
    return fetch_dicts(sql, params)
