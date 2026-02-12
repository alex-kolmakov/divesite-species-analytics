"""Dive site explorer API — backed by DuckDB `divesite_summary` and `divesite_species_detail`."""

from fastapi import APIRouter, Query

from ..db import get_conn

router = APIRouter(prefix="/api/divesites", tags=["divesites"])


@router.get("")
def list_divesites() -> list[dict]:
    """All dive sites with summary stats for initial map render."""
    conn = get_conn()

    sql = """
        SELECT dive_site, latitude, longitude,
               total_species, total_sightings,
               endangered_count, invasive_count
        FROM divesite_summary
        ORDER BY total_species DESC
    """
    result = conn.execute(sql).fetchall()
    columns = [
        "dive_site",
        "latitude",
        "longitude",
        "total_species",
        "total_sightings",
        "endangered_count",
        "invasive_count",
    ]
    return [dict(zip(columns, row, strict=True)) for row in result]


@router.get("/{dive_site}/species")
def divesite_species(
    dive_site: str,
    type: str = Query("all", description="Filter: all | endangered | invasive | normal"),
    limit: int = Query(50, ge=1, le=200),
) -> list[dict]:
    """Species observed at a dive site, with metadata and sighting counts."""
    conn = get_conn()

    conditions = ["dive_site = ?"]
    params: list[object] = [dive_site]

    if type != "all":
        conditions.append("species_type = ?")
        params.append(type)

    where = " AND ".join(conditions)
    sql = f"""
        SELECT species, common_name, description, image_url,
               species_type, is_endangered, is_invasive,
               sighting_count, frequency_rank
        FROM divesite_species_detail
        WHERE {where}
        ORDER BY frequency_rank
        LIMIT ?
    """
    params.append(limit)

    result = conn.execute(sql, params).fetchall()
    columns = [
        "species",
        "common_name",
        "description",
        "image_url",
        "species_type",
        "is_endangered",
        "is_invasive",
        "sighting_count",
        "frequency_rank",
    ]
    return [dict(zip(columns, row, strict=True)) for row in result]
