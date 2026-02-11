# Marine Species Analytics

## Project Overview

A marine biodiversity data platform that combines multiple scientific datasets to answer:
- **"Where can I find species X?"** - Search for any marine species and see dive sites where it's been observed
- **"What lives near dive site Y?"** - Browse dive sites on a map and see which species are present

**GCP Project**: `gbif-412615` | **BigQuery Dataset**: `marine_data` | **GCS Bucket**: `marine_data_412615`

## Project Structure

```
ingest/             # Python CLI for downloading/parsing/uploading data sources to GCS
enrich/             # Species enrichment pipeline (GBIF + Wikipedia + Wikidata → BigQuery)
dbt/                # dbt project (substrate/skeleton/coral models)
terraform/          # GCP infrastructure as code
docs/               # Setup and testing guides
Makefile            # Build/deploy/lint targets (run 'make help')
```

## Data Sources

| Source | Description | Format | Size |
|--------|-------------|--------|------|
| OBIS | Ocean Biogeographic Information System - species occurrences | Parquet (partitioned) | ~700MB |
| GBIF | Global Biodiversity Information Facility (BigQuery public dataset) | BigQuery | Massive (sampled in dev) |
| IUCN Red List | Endangered species list | DwCA zip | Small |
| GISD | Global Invasive Species Database | DwCA zip | Small |
| WoRMS | World Register of Marine Species (taxonomy) | DwCA zip (auth required) | Medium |
| PADI | Dive site locations globally | REST API (paginated) | ~3K sites |
| Enrichment APIs | Common names, descriptions, images | GBIF + Wikipedia REST + Wikidata SPARQL | On-demand |

## dbt Models (9 models, 3 layers)

- **Substrate** (raw): `divesites`, `gbif_occurrences`, `obis_occurrences`
- **Skeleton** (cleaned): `occurrences` (GBIF+OBIS union, validated by WoRMS), `clustered_occurrences`, `species` (with endangered/invasive flags)
- **Coral** (analytics): `near_dive_site_occurrences`, `monthly_species_occurrences`, `divesite_species_frequency`

## Pipeline Order

**Ingest → dbt → Enrich** (each step depends on the previous)

```bash
# 1. Ingest: download sources, convert to parquet, upload to GCS
python -m ingest --all           # Run everything
python -m ingest --source obis   # Run just one source
python -m ingest --source divesites,worms  # Run specific sources

# 2. dbt: build BigQuery models from GCS parquet (requires data in GCS)
cd dbt && dbt run && cd ..

# 3. Enrich: populate species common names/descriptions/images (requires species table)
python -m enrich
```

### Production (Cloud Run)

```bash
make deploy    # push images + run ingest → dbt → enrich
make refresh   # re-run jobs without rebuilding images
```

### Configuration

- `.env` uses quoted values for shell `source` compatibility; `Config.from_env()` strips quotes for Docker `--env-file` compatibility
- Auth: `secret.json` in project root (service account key, gitignored)
- GCS `storage.Client()` needs `project=` parameter explicitly
- **Package manager**: `uv` — use `uv pip install` / `uv add` instead of `pip install`

### Known Patterns

- OBIS data: use `s3://obis-open-data/occurrence/*.parquet` via DuckDB httpfs (public, always fresh)
- OBIS schema: columns are nested in `interpreted` struct (e.g., `interpreted.species`, `interpreted.decimalLatitude`)
- Pre-commit: pyrefly uses `local` hook with `language: system`; ruff hooks scoped with `files: ^(ingest|enrich)/`

### Cloud Run Gotchas

- **Architecture**: Always build with `--platform linux/amd64` on Apple Silicon — Cloud Run runs amd64 only. Symptom: container dies instantly with no logs.
- **Image updates**: `lifecycle { ignore_changes = [image] }` in Terraform means you must `gcloud run jobs update --image` after pushing new images. Cloud Run resolves `:latest` at deploy time, not execution time.
- **Read-only filesystem**: Cloud Run container filesystem is read-only except `/tmp`. DuckDB needs `SET temp_directory = '/tmp/...'`; dbt needs `--log-path /tmp/dbt-logs --target-path /tmp/dbt-target`.
- **Auth on redirects**: Python `requests` strips Basic Auth on HTTPS→HTTP redirects. Use the final URL directly if the server redirects across schemes.
- **Secret Manager**: Terraform creates empty secret shells — populate real values out-of-band with `gcloud secrets versions add`.
- **Stale URLs**: External dataset URLs change. Use "latest" aliases (e.g., `iucn-latest.zip`) when available; add retry/fallback logic for date-templated URLs.

### Enrichment API Notes

- Wikipedia REST API needs `Api-User-Agent` header in aiohttp (not just `User-Agent`) — 403 without it
- Wikipedia REST direct lookup (`/api/rest_v1/page/summary/{name}`) returns 404 cleanly — safer than search API
- GBIF BigQuery public dataset has NO vernacular names — only the REST API does
- Wikidata `Special:FilePath` URLs need MD5-based conversion to direct `upload.wikimedia.org` thumbnail URLs

## Articles (gitignored)

Draft writeups in `articles/` (gitignored, not committed):
- `01-cloud-run-deployment-pitfalls.md` — 8 problems deploying a data pipeline to Cloud Run Jobs with Terraform
- `02-species-enrichment-pipeline.md` — redesigning species enrichment from Wikipedia scraping to a 3-source API pipeline (16% → 83% coverage)
- `03-obis-ingestion-optimization.md` — optimizing 162M row S3-to-GCS transfer: DuckDB httpfs vs boto3 parallel download (78 min → 47 min)
