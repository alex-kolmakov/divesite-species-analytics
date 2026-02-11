"""Species search API — backed by DuckDB `species_divesite_summary` table."""

from fastapi import APIRouter, Query

from ..db import get_conn

router = APIRouter(prefix="/api/species", tags=["species"])


@router.get("/search")
def search_species(
    q: str = Query("", description="Search term (matches species or common_name)"),
    type: str = Query("all", description="Filter: all | endangered | invasive | normal"),
    limit: int = Query(20, ge=1, le=100),
) -> list[dict]:
    """Full-text search across species and common names."""
    conn = get_conn()

    conditions = ["1=1"]
    params: list[object] = []

    if q:
        conditions.append("(species ILIKE ? OR common_name ILIKE ?)")
        params.extend([f"%{q}%", f"%{q}%"])

    if type != "all":
        conditions.append("species_type = ?")
        params.append(type)

    where = " AND ".join(conditions)
    sql = f"""
        SELECT DISTINCT
            species,
            common_name,
            image_url,
            species_type,
            is_endangered,
            is_invasive
        FROM species_divesite_summary
        WHERE {where}
        ORDER BY species
        LIMIT ?
    """
    params.append(limit)

    result = conn.execute(sql, params).fetchall()
    columns = ["species", "common_name", "image_url", "species_type", "is_endangered", "is_invasive"]
    return [dict(zip(columns, row, strict=True)) for row in result]


@router.get("/{species_name}")
def species_detail(species_name: str) -> dict | None:
    """Get detailed info about a species including description."""
    conn = get_conn()

    sql = """
        SELECT species, common_name, description, image_url,
               species_type, is_endangered, is_invasive,
               SUM(sighting_count) as total_sightings,
               COUNT(DISTINCT dive_site) as total_sites
        FROM divesite_species_detail
        WHERE species = ?
        GROUP BY species, common_name, description, image_url,
                 species_type, is_endangered, is_invasive
    """
    result = conn.execute(sql, [species_name]).fetchone()
    if not result:
        return None
    columns = [
        "species", "common_name", "description", "image_url",
        "species_type", "is_endangered", "is_invasive",
        "total_sightings", "total_sites",
    ]
    return dict(zip(columns, result, strict=True))


@router.get("/{species_name}/sites")
def species_sites(species_name: str) -> list[dict]:
    """Dive sites where a species has been observed, ordered by frequency."""
    conn = get_conn()

    sql = """
        SELECT dive_site, dive_site_latitude, dive_site_longitude,
               sighting_count, frequency_rank
        FROM species_divesite_summary
        WHERE species = ?
        ORDER BY frequency_rank
    """
    result = conn.execute(sql, [species_name]).fetchall()
    columns = ["dive_site", "latitude", "longitude", "sighting_count", "frequency_rank"]
    return [dict(zip(columns, row, strict=True)) for row in result]
