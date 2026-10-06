"""
Tests for the WRiMS parsers (alien distributions, Marine Regions boundaries).

Run with:
    uv run pytest tests/test_wrims.py -v
"""

import json

import shapely
from ingest.sources.wrims import fallback_geometry, parse_distributions, parse_geometry

LIONFISH = [
    {
        "locality": "Cayman Islands part of the Caribbean Sea",
        "locationID": "http://marineregions.org/mrgid/25283",
        "establishmentMeans": "Alien",
        "invasiveness": "Invasive",
        "recordStatus": "valid",
        "qualityStatus": "checked",
    },
    {"locality": "Red Sea", "locationID": "http://marineregions.org/mrgid/4264", "establishmentMeans": None},
    {"locality": "Somewhere", "locationID": None, "establishmentMeans": "Alien", "invasiveness": "Invasive"},
]


def test_only_alien_records_with_a_region_are_kept():
    rows = parse_distributions(159559, "Pterois volitans", LIONFISH)
    assert len(rows) == 1
    assert rows[0]["mrgid"] == 25283
    assert rows[0]["invasiveness"] == "Invasive"
    assert rows[0]["species"] == "Pterois volitans"


def _jsonld(*wkts: str) -> str:
    return json.dumps(
        {
            "@id": "http://marineregions.org/mrgid/1",
            "mr:hasGeometry": [{"gsp:asWKT": f"<http://www.opengis.net/def/crs/OGC/1.3/CRS84> {w}"} for w in wkts],
        }
    )


def test_geometry_strips_crs_and_unions_sources():
    wkt = parse_geometry(_jsonld("POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))", "POLYGON((1 0, 2 0, 2 1, 1 1, 1 0))"))
    assert wkt is not None
    shape = shapely.from_wkt(wkt)
    assert abs(shape.area - 2.0) < 1e-9
    assert shape.contains(shapely.Point(1.5, 0.5))


def test_geometry_without_polygons_is_none():
    assert parse_geometry(_jsonld("POINT(1 1)")) is None
    assert parse_geometry(json.dumps({"mr:hasGeometry": []})) is None


def test_empty_and_broken_geometry_sources_are_skipped():
    body = json.dumps(
        {
            "mr:hasGeometry": [
                {"gsp:asWKT": "<http://www.opengis.net/def/crs/OGC/1.3/CRS84> "},
                {"gsp:asWKT": "<http://www.opengis.net/def/crs/OGC/1.3/CRS84> MULTIPOLYGON (((0 0, 1 0"},
                {"gsp:asWKT": "<http://www.opengis.net/def/crs/OGC/1.3/CRS84> POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))"},
            ]
        }
    )
    wkt = parse_geometry(body)
    assert wkt is not None
    assert abs(shapely.from_wkt(wkt).area - 1.0) < 1e-9


def test_fallback_uses_sorted_bbox():
    kerguelen = {
        "latitude": -49.33,
        "longitude": 69.25,
        "minLatitude": -50.34,
        "maxLatitude": -48.07,
        "minLongitude": 71.85,
        "maxLongitude": 66.77,
    }
    shape = shapely.from_wkt(fallback_geometry(kerguelen))
    assert shape.bounds == (66.77, -50.34, 71.85, -48.07)


def test_fallback_without_bbox_buffers_the_point():
    shape = shapely.from_wkt(fallback_geometry({"latitude": -33.9, "longitude": 18.4}))
    assert shape.contains(shapely.Point(18.5, -33.9))
    assert fallback_geometry({}) is None
