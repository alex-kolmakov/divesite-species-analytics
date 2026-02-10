# Marine Species Analytics - Project Revitalization Plan

## Project Overview

A marine biodiversity data platform that combines multiple scientific datasets to answer:
- **"Where can I find species X?"** - Search for any marine species and see dive sites where it's been observed
- **"What lives near dive site Y?"** - Browse dive sites on a map and see which species are present

### Current State (Legacy)

The project uses **Mage.ai** for orchestration with a **medallion architecture** (Substrate/Skeleton/Coral layers), **dbt** for modeling on **BigQuery**, data staged in **GCS** as Parquet, and a basic **Streamlit** frontend.

**GCP Project**: `gbif-412615` | **BigQuery Dataset**: `marine_data` | **GCS Bucket**: `marine_data_412615`

### Data Sources
| Source | Description | Format | Size |
|--------|-------------|--------|------|
| OBIS | Ocean Biogeographic Information System - species occurrences | Parquet (partitioned) | ~700MB |
| GBIF | Global Biodiversity Information Facility (BigQuery public dataset) | BigQuery | Massive (sampled in dev) |
| IUCN Red List | Endangered species list | DwCA zip | Small |
| GISD | Global Invasive Species Database | DwCA zip | Small |
| WoRMS | World Register of Marine Species (taxonomy) | DwCA zip (auth required) | Medium |
| PADI | Dive site locations globally | REST API (paginated) | ~3K sites |
| Wikipedia | Species images and common names | MediaWiki API | On-demand |

### Existing dbt Models (9 models, 3 layers)
- **Substrate** (raw): `divesites`, `gbif_occurrences`, `obis_occurrences`
- **Skeleton** (cleaned): `occurrences` (GBIF+OBIS union, validated by WoRMS), `clustered_occurrences`, `species` (with endangered/invasive flags)
- **Coral** (analytics): `near_dive_site_occurrences`, `monthly_species_occurrences`, `divesite_species_frequency`

### Known Issues
1. **Security**: `secret.json`, `.env` with plaintext passwords committed to repo
2. **dbt pipeline failing**: External table staging + data modeling blocks both fail in Mage
3. **Hardcoded values**: GCP project ID, bucket name, credential paths scattered everywhere
4. **Code duplication**: Two invasive species pipelines, similar GCS exporters
5. **No Terraform**: Infrastructure is manually provisioned
6. **Mage overhead**: Heavy orchestrator for what are essentially batch download jobs
7. **`max_bytes_billed: 1000000`** (1MB) in dbt profiles - way too low for real queries

---

## Stage 1: Infrastructure & Ingestion Revamp

**Goal**: Replace Mage with lightweight Python scripts, deploy everything via Terraform on GCP as cheaply as possible, and have a single command to update all data.

### 1.1 Terraform Infrastructure (Cost-Optimized)

Create `terraform/` directory with:

- **GCS Bucket** for raw data (Parquet files) - use `STANDARD` storage, lifecycle rules to auto-delete old versions
- **BigQuery Dataset** (`marine_data`) - use on-demand pricing (no reservations)
- **Cloud Run Job** (NOT Cloud Functions - better for long-running downloads) for the ingestion pipeline
  - Single container that runs all download/transform/upload steps sequentially
  - Triggered manually or on a schedule via Cloud Scheduler (optional, cheap)
  - 2 vCPU, 4GB RAM should suffice (OBIS processing needs DuckDB memory)
- **Artifact Registry** for the Docker image
- **Service Account** with minimal permissions (GCS write, BigQuery admin, Artifact Registry read)
- **IAM bindings** - principle of least privilege
- Optional: **Cloud Scheduler** for periodic refresh (cron-based, very cheap)

**Cost estimate**: ~$0-5/month idle, ~$1-3 per full refresh run (Cloud Run + BigQuery on-demand + GCS storage)

### 1.2 Ingestion Pipeline Rewrite

Replace Mage with a single Python CLI (`ingest/`) that can:

```
python -m ingest --all           # Run everything
python -m ingest --source obis   # Run just one source
python -m ingest --source divesites,worms  # Run specific sources
```

**Modules to create**:
- `ingest/__main__.py` - CLI entrypoint with argparse
- `ingest/sources/obis.py` - Download OBIS parquet, transform with DuckDB, upload to GCS
- `ingest/sources/iucn.py` - Download IUCN DwCA, parse, upload to GCS
- `ingest/sources/gisd.py` - Download GISD DwCA, parse, upload to GCS
- `ingest/sources/worms.py` - Download WoRMS DwCA (authenticated), parse, upload to GCS
- `ingest/sources/divesites.py` - Scrape PADI API (async), clean, upload to GCS
- `ingest/upload.py` - Shared GCS upload logic (chunked, resumable)
- `ingest/dwca.py` - Shared DwCA parsing logic (deduplicated from current transformers)
- `ingest/config.py` - All configuration from environment variables (no hardcoding)

