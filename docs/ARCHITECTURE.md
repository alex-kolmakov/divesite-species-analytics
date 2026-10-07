# Architecture

Detailed technical documentation for the Marine Species Analytics platform.

## Data Modeling

The dbt project uses a **medallion architecture** with marine biology-themed layers:

```
 Substrate (raw)          Skeleton (cleaned)           Coral (analytics)
┌──────────────┐      ┌──────────────────┐      ┌─────────────────────────┐
│ divesites    │      │ occurrences      │      │ near_dive_site_         │
│ gbif_occur.  │─────▶│ clustered_occur. │─────▶│   occurrences           │
│ obis_occur.  │      │ species          │      │ monthly_species_occur.  │
└──────────────┘      └──────────────────┘      │ divesite_species_freq.  │
                                                │ divesite_species        │
                                                │ species_summary         │
                                                │ divesite_summary        │
                                                └─────────────────────────┘
```

### Substrate (Raw)

External GCS parquet files are BigQuery external tables. The two occurrence sources are staged once into native tables (WoRMS species only, no other filter) so that nothing downstream re-scans GBIF or the OBIS parquet.

| Model | Source | Description |
|-------|--------|-------------|
| `divesites` | SSI + PADI | ~13,300 dive sites keyed by `site_id` (SSI ~10,600 primary + PADI ~2,700 not already in SSI: same name within 500 m, or within 25 m, counts as a duplicate) |
| `gbif_occurrences` | GBIF BigQuery public dataset | Table. ~559M records of WoRMS species with IDs and QC fields. The only model that scans GBIF (~306 GiB: 3.7B rows, no partitioning). Sampled in dev |
| `obis_occurrences` | OBIS S3 bucket | Table. ~182M records of WoRMS species with IDs, validated dates and QC fields (~29 GiB read of the parquet) |

### Skeleton (Cleaned)

Validated, deduplicated, and unified datasets ready for analytics.

| Model | Description |
|-------|-------------|
| `occurrences` | Presences from GBIF + OBIS (~493M), keyed by `occurrence_key`. Drops absences, OBIS QC rejects, fossil/living specimens, invalid or pre-`MIN_YEAR` dates, 0/0 coordinates, records less precise than `PROXIMITY_METERS`, and GBIF copies of OBIS records. Partitioned by `event_date` (month), clustered by `geography`. `analyses/occurrence_filter_counts.sql` counts each rule. |
| `species` | Deduplicated species reference table with `iucn_category`, `is_endangered` (IUCN VU/EN/CR) and `is_invasive` (WRiMS: invasive somewhere) flags. |

### Coral (Analytics)

Denormalized tables optimized for the application's two primary queries.

| Model | Description |
|-------|-------------|
| `near_dive_site_occurrences` | Spatial join: one row per (`occurrence_key`, `site_id`) within a configurable radius (`PROXIMITY_METERS`), with the distance. A sighting counts for every site in range, so occurrence totals come from `occurrences`, not from this table. The only coral model that reads `occurrences`. |
| `monthly_species_occurrences` | Sightings per site, species and calendar month (`month_start`, `year`, `month` 1–12). Powers temporal trend charts. |
| `divesite_species_frequency` | Per (`site_id`, species): records, distinct days seen (all time and last `RECENT_YEARS`), first/last seen, months seen, and `best_place_score` (days seen, each weighted by recency with a `BEST_PLACE_HALF_LIFE_YEARS` half-life). Ranks species per site and sites per species. |
| `divesite_species` | App table: `divesite_species_frequency` plus the per-site invasive label. Narrow on purpose (no text). Answers "what lives at site Y" and "best places to see species X". |
| `species_summary` | App table: one row per species found at a site, with name, description, image, global IUCN category and how many sites it is at. LEFT JOINs `species_enrichment`. |
| `divesite_invasive_species` | Species invasive at each dive site: WRiMS lists it as Invasive / Of concern in a sea area within 5 km. Invasiveness is per place. |
| `divesite_summary` | One row per dive site with species counts and coordinates (~13,300 rows). Loaded entirely on app startup. |

