"""
Compare PADI vs SSI dive site datasets.
Fetches both sources without GCS, saves locally, prints analysis.

Run from repo root:
    uv run python scripts/compare_divesite_sources.py
"""

import asyncio
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

PADI_GUIDE_URL = "https://travel.padi.com/api/v2/travel/dive-guide/world/all/dive-sites"
PADI_MAP_URL = "https://travel.padi.com/api/v2/travel/dsl/dive-sites/map/"
OUT_DIR = Path("/tmp/marine-data")
OUT_DIR.mkdir(parents=True, exist_ok=True)


# ── Fetch ──────────────────────────────────────────────────────────────────────


def fetch_padi() -> pd.DataFrame:
    from ingest.sources.divesites import _get_divesites

    print("Fetching PADI …")
    df = asyncio.run(_get_divesites(PADI_GUIDE_URL, PADI_MAP_URL))
    df.to_parquet(OUT_DIR / "padi.parquet", index=False)
    print(f"  PADI: {len(df):,} sites saved to {OUT_DIR}/padi.parquet")
    return df


def fetch_ssi() -> pd.DataFrame:
    from ingest.sources.ssi import _get_ssi_divesites

    print("Fetching SSI …")
    df = asyncio.run(_get_ssi_divesites())
    df.to_parquet(OUT_DIR / "ssi.parquet", index=False)
    print(f"  SSI:  {len(df):,} sites saved to {OUT_DIR}/ssi.parquet")
    return df


def load_cached(name: str, fetcher) -> pd.DataFrame:
    path = OUT_DIR / f"{name}.parquet"
    if path.exists():
        df = pd.read_parquet(path)
        print(f"  {name.upper()}: loaded {len(df):,} sites from cache ({path})")
        return df
    return fetcher()


# ── Analysis ───────────────────────────────────────────────────────────────────


def section(title: str) -> None:
    print(f"\n{'═' * 60}")
    print(f"  {title}")
    print("═" * 60)


def field_coverage(df: pd.DataFrame, fields: list[str]) -> pd.DataFrame:
    rows = []
    for f in fields:
        if f not in df.columns:
            rows.append({"field": f, "present": False, "filled_%": 0.0, "sample": "—"})
            continue
        filled = (
            df[f].notna()
            & (df[f].astype(str).str.strip() != "")
            & (df[f].astype(str) != "[]")
            & (df[f].astype(str) != "0")
        )
        pct = filled.mean() * 100
        sample = df.loc[filled, f].iloc[0] if filled.any() else "—"
        if isinstance(sample, list):
            sample = str(sample)
        sample_str = str(sample)[:60]
        rows.append({"field": f, "present": True, "filled_%": round(pct, 1), "sample": sample_str})
    return pd.DataFrame(rows)


def lat_band(lat: float) -> str:
    if lat > 60:
        return "Arctic (>60N)"
    if lat > 30:
        return "Temperate N (30-60N)"
    if lat > 0:
        return "Tropical N (0-30N)"
    if lat > -30:
        return "Tropical S (0-30S)"
    if lat > -60:
        return "Temperate S (30-60S)"
    return "Antarctic (<60S)"


