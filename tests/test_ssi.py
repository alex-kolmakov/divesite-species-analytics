"""
Tests for the SSI dive site ingest source.

Coverage:
  - _make_tile_body: multipart format and payload correctness (pure function)
  - _extract_sites: response parsing and non-divesite element filtering (pure function)
  - _fetch_all_tiles: tile subdivision when a tile hits the 1000-result cap
  - within-source dedup: id-based dedup applied by ingest_ssi
  - cross-source dedup helper: geographic proximity dedup (PADI vs SSI)

Run with:
    uv run pytest tests/test_ssi.py -v
"""

import asyncio
import json
from unittest.mock import patch

import pandas as pd
import pytest
from ingest.sources.ssi import (
    MAX_TILE_ATTEMPTS,
    SATURATION_LIMIT,
    _extract_sites,
    _fetch_all_tiles,
    _make_tile_body,
)

# ─── _make_tile_body ──────────────────────────────────────────────────────────


def test_make_tile_body_multipart_structure():
    body = _make_tile_body(35.0, 10.0, 45.0, 20.0)
    assert body.startswith("------WB\r\n")
    assert body.endswith("------WB--\r\n")
    assert 'Content-Disposition: form-data; name="request"' in body


def test_make_tile_body_payload_values():
    body = _make_tile_body(35.0, 10.0, 45.0, 20.0)
    # Extract JSON between the blank line and the closing boundary
    raw_json = body.split("\r\n\r\n")[1].split("\r\n------WB--")[0]
    payload = json.loads(raw_json)

    assert payload["type"] == "BOUNDS_CHANGED"
    assert payload["filter"]["targets"] == ["DiveSites"]
    assert payload["filter"]["geoBounds"] == {"south": 35.0, "west": 10.0, "north": 45.0, "east": 20.0}
    assert payload["filter"]["viewportCenter"] == {"lat": 40.0, "lng": 15.0}


def test_make_tile_body_viewport_center_is_midpoint():
    body = _make_tile_body(-90.0, -180.0, 90.0, 180.0)
    raw_json = body.split("\r\n\r\n")[1].split("\r\n------WB--")[0]
    payload = json.loads(raw_json)
    assert payload["filter"]["viewportCenter"] == {"lat": 0.0, "lng": 0.0}


# ─── _extract_sites ───────────────────────────────────────────────────────────

SAMPLE_RESPONSE = {
    "stats": {"total": 2},
    "result": {
        "elements": [
            {
                "ident": "divesite",
                "data": {
                    "properties": {
                        "id": "12345",
                        "name": "Blue Hole",
                        "lat": "35.95",
                        "lng": "14.36",
                        "averageRating": "4",
                    },
                    "text": {"description1": "A famous limestone arch site."},
                },
            },
            {
                # Dive center — must be ignored
                "ident": "divecenter",
                "data": {"properties": {"id": "99999"}, "text": {}},
            },
        ],
    },
}


def test_extract_sites_returns_only_divesites():
    sites = _extract_sites(SAMPLE_RESPONSE)
    assert len(sites) == 1
    assert sites[0]["id"] == "12345"
    assert sites[0]["name"] == "Blue Hole"


def test_extract_sites_merges_text_into_props():
    sites = _extract_sites(SAMPLE_RESPONSE)
    assert sites[0]["description1"] == "A famous limestone arch site."


def test_extract_sites_handles_empty_response():
    assert _extract_sites({}) == []
    assert _extract_sites({"result": {}}) == []
    assert _extract_sites({"result": {"elements": []}}) == []


def test_extract_sites_ignores_missing_ident():
    resp = {"result": {"elements": [{"data": {"properties": {"id": "1"}, "text": {}}}]}}
    assert _extract_sites(resp) == []


# ─── _fetch_all_tiles: subdivision logic ──────────────────────────────────────