### Core Column Schema

Columns present across the occurrence-based models:

| Column | Type | Description |
|--------|------|-------------|
| `species` | STRING | Scientific species name (WoRMS-validated) |
| `individual_count` | INTEGER | Individuals per sighting; null when not recorded or not a whole number |
| `event_date` | TIMESTAMP | Observation timestamp (partition key) |
| `geography` | GEOGRAPHY | BigQuery POINT geometry |
| `source` | STRING | Origin dataset (`OBIS` or `GBIF`) |
| `is_invasive` | BOOLEAN | WRiMS lists it as Invasive somewhere; per site see `divesite_invasive_species` |
| `is_endangered` | BOOLEAN | Flagged by IUCN Red List |
| `species_type` | STRING | Derived label: `endangered` > `invasive` > `normal` |

### Enrichment Data

The `species_enrichment` table is a **dbt source** (not a model) — it is managed entirely by the enrichment pipeline and survives `dbt run` rebuilds.

| Column | Type | Source |
|--------|------|--------|
| `species` | STRING | Primary key, matches `species.species` |
| `common_name` | STRING | GBIF vernacular names REST API |
| `description` | STRING | Wikipedia REST API (first paragraph) |
| `image_url` | STRING | Wikipedia / Wikimedia Commons (via Wikidata fallback) |

Convention: empty string `''` = "API tried, nothing found" vs `NULL` = "not yet attempted."

---

## Ingest Pipeline

Each data source has a dedicated handler in `ingest/`. All sources are run as **parallel Cloud Run executions** from the same container image, differentiated by `--source` args.

| Source | Records | Size | Time | Method |
|--------|---------|------|------|--------|
| IUCN Red List | ~311K taxa | ~20MB | ~15s | DwCA zip (iucn-latest) + distribution extension for the category |
| WRiMS | ~3.2K species × sea areas | small | minutes | GBIF checklist API + WoRMS REST distributions + Marine Regions boundaries |
| GISD (unused) | ~830 | <1MB | <1s | DwCA zip, 2011 snapshot; replaced by WRiMS |
| WoRMS | ~593K | ~90MB | ~60s | DwCA zip (authenticated download) |
| Divesites (PADI) | ~3,400 | <1MB | ~90s | Paginated REST API scrape |
| SSI | ~10,600 | <1MB | ~3min | Session auth + async tile subdivision |
| OBIS | ~203M | ~6.3GB | ~47min on Cloud Run | boto3 parallel download (16 workers) from S3 + DuckDB batch processing |

### OBIS Optimization

The original implementation used DuckDB's `httpfs` extension to query S3 directly — single-threaded per connection, resulting in ~78 min runtime. The current approach uses **boto3 parallel download** (16 workers) to fetch partitioned parquet files concurrently, then DuckDB processes them locally. Result: **78 min → 47 min (40% faster)**.

All sources output parquet files to a temp directory, then upload to GCS. The pipeline is idempotent — re-running overwrites previous data.

---

## Enrichment Pipeline

The enrichment pipeline (`enrich/`) gives the species the app shows a common name, a description and a credited image, stored in `species_enrichment` (a dbt source, never rebuilt by dbt).

### What it enriches

Species in `species_summary` (every species recorded near a dive site), most widespread first. A species is picked when it has no enrichment row, when this pipeline has never processed its row (`attempted_at` is NULL), or when a field is still missing and the last attempt is older than `ENRICH_RETRY_DAYS` (90).

### Sources, in order

1. **Common name:** GBIF species match (exact, species rank) → English vernacular name.
2. **Description:** Wikipedia summary by scientific name. Pages that are the genus (the species redirects to its genus) or a disambiguation are rejected; one-sentence "X is a species of …" stubs are kept and flagged `description_is_stub`.
3. **Image:** the Wikipedia article's image, else Wikidata's (P18), both resolved through Wikimedia Commons for an 800 px thumbnail (JPEG/PNG even for SVG/TIFF), the artist and the license. Local en.wikipedia files (usually non-free) are skipped.
4. **Image fallback:** a photo from a GBIF occurrence record, field observations (e.g. iNaturalist) before museum specimens.

