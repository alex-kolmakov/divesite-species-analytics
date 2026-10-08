"""Species search API — backed by DuckDB `species_summary`, `divesite_species` and `divesite_summary`."""

from typing import Literal

from fastapi import APIRouter, HTTPException, Query

from ..db import fetch_dicts

router = APIRouter(prefix="/api/species", tags=["species"])

SPECIES_COLUMNS = """
    species, taxon_class, common_name, description, description_is_stub,
    image_url, image_credit, image_license, image_license_url, image_page_url, image_source,
    iucn_category, is_endangered, is_invasive, species_type,
    total_sites, invasive_sites, recent_sites, last_seen
"""


@router.get("/search")
def search_species(
    q: str = Query("", description="Search term (matches species or common_name)"),
    type: Literal["all", "endangered", "invasive", "normal"] = Query("all"),
    limit: int = Query(20, ge=1, le=100),
) -> list[dict]:
    """Search species by scientific or common name. `type` uses the species-level label.

    With no search term this is the list of most widely seen species, without the ones a diver
    doesn't meet underwater: seabirds are recorded near almost every site and would fill the list.
    """
    conditions = ["1=1"]
    params: list[object] = []

    if q:
        conditions.append("(species ILIKE ? OR common_name ILIKE ?)")
        params.extend([f"%{q}%", f"%{q}%"])
    else:
        conditions.append("NOT is_above_water")

    if type != "all":
        conditions.append("species_type = ?")
        params.append(type)

    sql = f"""
        SELECT species, taxon_class, common_name, image_url, image_credit, image_license, image_page_url,
               iucn_category, species_type, is_endangered, is_invasive, total_sites
        FROM species_summary
        WHERE {" AND ".join(conditions)}
        ORDER BY recent_sites DESC, total_sites DESC, species
        LIMIT ?
    """
    params.append(limit)
    return fetch_dicts(sql, params)


@router.get("/{species_name}")
def species_detail(species_name: str) -> dict:
    """One species with its description, global labels and how many sites it is recorded at."""
    rows = fetch_dicts(f"SELECT {SPECIES_COLUMNS} FROM species_summary WHERE species = ?", [species_name])
    if not rows:
        raise HTTPException(status_code=404, detail=f"Species {species_name} not found")
    return rows[0]


@router.get("/{species_name}/sites")
def species_sites(
    species_name: str,
    limit: int = Query(5000, ge=1, le=20000),
) -> list[dict]:
    """Dive sites where the species is recorded, best places first.

    Best = days seen, each weighted by recency (best_place_rank). `invasiveness` says whether the
    species is invasive in that site's region.
    """
    sql = """
        SELECT ds.site_id, site.dive_site, site.latitude, site.longitude, site.country_iso3,
               ds.sighting_count, ds.days_seen, ds.days_seen_recent,
               ds.first_seen, ds.last_seen, ds.months_seen,
               ds.best_place_rank, ds.invasiveness, ds.is_invasive_here
        FROM divesite_species AS ds
        JOIN divesite_summary AS site USING (site_id)
        WHERE ds.species = ?
        ORDER BY ds.best_place_rank, ds.site_id
        LIMIT ?
    """
    return fetch_dicts(sql, [species_name, limit])
