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
                                                │ species_divesite_summ.  │
                                                │ divesite_species_detail │
                                                │ divesite_summary        │
                                                └─────────────────────────┘
```

### Substrate (Raw)

External GCS parquet files loaded as BigQuery external tables. No transformations — raw data as ingested.

| Model | Source | Description |
|-------|--------|-------------|
| `divesites` | PADI REST API | ~3,400 dive site locations worldwide |
| `gbif_occurrences` | GBIF BigQuery public dataset | Species occurrence records (sampled in dev) |
| `obis_occurrences` | OBIS S3 bucket | ~162M occurrence records from ocean observations |

### Skeleton (Cleaned)

Validated, deduplicated, and unified datasets ready for analytics.

| Model | Description |
|-------|-------------|
| `occurrences` | Union of GBIF + OBIS, filtered to WoRMS-validated species only. Partitioned by `event_date` (month), clustered by `geography`. |
| `clustered_occurrences` | Re-clustered copy of occurrences with `species` as clustering key for fast species-level lookups. |
| `species` | Deduplicated species reference table with `is_endangered` (IUCN) and `is_invasive` (GISD) flags. |

### Coral (Analytics)

Denormalized tables optimized for the application's two primary queries.

| Model | Description |
|-------|-------------|
| `near_dive_site_occurrences` | Spatial join: each occurrence matched to nearest dive site within configurable radius (`PROXIMITY_METERS`). Uses `ST_DWithin` + distance ranking. |
| `monthly_species_occurrences` | Monthly aggregation of sightings per species per dive site. Powers temporal trend charts. |
| `divesite_species_frequency` | Species ranked by sighting count at each dive site. Intermediate table feeding the UI models. |
| `species_divesite_summary` | Denormalized for "Where can I find species X?" — clustered by `species` for fast single-species lookups. LEFT JOINs `species_enrichment` for common names and images. |
| `divesite_species_detail` | Denormalized for "What lives near dive site Y?" — clustered by `dive_site` for fast single-site lookups. LEFT JOINs `species_enrichment` for descriptions and images. |
| `divesite_summary` | One row per dive site with species counts and coordinates (~3,400 rows). Loaded entirely on app startup. |

### Core Column Schema

Columns present across the occurrence-based models:

| Column | Type | Description |
|--------|------|-------------|
| `species` | STRING | Scientific species name (WoRMS-validated) |
| `individual_count` | INTEGER | Individuals per sighting (defaults to 1 when null) |
| `event_date` | TIMESTAMP | Observation timestamp (partition key) |
| `geography` | GEOGRAPHY | BigQuery POINT geometry |
| `source` | STRING | Origin dataset (`OBIS` or `GBIF`) |
| `is_invasive` | BOOLEAN | Flagged by GISD |
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
| IUCN Red List | ~255K | ~20MB | ~15s | DwCA zip download + parse |
| GISD | ~830 | <1MB | <1s | DwCA zip download + parse |
| WoRMS | ~593K | ~90MB | ~60s | DwCA zip (authenticated download) |
| Divesites | ~3,400 | <1MB | ~90s | Paginated REST API scrape |
| OBIS | ~162M | ~686MB | ~47min | boto3 parallel download (16 workers) from S3 + DuckDB batch processing |

### OBIS Optimization

The original implementation used DuckDB's `httpfs` extension to query S3 directly — single-threaded per connection, resulting in ~78 min runtime. The current approach uses **boto3 parallel download** (16 workers) to fetch partitioned parquet files concurrently, then DuckDB processes them locally. Result: **78 min → 47 min (40% faster)**.

All sources output parquet files to a temp directory, then upload to GCS. The pipeline is idempotent — re-running overwrites previous data.

---

## Enrichment Pipeline

The enrichment pipeline (`enrich/`) populates species common names, descriptions, and images. It uses a **3-stage architecture designed to minimize BigQuery costs**.

### Architecture (5 BigQuery queries total)

```
Stage 1: Fetch work list          Stage 2: Process locally        Stage 3: Upload
┌─────────────────────┐          ┌──────────────────────┐       ┌──────────────┐
│ 1 query: get stats  │          │ For each batch:      │       │ 1 query:     │
│ 1 query: fetch all  │──────▶  │   • Call APIs        │──────▶│   MERGE via  │
│   species to process│          │   • Checkpoint /tmp  │       │   staging    │
│ 1 query: ensure     │          │   • 0 BQ queries     │       │   table      │
│   table exists      │          └──────────────────────┘       └──────────────┘
└─────────────────────┘
```

Previous approach: ~3N+2 queries for N batches (read + write per batch). Current: **5 total** — a **60x cost reduction** for 100 batches.

### API Fallback Chain

For each species, three API sources are queried in a concurrent-then-fallback pattern:

1. **GBIF REST API** → common names (English preferred)
2. **Wikipedia REST API** → description (first paragraph) + image URL
3. **Wikidata SPARQL** → fallback image URL if Wikipedia has none

Steps 1 and 2 run **concurrently** via `asyncio.gather`. Step 3 runs only when Wikipedia didn't provide an image. All APIs use rate limiting, exponential backoff, and jitter.

### Fault Tolerance

- **Checkpoint after every batch**: progress saved to `/tmp/enrich_checkpoints/enrichment_progress.json`
- **`--resume`**: continue from last checkpoint if a job fails mid-run
- **`--checkpoint-only`**: upload partial results to BigQuery without processing more batches
- **`--new-only`**: skip species that already have enrichment data (only process unattempted ones)

### Coverage

| Field | Coverage |
|-------|----------|
| Common names | ~62% |
| Descriptions | ~72% |
| Images | ~76% |

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
| `species_divesite_summary` | Species → dive site mapping for search | Clustered by species |
| `divesite_species_detail` | Dive site → species list for explorer | Clustered by dive_site |
| `divesite_summary` | Map markers with species counts | ~3,400 rows |

---

## Pipeline Order

The full pipeline runs in sequence: **Ingest → dbt → Enrich**.

```
Ingest (parallel)          dbt                    Enrich
┌──────────────┐      ┌──────────┐          ┌──────────────┐
│ IUCN    ─┐   │      │          │          │ GBIF API     │
│ GISD    ─┤   │      │ substrate│          │ Wikipedia    │
│ WoRMS   ─┼──▶│──▶   │ skeleton │──▶       │ Wikidata     │
│ PADI    ─┤   │      │ coral    │          │              │
│ OBIS    ─┘   │      │          │          │ → BigQuery   │
└──────────────┘      └──────────┘          └──────────────┘
     GCS                 BigQuery              species_enrichment
```

On Cloud Run, the 5 ingest sources run as **separate parallel executions** of the same container image. dbt waits for all ingestion to complete, then enrichment waits for dbt.