def analyze(padi: pd.DataFrame, ssi: pd.DataFrame) -> None:

    # ── 1. Volume ────────────────────────────────────────────────────────────
    section("1. VOLUME")
    print(f"  PADI sites : {len(padi):>6,}")
    print(f"  SSI sites  : {len(ssi):>6,}")
    print(f"  SSI / PADI : {len(ssi) / max(len(padi), 1):.1f}×")

    # ── 2. Geographic distribution ───────────────────────────────────────────
    section("2. GEOGRAPHIC DISTRIBUTION (latitude bands)")
    padi_lat = pd.to_numeric(padi.get("latitude", padi.get("lat")), errors="coerce").dropna()
    ssi_lat = pd.to_numeric(ssi["lat"], errors="coerce").dropna()

    bands = [
        "Arctic (>60N)",
        "Temperate N (30-60N)",
        "Tropical N (0-30N)",
        "Tropical S (0-30S)",
        "Temperate S (30-60S)",
        "Antarctic (<60S)",
    ]
    padi_bands = padi_lat.map(lat_band).value_counts().reindex(bands, fill_value=0)
    ssi_bands = ssi_lat.map(lat_band).value_counts().reindex(bands, fill_value=0)

    print(f"  {'Band':<28} {'PADI':>6}  {'SSI':>6}  {'SSI/PADI':>8}")
    print(f"  {'-' * 28} {'-' * 6}  {'-' * 6}  {'-' * 8}")
    for band in bands:
        p, s = padi_bands[band], ssi_bands[band]
        ratio = f"{s / p:.1f}×" if p > 0 else ("∞" if s > 0 else "—")
        print(f"  {band:<28} {p:>6,}  {s:>6,}  {ratio:>8}")

    # ── 3. Country coverage ──────────────────────────────────────────────────
    section("3. COUNTRY COVERAGE")
    padi_countries = set()
    if "country" in padi.columns:
        padi_countries = set(padi["country"].dropna().unique())
    elif "country_x" in padi.columns:
        padi_countries = set(padi["country_x"].dropna().unique())

    ssi_countries = set()
    if "country_iso3" in ssi.columns:
        ssi_countries = set(ssi["country_iso3"].dropna().unique())

    print(f"  PADI unique countries/codes : {len(padi_countries)}")
    print(f"  SSI unique ISO3 codes       : {len(ssi_countries)}")
    if ssi_countries and padi_countries:
        overlap = padi_countries & ssi_countries
        print(f"  Overlap                     : {len(overlap)}")
        ssi_only = ssi_countries - padi_countries
        if ssi_only:
            print(f"  SSI-only countries (sample) : {sorted(ssi_only)[:15]}")

    # ── 4. Field richness ────────────────────────────────────────────────────
    section("4. FIELD RICHNESS — PADI")
    padi_fields = [
        "title",
        "latitude",
        "longitude",
        "country",
        "description",
        "rating",
        "difficulty",
        "max_depth",
        "visibility",
        "water_temp_min",
        "water_temp_max",
        "entry_type",
        "slug",
    ]
    padi_cov = field_coverage(padi, padi_fields)
    print(padi_cov.to_string(index=False))

    section("4. FIELD RICHNESS — SSI")
    ssi_fields = [
        "id",
        "name",
        "lat",
        "lng",
        "country_iso3",
        "averageRating",
        "loggedDives",
        "loggedUsers",
        "averageMaxDepth",
        "averageDivetime",
        "averageVis",
        "level",
        "wildlife",
        "description1",
        "description2",
        "URL",
        "dcAffiliated",
    ]
    ssi_cov = field_coverage(ssi, ssi_fields)
    print(ssi_cov.to_string(index=False))

    # ── 5. Data quality signals ──────────────────────────────────────────────
    section("5. COMMUNITY / QUALITY SIGNALS")

    # SSI has logged dives — a proxy for site popularity validation
    if "loggedDives" in ssi.columns:
        logged = pd.to_numeric(ssi["loggedDives"], errors="coerce").dropna()
        n_logged, pct_logged = (logged >= 1).sum(), (logged >= 1).mean() * 100
        print(f"  SSI — sites with ≥1 logged dive  : {n_logged:,} / {len(ssi):,} ({pct_logged:.0f}%)")
        print(f"  SSI — median logged dives/site   : {logged.median():.0f}")
        print("  SSI — top-10 most-logged sites   :")
        top = ssi.copy()
        top["_ld"] = pd.to_numeric(top["loggedDives"], errors="coerce")
        top10 = top.nlargest(10, "_ld")[["name", "country_iso3", "_ld"]].copy()
        top10.columns = ["name", "country", "logged_dives"]
        for _, row in top10.iterrows():
            print(f"    {row['name'][:40]:<40} {row['country']}  {int(row['logged_dives']):,}")

    if "averageRating" in ssi.columns:
        rating = pd.to_numeric(ssi["averageRating"], errors="coerce").dropna()
        print(
            f"  SSI — sites with a rating        : {len(rating):,} / {len(ssi):,} ({len(rating) / len(ssi) * 100:.0f}%)"
        )
        print(f"  SSI — mean rating                : {rating.mean():.2f}/5")

    if "level" in ssi.columns:
        has_level = ssi["level"].apply(
            lambda x: bool(x) if isinstance(x, list) else (isinstance(x, str) and x not in ("", "[]", "null"))
        )
        print(
            f"  SSI — sites with difficulty level: {has_level.sum():,} / {len(ssi):,} ({has_level.mean() * 100:.0f}%)"
        )

    if "wildlife" in ssi.columns:
        has_wildlife = ssi["wildlife"].apply(lambda x: bool(x) if isinstance(x, list) else False)
        pct_wildlife = has_wildlife.mean() * 100
        print(f"  SSI — sites with wildlife tags   : {has_wildlife.sum():,} / {len(ssi):,} ({pct_wildlife:.0f}%)")

    # ── 6. Overlap estimate (geographic) ─────────────────────────────────────
    section("6. GEOGRAPHIC OVERLAP ESTIMATE (0.01° grid ≈ 1km)")
    padi_coord = padi.copy()
    padi_lat_col = "latitude" if "latitude" in padi.columns else "lat"
    padi_lon_col = "longitude" if "longitude" in padi.columns else "lng"
    padi_coord["_glat"] = pd.to_numeric(padi_coord[padi_lat_col], errors="coerce").round(2)
    padi_coord["_glng"] = pd.to_numeric(padi_coord[padi_lon_col], errors="coerce").round(2)
    padi_cells = set(zip(padi_coord["_glat"], padi_coord["_glng"], strict=True))

    ssi_coord = ssi.copy()
    ssi_coord["_glat"] = pd.to_numeric(ssi_coord["lat"], errors="coerce").round(2)
    ssi_coord["_glng"] = pd.to_numeric(ssi_coord["lng"], errors="coerce").round(2)
    ssi_cells = set(zip(ssi_coord["_glat"], ssi_coord["_glng"], strict=True))

    overlap_cells = padi_cells & ssi_cells
    padi_only = padi_cells - ssi_cells
    ssi_only = ssi_cells - padi_cells

    print(f"  PADI unique 1km grid cells  : {len(padi_cells):,}")
    print(f"  SSI unique 1km grid cells   : {len(ssi_cells):,}")
    pct_shared = len(overlap_cells) / max(len(padi_cells), 1) * 100
    print(f"  Shared cells (≈ same sites) : {len(overlap_cells):,}  ({pct_shared:.0f}% of PADI)")
    print(f"  SSI-only cells              : {len(ssi_only):,}  (net new sites vs PADI)")
    print(f"  PADI-only cells             : {len(padi_only):,}  (sites SSI doesn't have)")

    # ── 7. Verdict ───────────────────────────────────────────────────────────
    section("7. VERDICT")
    ssi_total = len(ssi)
    padi_total = len(padi)
    ssi_has_community = "loggedDives" in ssi.columns
    ssi_has_depth = (
        "averageMaxDepth" in ssi.columns and pd.to_numeric(ssi["averageMaxDepth"], errors="coerce").notna().mean() > 0.3
    )
    ssi_has_desc = "description1" in ssi.columns and ssi["description1"].notna().mean() > 0.1
    ssi_coverage_ratio = ssi_total / max(padi_total, 1)

    points = []
    if ssi_coverage_ratio > 1.5:
        points.append(f"SSI has {ssi_coverage_ratio:.1f}× more sites")
    if ssi_has_community:
        logged = pd.to_numeric(ssi["loggedDives"], errors="coerce")
        if (logged >= 1).mean() > 0.3:
            points.append("SSI has real community validation (logged dives/users)")
    if ssi_has_depth:
        points.append("SSI carries dive-specific metrics (depth, divetime, visibility)")
    if ssi_has_desc:
        points.append("SSI has site descriptions (description1/description2)")
    if len(ssi_only) > len(padi_only):
        points.append(f"SSI adds {len(ssi_only):,} genuinely new locations vs PADI")

    if len(points) >= 3:
        print("  → SSI should be the PRIMARY source. Reasons:")
        for p in points:
            print(f"    • {p}")
        print("\n  Recommended dbt change: rename divesites_table → ssi_divesites_table as primary,")
        print("  keep padi as supplementary for sites SSI doesn't cover.")
    else:
        print("  → PADI remains competitive. Use UNION ALL, no clear primary.")

    print()


if __name__ == "__main__":
    import logging

    logging.basicConfig(level=logging.WARNING)  # suppress fetch noise during analysis

    print("Loading / fetching datasets …\n")
    padi = load_cached("padi", fetch_padi)
    ssi = load_cached("ssi", fetch_ssi)

    print(f"\nPADI columns : {sorted(padi.columns.tolist())}")
    print(f"SSI  columns : {sorted(ssi.columns.tolist())}")

    analyze(padi, ssi)
