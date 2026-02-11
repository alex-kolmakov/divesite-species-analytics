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

```
                     ┌──────────────┐
                     │  Cloud       │
                     │  Scheduler   │
                     └──────┬───────┘
                            │ trigger
                     ┌──────▼───────┐        ┌──────────────┐
  OBIS (S3)  ───┐   │              │        │              │
  IUCN (ZIP) ───┤   │  Cloud Run   │───────▶│     GCS      │
  GISD (ZIP) ───┤──▶│  Ingest Job  │ upload │   (Parquet)  │
  WoRMS (ZIP)───┤   │              │        │              │
  PADI (API) ───┘   └──────────────┘        └──────┬───────┘
                                                    │ external tables
                     ┌──────────────┐        ┌──────▼───────┐
                     │  Cloud Run   │        │              │
                     │  dbt Job     │───────▶│   BigQuery   │
                     │              │        │  (dbt models)│
                     └──────────────┘        └──────┬───────┘
                                                    │ species table
                     ┌──────────────┐        ┌──────▼───────┐
                     │  Enrichment  │        │              │
                     │  (Cloud Run) │───────▶│   BigQuery   │
                     │ GBIF+WP+WD  │ enrich │  (+ images)  │
                     └──────────────┘        └──────┬───────┘
                                                    │
                                             ┌──────▼───────┐
                                             │   Frontend   │
                                             │  (Streamlit) │
                                             └──────────────┘

  Pipeline order: Ingest → dbt → Enrich
```

## Data Sources

| Source | Description | Records | Method |
|--------|-------------|---------|--------|
| [OBIS](https://obis.org) | Ocean Biogeographic Information System | ~5M+ occurrences | S3 Parquet via DuckDB |
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
terraform/           GCP infrastructure as code
.github/workflows/   CI pipeline (lint, typecheck, Docker build, Terraform validate)
docs/                Setup and testing guides
```

## Quick Start

> Full setup guide: [`docs/SETUP.md`](docs/SETUP.md) | Testing guide: [`docs/TESTING.md`](docs/TESTING.md)

### Prerequisites

- Python 3.11+ and [uv](https://docs.astral.sh/uv/)
- GCP project with BigQuery and GCS
- Docker (for container builds)
- Terraform (for infrastructure)

### Setup

```bash
git clone https://github.com/alex-kolmakov/divesite-species-analytics.git
cd divesite-species-analytics

uv venv .venv && source .venv/bin/activate
uv pip install -r requirements-ingest.txt -r requirements-enrich.txt -r requirements-dev.txt

cp env.example .env   # edit with your values
```

### Local Development

```bash
source .env

python -m ingest --source iucn          # single source
python -m ingest --source iucn,gisd     # multiple sources
python -m ingest --source all           # everything

cd dbt && dbt run && cd ..              # build BigQuery models
python -m enrich                        # species enrichment (requires species table from dbt)
```

### Production Deployment

```bash
make infra                       # deploy GCP infrastructure via Terraform
make deploy                      # build images, push to Artifact Registry, run Cloud Run jobs
make refresh                     # re-run Cloud Run jobs without rebuilding images
```

Run `make help` for the full list of targets.

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
