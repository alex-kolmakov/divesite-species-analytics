<div align="center">

# Marine Species Analytics

**Where biodiversity data meets dive site discovery**

[![CI](https://github.com/alex-kolmakov/divesite-species-analytics/actions/workflows/ci.yml/badge.svg)](https://github.com/alex-kolmakov/divesite-species-analytics/actions/workflows/ci.yml)
[![Python 3.11](https://img.shields.io/badge/python-3.11-3776AB?logo=python&logoColor=white)](https://python.org)
[![Terraform](https://img.shields.io/badge/terraform-GCP-844FBA?logo=terraform&logoColor=white)](terraform/)
[![dbt](https://img.shields.io/badge/dbt-BigQuery-FF694B?logo=dbt&logoColor=white)](dbt/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![Pyrefly](https://img.shields.io/badge/types-pyrefly-F7DC6F?logo=python&logoColor=white)](https://github.com/facebook/pyrefly)

*A marine biodiversity data platform combining multiple scientific datasets to answer:*

**"Where can I find species X?"** · **"What lives near dive site Y?"**

</div>

---

## Architecture

<!-- Source: docs/architecture.excalidraw — export to SVG after editing -->
![Architecture](docs/architecture.svg)

## Data Sources

| Source | Description | Records | Method |
|--------|-------------|---------|--------|
| [OBIS](https://obis.org) | Ocean Biogeographic Information System | ~162M occurrences | S3 Parquet via boto3 |
| [GBIF](https://gbif.org) | Global Biodiversity Information Facility | Massive (sampled) | BigQuery public dataset |
| [IUCN Red List](https://iucnredlist.org) | Endangered species assessments | ~255K | DwCA zip |
| [GISD](http://griis.org) | Global Invasive Species Database | ~830 | DwCA zip |
| [WoRMS](https://marinespecies.org) | World Register of Marine Species | ~593K | DwCA zip (auth) |
| [PADI](https://padi.com) | Dive site locations globally | ~3.4K sites | REST API |
| Enrichment APIs | Species common names, descriptions, images | On-demand | GBIF + Wikipedia REST + Wikidata SPARQL |

## Data Modeling

The dbt project uses a **medallion architecture** with marine biology-themed layers:

```
 Substrate (raw)          Skeleton (cleaned)           Coral (analytics)
┌──────────────┐      ┌──────────────────┐      ┌─────────────────────────┐
│ divesites    │      │ occurrences      │      │ near_dive_site_         │
│ gbif_occur.  │─────▶│ clustered_occur. │─────▶│   occurrences           │
│ obis_occur.  │      │ species          │      │ monthly_species_occur.  │
└──────────────┘      └──────────────────┘      │ divesite_species_freq.  │
                                                └─────────────────────────┘
```

| Column | Type | Description |
|--------|------|-------------|
| `species` | STRING | Scientific species name |
| `individualcount` | INTEGER | Individuals per sighting |
| `eventdate` | TIMESTAMP | Observation timestamp |
| `geography` | GEOGRAPHY | BigQuery POINT geometry |
| `source` | STRING | Origin dataset (OBIS/GBIF) |
| `is_invasive` | BOOLEAN | Flagged by GISD |
| `is_endangered` | BOOLEAN | Flagged by IUCN Red List |

## Project Structure

```
ingest/              Python CLI - downloads, transforms, uploads to GCS
enrich/              Species enrichment pipeline (GBIF + Wikipedia + Wikidata → BigQuery)
dbt/                 dbt models (substrate / skeleton / coral)
app/                 UI application (FastAPI backend + React frontend)
terraform/           GCP infrastructure as code
docs/                Setup, testing, and workflow guides
.github/workflows/   CI pipeline (lint, typecheck, Docker build, Terraform validate)
```

## Zero to Production

Follow steps 1–8 to go from a fresh clone to a fully deployed app. For GCP details and troubleshooting, see [`docs/SETUP.md`](docs/SETUP.md).

### 1. Prerequisites

- Python 3.11+ and [uv](https://docs.astral.sh/uv/)
- [Docker](https://docs.docker.com/get-docker/)
- [Google Cloud SDK](https://cloud.google.com/sdk/docs/install) (`gcloud`, `bq`)
- [Terraform](https://developer.hashicorp.com/terraform/install)
- A GCP project (default: `gbif-412615`)

### 2. Clone & Install

```bash
git clone https://github.com/alex-kolmakov/divesite-species-analytics.git
cd divesite-species-analytics
uv sync --all-extras
```

### 3. Create a GCP Service Account

1. Go to **IAM & Admin > Service Accounts** in the GCP console
2. Create a service account with these roles:
   - Storage Admin, BigQuery Data Editor, BigQuery Job User
   - Artifact Registry Administrator, Cloud Run Admin
   - Secret Manager Admin, Service Account User, Service Usage Admin
3. Create a JSON key and save it as `secret.json` in the project root (gitignored)

### 4. Enable Required GCP APIs

These three must be enabled manually before `make setup` can handle the rest:

| API | Console Link |
|-----|-------------|
| Service Usage API | [Enable](https://console.cloud.google.com/apis/api/serviceusage.googleapis.com) |
| Cloud Resource Manager API | [Enable](https://console.cloud.google.com/apis/api/cloudresourcemanager.googleapis.com) |
| Secret Manager API | [Enable](https://console.cloud.google.com/apis/api/secretmanager.googleapis.com) |

### 5. Configure Environment

```bash
cp env.example .env
# Edit .env with your values (see docs/SETUP.md for full variable reference)
```

### 6. One-Time Setup

```bash
make setup
```

This authenticates with GCP, enables remaining APIs, builds and pushes Docker images, and applies Terraform infrastructure.

### 7. Deploy the Pipeline

```bash
make deploy       # Build images + run: Ingest → dbt → Enrich
```

### 8. Deploy the App

```bash
make app-deploy   # Export data to GCS + build + deploy FastAPI/React app to Cloud Run
```

## Local Development

For local runs, load environment variables and use `uv run`:

```bash
set -a && source .env && set +a
export GOOGLE_APPLICATION_CREDENTIALS=secret.json

# Ingest
uv run python -m ingest --source iucn          # single source
uv run python -m ingest --source iucn,gisd     # multiple sources
uv run python -m ingest --all                  # everything

# dbt
cd dbt && uv run dbt run && cd ..

# Enrich
uv run python -m enrich --new-only             # only unattempted species

# Local UI (see docs/LOCAL_DATA_WORKFLOW.md for full workflow)
uv run python -m app.backend.main              # starts on http://localhost:8080
```

### Development Mode

Add `DEV=1` to any `make` target to use sampled data and smaller batches — useful for faster iteration without processing the full ~162M OBIS dataset:

```bash
make deploy DEV=1
make refresh DEV=1
```

## Makefile Quick Reference

| Target | Description |
|--------|-------------|
| `make setup` | One-time: authenticate, enable GCP APIs, build images, deploy infrastructure |
| `make deploy` | Build images, push to Artifact Registry, run full pipeline |
| `make refresh` | Re-run pipeline without rebuilding images |
| `make infra` | Apply Terraform changes |
| `make export-data` | Rebuild enriched dbt models + export app tables to GCS |
| `make app-build` | Build and push the UI app Docker image |
| `make app-deploy` | Full app deployment: export data + build + deploy |
| `make help` | Show all targets |

## CI/CD

All checks run on every push and on pull requests to `main`:

| Job | What it does |
|-----|-------------|
| **Lint** | Ruff linting + format check on `ingest/` and `enrich/` |
| **Type Check** | Pyrefly static type analysis |
| **Docker Build** | Builds `ingest`, `dbt`, and `enrich` container images |
| **Terraform Validate** | Format check, init, and validate on `terraform/` |

## [Dashboard](https://lookerstudio.google.com/s/vSQv3DXuGNQ)

- Divesites and observations distribution between used sources
- Invasive species near divesites
- Endangered species near divesites
- Top 20 invasive species near divesites

<img width="1265" alt="Dashboard screenshot" src="https://github.com/alex-kolmakov/divesite-species-analytics/assets/3127175/3e01401b-4dce-41f4-af46-ee03aae6be33">

---

## Acknowledgements & Credits

If you're interested in contributing to this project, need to report issues or submit pull requests, please get in touch via:
- [GitHub](https://github.com/alex-kolmakov)
- [LinkedIn](https://linkedin.com/in/aleksandr-kolmakov)

### DataTalks.Club

Acknowledgement to **#DataTalksClub** for mentoring us through the Data Engineering Zoom Camp over the last 10 weeks. It has been a privilege to take part in the Spring '24 Cohort, go and check them out!

![DataTalks.Club](https://github.com/alex-kolmakov/divesite-species-analytics/assets/3127175/d6504180-31a9-4cb7-8cd0-26cd2d0a12ad)