**Dockerfile**: Slim Python image, just the ingest package + requirements. Used by Cloud Run Job.

### 1.3 Cleanup

- Remove `orchestration/` Mage directory entirely (or archive it)
- Remove duplicate pipelines, stale files, DuckDB files from root
- Move secrets to GCP Secret Manager (referenced by Terraform)
- Add proper `.gitignore` entries for `.env`, `secret.json`, `*.duckdb`, `*.parquet`

### 1.4 Deliverables
- [ ] `terraform/` with all infrastructure as code
- [ ] `ingest/` Python package replacing all Mage pipelines
- [ ] `Dockerfile` for Cloud Run Job
- [ ] Single `make refresh` or `gcloud run jobs execute` to update all data
- [ ] All secrets in environment variables / Secret Manager, none in repo

---

## Stage 2: dbt Data Modeling & Testing on BigQuery

**Goal**: Fix and expand the dbt project with comprehensive testing, proper CI, and correct configuration.

### 2.1 Fix Existing dbt Setup

- Fix `max_bytes_billed` (increase to reasonable limit or remove for dev)
- Fix external table staging (ensure GCS parquet files are correctly referenced)
- Move dbt project out of `orchestration/analytics/` to top-level `analytics/` or `dbt/`
- Update `profiles.yml` to use environment variables for credentials (not hardcoded paths)

### 2.2 Expand Models

Keep the existing 3-layer architecture (Substrate/Skeleton/Coral) but improve:

**Substrate** (external tables from GCS):
- Keep: `divesites`, `obis_occurrences`, `gbif_occurrences`
- Add: Explicit column typing and descriptions in schema.yml

**Skeleton** (cleaned, validated):
- Keep: `occurrences`, `clustered_occurrences`, `species`
- Improve: Add incremental materialization where possible
- Add: `dim_divesites` (proper dimension with surrogate keys)

**Coral** (analytics):
- Keep: `near_dive_site_occurrences`, `monthly_species_occurrences`, `divesite_species_frequency`
- Add: `species_divesite_matrix` (pivot table for frontend)

### 2.3 Comprehensive dbt Tests

- **Schema tests**: not_null, unique, accepted_values, relationships on every model
- **Data tests**: Row count thresholds, freshness checks
- **Custom tests**: Geographic bounds validation (lat/lon ranges), date range sanity
- **Source freshness**: Check GCS parquet file modification dates

### 2.4 dbt CI

- Cloud Run Job or GitHub Action to run `dbt build` after ingestion completes
- Optionally chain: ingestion Cloud Run Job -> dbt Cloud Run Job via Workflows

### 2.5 Deliverables
- [ ] Working `dbt build` that creates all models in BigQuery
- [ ] 30+ dbt tests covering data quality
- [ ] `dbt/` directory with clean project structure
- [ ] CI pipeline for dbt (Terraform-managed)

---

## Stage 3: Frontend Application

**Goal**: Interactive web app to explore species-divesite relationships.

### 3.1 Features

**Feature A: Species Search**
- Search box for species name (common or scientific)
- Results show: species card (image, name, endangered/invasive badge)
- Click species -> map showing all dive sites where it's been observed
- Occurrence counts and temporal trends per dive site

**Feature B: Dive Site Explorer**
- Interactive world map with dive site markers
- Click dive site -> panel showing all species observed there
- Species list sortable by frequency, filterable by type (endangered/invasive/normal)
- Monthly occurrence chart

### 3.2 Tech Stack Options

**Option A: Enhanced Streamlit** (simplest, cheapest)
- Extend existing `run.py`
- Deploy on Streamlit Community Cloud (free) or Cloud Run
- Good enough for the use case, fast to build

**Option B: Next.js + Deck.gl** (best UX)
- Server-side rendering, fast map interactions
- API routes querying BigQuery
- Deploy on Cloud Run or Vercel
- More work but much better map experience

**Option C: Streamlit + custom Deck.gl components** (middle ground)
- Use `pydeck` for rich map visualizations within Streamlit
- Keep deployment simple

### 3.3 Data Access Layer

- BigQuery queries via Python client (Streamlit) or REST API (Next.js)
- Cache frequently accessed data (species list, dive site list) in-memory or Redis
- Parameterized queries to prevent SQL injection (already done in current code)

### 3.4 Deliverables
- [ ] Interactive species search with map visualization
- [ ] Dive site explorer with species listings
- [ ] Deployed and accessible publicly
- [ ] Connected to live BigQuery data (auto-refreshed by Stage 1 pipeline)

---

## Execution Order

```
Stage 1 (Infra + Ingestion)  ──→  Stage 2 (dbt Modeling)  ──→  Stage 3 (Frontend)
         ↓                                  ↓                          ↓
   Terraform + ingest/              dbt build works              App deployed
   Cloud Run Job works              Tests pass                   Users can search
   Data in GCS                      Data in BigQuery             Map visualization
```

Each stage is independently deployable and testable. We proceed to the next stage only after the current one is solid.