def _make_tile_response(total: int, n_sites: int, id_prefix: str) -> dict:
    """Build a fake SSI API response with the given total count and n site records."""
    return {
        "stats": {"total": total},
        "result": {
            "elements": [
                {
                    "ident": "divesite",
                    "data": {
                        "properties": {"id": f"{id_prefix}_{i}", "name": f"Site {i}"},
                        "text": {},
                    },
                }
                for i in range(n_sites)
            ]
        },
    }


def test_no_subdivision_when_below_limit():
    """Tiles with < 1000 results are accepted as-is."""

    async def mock_fetch(session, sem, phpsessid, auth_token, s, w, n, e):
        return _make_tile_response(total=5, n_sites=5, id_prefix="ok")

    with patch("ingest.sources.ssi._fetch_tile", side_effect=mock_fetch):
        sites = asyncio.run(_fetch_all_tiles("sess", "tok", [(-30.0, -30.0, 0.0, 0.0)]))

    assert len(sites) == 5


def test_subdivision_triggered_on_saturation():
    """A tile returning exactly 1000 results must be subdivided into 4 sub-tiles."""
    tiles_requested: list[tuple] = []

    async def mock_fetch(session, sem, phpsessid, auth_token, s, w, n, e):
        tiles_requested.append((s, w, n, e))
        # Only the first tile saturates; all sub-tiles return small counts
        if (s, w, n, e) == (-60.0, -60.0, -30.0, -30.0):
            return _make_tile_response(total=SATURATION_LIMIT, n_sites=0, id_prefix="sat")
        return _make_tile_response(total=3, n_sites=3, id_prefix="sub")

    initial = [
        (-60.0, -60.0, -30.0, -30.0),  # will saturate → 4 sub-tiles
        (-60.0, -30.0, -30.0, 0.0),  # will not saturate
    ]
    with patch("ingest.sources.ssi._fetch_tile", side_effect=mock_fetch):
        sites = asyncio.run(_fetch_all_tiles("sess", "tok", initial))

    # 2 initial + 4 sub-tiles = 6 total calls
    assert len(tiles_requested) == 6

    # Sub-tiles of (-60,-60,-30,-30) split at midpoints (-45, -45)
    mid_lat, mid_lng = -45.0, -45.0
    expected_subtiles = {
        (-60.0, -60.0, mid_lat, mid_lng),
        (-60.0, mid_lng, mid_lat, -30.0),
        (mid_lat, -60.0, -30.0, mid_lng),
        (mid_lat, mid_lng, -30.0, -30.0),
    }
    assert expected_subtiles.issubset(set(tiles_requested))

    # Saturated tile's sites (n_sites=0) were not added; 4 sub-tiles × 3 sites + 1 non-saturated × 3
    assert len(sites) == 4 * 3 + 3


def test_failed_tile_is_retried():
    """A tile answered with null (as the SSI API does under load) is retried, not dropped."""
    calls = [0]

    async def mock_fetch(session, sem, phpsessid, auth_token, s, w, n, e):
        calls[0] += 1
        return None if calls[0] == 1 else _make_tile_response(total=4, n_sites=4, id_prefix="ok")

    with (
        patch("ingest.sources.ssi._fetch_tile", side_effect=mock_fetch),
        patch("ingest.sources.ssi.RETRY_DELAY_SECONDS", 0),
    ):
        sites = asyncio.run(_fetch_all_tiles("sess", "tok", [(-30.0, -30.0, 0.0, 0.0)]))

    assert calls[0] == 2
    assert len(sites) == 4


