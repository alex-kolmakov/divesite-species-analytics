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

`162M+ ocean observations` · `7 scientific datasets` · `3,400+ dive sites` · `Full-stack app`

</div>

---

A marine biodiversity data platform that combines multiple scientific datasets to answer two questions:

- **"Where can I find species X?"** — Search for any marine species and see dive sites where it's been observed
- **"What lives near dive site Y?"** — Browse dive sites on a map and discover which species are present

![Screen Recording 2026-02-13 at 10 17 43 AM](https://github.com/user-attachments/assets/3b6efe2f-7d59-45c9-8dfc-155f0ab82318)


## Data at a Glance

| Source | Description | Records | Size | Ingestion |
|--------|-------------|---------|------|-----------|
| [OBIS](https://obis.org) | Ocean observations | ~162M | ~686MB | boto3 parallel (16 workers) from S3 |
| [GBIF](https://gbif.org) | Biodiversity occurrences | ~3B | ~2TB | BigQuery public dataset |
| [WoRMS](https://marinespecies.org) | Marine taxonomy | ~593K | ~90MB | DwCA zip (authenticated) |
| [IUCN Red List](https://iucnredlist.org) | Endangered species | ~255K | ~20MB | DwCA zip |
| [PADI](https://padi.com) | Dive site locations | ~3,400 sites | <1MB | Paginated REST API |
| [GISD](http://griis.org) | Invasive species | ~830 | <1MB | DwCA zip |
| Enrichment APIs | Names, descriptions, images | On-demand | — | GBIF + Wikipedia + Wikidata |

## Engineering Highlights

**40% faster OBIS ingestion** — boto3 parallel download (16 workers) + DuckDB batch processing replaced single-threaded DuckDB httpfs. 78 min → 47 min for 162M rows.

**Fault-tolerant enrichment** — Checkpoint after every batch, resume from failure with `--resume`, upload partial results with `--checkpoint-only`. No work is lost on crash.

**Parallel Cloud Run execution** — 5 ingest sources run simultaneously as separate Cloud Run job executions from the same container image.

**Smart API fallback chain** — GBIF + Wikipedia run concurrently, then Wikidata as fallback for missing images. Rate limiting, exponential backoff, and jitter on all API calls.

**Zero-cost app serving** — DuckDB in-memory on Parquet files, React frontend served as static files from FastAPI. Single container, no database server.

## Quick Start

**Prerequisites:** Python 3.11+, [uv](https://docs.astral.sh/uv/), Docker, [gcloud CLI](https://cloud.google.com/sdk/docs/install), [Terraform](https://developer.hashicorp.com/terraform/install), a GCP project with billing enabled.

```bash
git clone https://github.com/alex-kolmakov/divesite-species-analytics.git
cd divesite-species-analytics
uv sync --all-extras
cp env.example .env              # edit with your GCP project ID, bucket, URLs
make setup && make deploy && make app-deploy
```

For detailed GCP setup from scratch (service account creation, API enabling, Terraform config), see [`docs/SETUP.md`](docs/SETUP.md).

## Project Structure

```
ingest/              Python CLI - downloads, transforms, uploads to GCS
enrich/              Species enrichment pipeline (GBIF + Wikipedia + Wikidata → BigQuery)
dbt/                 dbt models (substrate / skeleton / coral)
app/                 UI application (FastAPI backend + React frontend)
terraform/           GCP infrastructure as code
docs/                Setup, testing, architecture, and workflow guides
.github/workflows/   CI pipeline (lint, typecheck, Docker build, Terraform validate)
```

## Makefile Quick Reference

| Target | Description |
|--------|-------------|
| `make setup` | One-time: authenticate, enable GCP APIs, build images, deploy infrastructure |
| `make deploy` | Build images, push to Artifact Registry, run full pipeline |
| `make export-data` | Rebuild enriched dbt models + export app tables to GCS |
| `make app-build` | Build and push the UI app Docker image |
| `make app-deploy` | Full app deployment: export data + build + deploy |
| `make help` | Show all targets |

## Development

```bash
set -a && source .env && set +a
export GOOGLE_APPLICATION_CREDENTIALS=secret.json

uv run python -m ingest --source iucn       # ingest a single source
cd dbt && uv run dbt run && cd ..            # build dbt models
uv run python -m enrich --new-only           # enrich unattempted species
uv run python -m app.backend.main            # start app on http://localhost:8080
```

Add `DEV=1` to any `make` target for sampled data and smaller batches: `make deploy DEV=1`

See [`docs/LOCAL_DATA_WORKFLOW.md`](docs/LOCAL_DATA_WORKFLOW.md) for the full local workflow and [`docs/TESTING.md`](docs/TESTING.md) for testing each component.

## Data Modeling

The dbt project uses a **medallion architecture** with marine biology-themed layers (substrate → skeleton → coral). See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for full details.

```
 Substrate (raw)          Skeleton (cleaned)           Coral (analytics)
┌──────────────┐      ┌──────────────────┐      ┌─────────────────────────┐
│ divesites    │      │ occurrences      │      │ near_dive_site_         │
│ gbif_occur.  │─────▶│ clustered_occur. │─────▶│   occurrences           │
│ obis_occur.  │      │ species          │      │ monthly_species_occur.  │
└──────────────┘      └──────────────────┘      │ divesite_species_freq.  │
                                                └─────────────────────────┘
```

## CI/CD

All checks run on every push and on pull requests to `main`:

| Job | What it does |
|-----|-------------|
| **Lint** | Ruff linting + format check on `ingest/` and `enrich/` |
| **Type Check** | Pyrefly static type analysis |
| **Docker Build** | Builds `ingest`, `dbt`, and `enrich` container images |
| **Terraform Validate** | Format check, init, and validate on `terraform/` |

---

## Acknowledgements & Credits

If you're interested in contributing to this project, need to report issues or submit pull requests, please get in touch via:
- [GitHub](https://github.com/alex-kolmakov)
- [LinkedIn](https://linkedin.com/in/aleksandr-kolmakov)

### DataTalks.Club

Acknowledgement to **#DataTalksClub** for mentoring us through the Data Engineering Zoom Camp over the last 10 weeks. It has been a privilege to take part in the Spring '24 Cohort, go and check them out!

![DataTalks.Club](https://github.com/alex-kolmakov/divesite-species-analytics/assets/3127175/d6504180-31a9-4cb7-8cd0-26cd2d0a12ad)
