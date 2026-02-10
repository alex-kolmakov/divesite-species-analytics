# Marine Species Analytics - Development Plan

## Execution Order

```
Stage 1 (Infra + Ingestion)  -->  Stage 2 (dbt Modeling)  -->  Stage 3 (Frontend)
         |                                  |                          |
   Terraform + ingest/              dbt build works              App deployed
   Cloud Run Job works              Tests pass                   Users can search
   Data in GCS                      Data in BigQuery             Map visualization
```

Each stage is independently deployable and testable. We proceed to the next stage only after the current one is solid.

---

## Stage 1: Infrastructure & Ingestion Revamp [COMPLETE]

**Goal**: Replace Mage with lightweight Python scripts, deploy everything via Terraform on GCP as cheaply as possible, and have a single command to update all data.

### 1.1 Terraform Infrastructure (Cost-Optimized)

`terraform/` directory with:

- **GCS Bucket** for raw data (Parquet files) - `STANDARD` storage, lifecycle rules to auto-delete old versions
- **BigQuery Dataset** (`marine_data`) - on-demand pricing (no reservations)
- **Cloud Run Job** for the ingestion pipeline
  - Single container that runs all download/transform/upload steps sequentially
  - Triggered manually or on a schedule via Cloud Scheduler
  - 2 vCPU, 4GB RAM (OBIS processing needs DuckDB memory)
- **Artifact Registry** for the Docker image
- **Service Account** with minimal permissions (GCS write, BigQuery admin, Artifact Registry read)
- **IAM bindings** - principle of least privilege

**Cost estimate**: ~$0-5/month idle, ~$1-3 per full refresh run

### 1.2 Ingestion Pipeline

Single Python CLI (`ingest/`):

```
python -m ingest --all           # Run everything
python -m ingest --source obis   # Run just one source
python -m ingest --source divesites,worms  # Run specific sources
```

**Modules**:
- `ingest/__main__.py` - CLI entrypoint with argparse
- `ingest/sources/obis.py` - Download OBIS parquet, transform with DuckDB, upload to GCS
- `ingest/sources/iucn.py` - Download IUCN DwCA, parse, upload to GCS
- `ingest/sources/gisd.py` - Download GISD DwCA, parse, upload to GCS
- `ingest/sources/worms.py` - Download WoRMS DwCA (authenticated), parse, upload to GCS
- `ingest/sources/divesites.py` - Scrape PADI API (async), clean, upload to GCS
- `ingest/upload.py` - Shared GCS upload logic (chunked, resumable)
- `ingest/dwca.py` - Shared DwCA parsing logic
- `ingest/config.py` - All configuration from environment variables

### 1.3 Deliverables
- [x] `terraform/` with all infrastructure as code
- [x] `ingest/` Python package replacing all Mage pipelines
- [x] `Dockerfile` for Cloud Run Job
- [x] All secrets in environment variables / Secret Manager, none in repo

---

## Stage 2: dbt Data Modeling & Testing on BigQuery

**Goal**: Fix and expand the dbt project with comprehensive testing, proper CI, and correct configuration.

### 2.1 Fix Existing dbt Setup

- Fix `max_bytes_billed` (increase to reasonable limit or remove for dev)
- Fix external table staging (ensure GCS parquet files are correctly referenced)
- dbt project at top-level `dbt/` directory
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