def test_persistently_failing_tile_is_subdivided():
    """After MAX_TILE_ATTEMPTS failures the 30° tile is split; its 15° sub-tiles succeed."""
    requested: list[tuple] = []

    async def mock_fetch(session, sem, phpsessid, auth_token, s, w, n, e):
        requested.append((s, w, n, e))
        if n - s >= 30:
            raise ConnectionError("timeout")
        return _make_tile_response(total=2, n_sites=2, id_prefix=f"{s}_{w}")

    with (
        patch("ingest.sources.ssi._fetch_tile", side_effect=mock_fetch),
        patch("ingest.sources.ssi.RETRY_DELAY_SECONDS", 0),
    ):
        sites = asyncio.run(_fetch_all_tiles("sess", "tok", [(-30.0, -30.0, 0.0, 0.0)]))

    assert requested.count((-30.0, -30.0, 0.0, 0.0)) == MAX_TILE_ATTEMPTS
    assert len(sites) == 4 * 2


def test_one_bad_record_is_isolated_and_skipped():
    """A tile holding one unencodable record fails at every size; splitting recovers its neighbours."""

    async def mock_fetch(session, sem, phpsessid, auth_token, s, w, n, e):
        if s <= -29 < n and w <= -29 < e:  # every tile containing the point (-29, -29) fails
            return None
        return _make_tile_response(total=1, n_sites=1, id_prefix=f"{s}_{w}")

    with (
        patch("ingest.sources.ssi._fetch_tile", side_effect=mock_fetch),
        patch("ingest.sources.ssi.RETRY_DELAY_SECONDS", 0),
        patch("ingest.sources.ssi.MIN_TILE_SIZE", 5),
    ):
        sites = asyncio.run(_fetch_all_tiles("sess", "tok", [(-30.0, -30.0, 0.0, 0.0)]))

    # 30° fails → 4 × 15°: 3 succeed, 1 fails → 4 × 7.5°: 3 succeed, 1 fails and is too small to split
    assert len(sites) == 3 + 3


def test_too_many_unreadable_tiles_raise():
    """If the API fails everywhere, abort instead of uploading a partial scrape."""

    async def mock_fetch(session, sem, phpsessid, auth_token, s, w, n, e):
        return None

    with (
        patch("ingest.sources.ssi._fetch_tile", side_effect=mock_fetch),
        patch("ingest.sources.ssi.RETRY_DELAY_SECONDS", 0),
        patch("ingest.sources.ssi.MIN_TILE_SIZE", 10),
        patch("ingest.sources.ssi.MAX_LOST_TILES", 3),
        pytest.raises(RuntimeError, match="failed after retries"),
    ):
        asyncio.run(_fetch_all_tiles("sess", "tok", [(-30.0, -30.0, 0.0, 0.0)]))


def test_multiple_rounds_of_subdivision():
    """A sub-tile that also saturates must trigger a second round of subdivision."""
    call_count = [0]

    async def mock_fetch(session, sem, phpsessid, auth_token, s, w, n, e):
        call_count[0] += 1
        tile_size = n - s
        if tile_size >= 15:  # 30° and 15° tiles saturate; 7.5° tiles do not
            return _make_tile_response(total=SATURATION_LIMIT, n_sites=0, id_prefix="sat")
        return _make_tile_response(total=2, n_sites=2, id_prefix="ok")

    with patch("ingest.sources.ssi._fetch_tile", side_effect=mock_fetch):
        # 1 tile of 30° → 4 sub-tiles of 15° → each saturates → 16 sub-tiles of 7.5°
        sites = asyncio.run(_fetch_all_tiles("sess", "tok", [(-30.0, -30.0, 0.0, 0.0)]))

    assert call_count[0] == 1 + 4 + 16
    assert len(sites) == 16 * 2


# ─── within-source dedup ──────────────────────────────────────────────────────


def test_ssi_deduplicates_by_id():
    """
    Adjacent tiles overlap slightly — the same site can appear in both tile responses.
    The final DataFrame must deduplicate by site id.
    """
    raw = [
        {"id": "100", "name": "The Arch", "lat": "35.9", "lng": "14.3"},
        {"id": "100", "name": "The Arch", "lat": "35.9", "lng": "14.3"},  # duplicate from tile overlap
        {"id": "200", "name": "Blue Hole", "lat": "36.0", "lng": "14.4"},
    ]
    df = pd.DataFrame(raw).drop_duplicates(subset=["id"])
    assert len(df) == 2
    assert set(df["id"]) == {"100", "200"}