Only images under CC0/public domain, CC BY, CC BY-SA, CC BY-NC or CC BY-NC-SA are kept (`enrich/licenses.py`), always with `image_credit`, `image_license` and `image_page_url` so the app can credit them. NoDerivatives and unknown licenses are dropped.

### Running and failure handling

- Results are merged into BigQuery every `ENRICH_FLUSH_SIZE` (2,000) species through a staging table, so a killed job loses at most one chunk. No local checkpoint.
- A Wikipedia lookup that fails (rate limit, network) leaves the stored row untouched and its `attempted_at` NULL, so the next run retries it; a genuine miss is recorded as a miss.
- `--new-only` (only species with no row), `--limit N`, `--dry-run` (look up, write nothing).
- Each run ends with a coverage line for the species at dive sites.

---

## App Architecture

The application is a **single-container deployment** with no external database server.

```
┌─────────────────────────────────────┐
│         Cloud Run Service           │
│                                     │
│  ┌───────────────────────────────┐  │
│  │  FastAPI (Python)             │  │
│  │  ├── /api/species/*           │  │
│  │  ├── /api/divesites/*         │  │
│  │  └── /* (static files)        │  │
│  └─────────────┬─────────────────┘  │
│                │                    │
│  ┌─────────────▼─────────────────┐  │
│  │  DuckDB (in-memory)           │  │
│  │  Loaded from Parquet at start │  │
│  └───────────────────────────────┘  │
│                                     │
│  ┌───────────────────────────────┐  │
│  │  React (pre-built static)     │  │
│  │  Served by FastAPI            │  │
│  └───────────────────────────────┘  │
└─────────────────────────────────────┘
```

### How it works

1. **Startup**: FastAPI lifespan loads 3 Parquet files (exported from BigQuery) into DuckDB in-memory tables
2. **API**: Two routers — species search and dive site explorer — query DuckDB directly
3. **Frontend**: React app is pre-built and served as static files from the same FastAPI process
4. **Data source**: In production, Parquet files are downloaded from GCS at startup. In local dev, files are mounted from disk.

### Exported Tables

| Table | Purpose | Size |
|-------|---------|------|
| `divesite_summary` | Map markers with species counts | ~13,600 rows |
| `species_summary` | Species search and species pages | ~65,000 rows |
| `divesite_species` | Site ↔ species pairs with counts, best-place metrics, per-site invasiveness | ~4M rows, ~67 MB parquet |

Each table is exported to its own folder (`app-export/<table>/part-*.parquet`; `bq extract` splits large tables). The app loads them into a compressed in-memory DuckDB catalog with a 300 MB limit: ~80 MB resident, ~360 MB peak while loading.

---

## Pipeline Order

The full pipeline runs in sequence: **Ingest → dbt → Enrich**.

```
Ingest (parallel)          dbt                    Enrich
┌──────────────┐      ┌──────────┐          ┌──────────────┐
│ IUCN    ─┐   │      │          │          │ GBIF API     │
│ WRiMS   ─┤   │      │ substrate│          │ Wikipedia    │
│ WoRMS   ─┼──▶│──▶   │ skeleton │──▶       │ Wikidata     │
│ PADI    ─┤   │      │ coral    │          │              │
│ SSI     ─┤   │      │          │          │ → BigQuery   │
│ OBIS    ─┘   │      │          │          │              │
└──────────────┘      └──────────┘          └──────────────┘
     GCS                 BigQuery              species_enrichment
```

On Cloud Run, the 5 ingest sources run as **separate parallel executions** of the same container image. dbt waits for all ingestion to complete, then enrichment waits for dbt.