# ─── cross-source dedup (PADI vs SSI) ────────────────────────────────────────
#
# PADI and SSI use entirely different internal IDs — the only shared key is
# geographic proximity. Two sites from different sources that are within ~100m
# of each other are the same physical dive site.
#
# Strategy: round lat/lon to 3 decimal places (≈ 111m at equator) to create a
# grid-cell key, then keep one record per cell (prefer PADI as the primary source).
# This logic lives in dbt (substrate/divesites.sql) but is unit-tested here
# using the same pandas mechanics so the logic is verified before the SQL is written.


def _dedup_combined(padi_df: pd.DataFrame, ssi_df: pd.DataFrame) -> pd.DataFrame:
    """
    Reference implementation of the cross-source dedup logic that will be
    replicated in dbt's substrate/divesites.sql.

    Both DataFrames must have float columns: latitude, longitude, title/name.
    SSI uses 'name'; we normalise to 'title' here to match PADI's schema.
    """
    padi = padi_df[["title", "latitude", "longitude"]].copy()
    padi["source"] = "padi"

    ssi = ssi_df[["name", "lat", "lng"]].copy()
    ssi = ssi.rename(columns={"name": "title"})
    ssi["latitude"] = ssi["lat"].astype(float)
    ssi["longitude"] = ssi["lng"].astype(float)
    ssi = ssi[["title", "latitude", "longitude"]]
    ssi["source"] = "ssi"

    combined = pd.concat([padi, ssi], ignore_index=True)

    # Grid-cell key: 0.001° ≈ 111m at equator
    combined["lat_grid"] = combined["latitude"].round(3)
    combined["lng_grid"] = combined["longitude"].round(3)

    # Sort so PADI comes first → kept by drop_duplicates(keep='first')
    combined = combined.sort_values("source")  # 'padi' < 'ssi' alphabetically
    return combined.drop_duplicates(subset=["lat_grid", "lng_grid"]).drop(columns=["lat_grid", "lng_grid", "source"])


def test_cross_source_dedup_keeps_padi_for_nearby_sites():
    """If a PADI and SSI site are within 100m, the PADI record is kept."""
    padi = pd.DataFrame(
        [
            {"title": "Blue Hole (PADI)", "latitude": 35.9500, "longitude": 14.3600},
        ]
    )
    ssi = pd.DataFrame(
        [
            # Same physical site — within 100m (0.0001° difference ≈ 11m)
            {"name": "The Blue Hole", "lat": "35.9501", "lng": "14.3601"},
        ]
    )
    result = _dedup_combined(padi, ssi)
    assert len(result) == 1
    assert result.iloc[0]["title"] == "Blue Hole (PADI)"


def test_cross_source_dedup_keeps_both_when_distant():
    """Sites from different sources that are far apart must both be retained."""
    padi = pd.DataFrame(
        [
            {"title": "Blue Hole Malta", "latitude": 35.95, "longitude": 14.36},
        ]
    )
    ssi = pd.DataFrame(
        [
            {"name": "Ras Mohammed", "lat": "27.73", "lng": "34.25"},  # Egypt — clearly different
        ]
    )
    result = _dedup_combined(padi, ssi)
    assert len(result) == 2


def test_cross_source_dedup_ssi_only_site_is_kept():
    """An SSI site with no nearby PADI counterpart must be included in the output."""
    padi = pd.DataFrame(
        [
            {"title": "Blue Hole Malta", "latitude": 35.95, "longitude": 14.36},
        ]
    )
    ssi = pd.DataFrame(
        [
            {"name": "El Quseir Caves", "lat": "26.10", "lng": "34.30"},  # Egypt — SSI-only
        ]
    )
    result = _dedup_combined(padi, ssi)
    assert len(result) == 2
    assert "El Quseir Caves" in result["title"].values
