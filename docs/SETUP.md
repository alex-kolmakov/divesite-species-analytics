# GCP Setup & Troubleshooting

This document covers GCP prerequisites, a complete environment variable reference, and common errors. For the deployment walkthrough, see the [README](../README.md#zero-to-production).

## Prerequisites

- Python 3.11+ and [uv](https://docs.astral.sh/uv/)
- Docker
- [Google Cloud SDK](https://cloud.google.com/sdk/docs/install)
- [Terraform](https://developer.hashicorp.com/terraform/install)
- A GCP project (default: `gbif-412615`)

## GCP APIs

Three APIs must be enabled manually before `make setup`:

| API | Why |
|-----|-----|
| [Service Usage API](https://console.cloud.google.com/apis/api/serviceusage.googleapis.com) | Lets Terraform enable other APIs |
| [Cloud Resource Manager API](https://console.cloud.google.com/apis/api/cloudresourcemanager.googleapis.com) | Lets Terraform manage project-level resources |
| [Secret Manager API](https://console.cloud.google.com/apis/api/secretmanager.googleapis.com) | Stores WoRMS credentials securely |

`make setup` automatically enables the remaining APIs:
- Cloud Run, Artifact Registry, BigQuery, IAM, Cloud Scheduler

## Service Account Roles

Create a service account in **IAM & Admin > Service Accounts** and grant these roles:

| Role | Purpose |
|------|---------|
| Storage Admin | Manage GCS buckets and objects |
| BigQuery Data Editor | Manage datasets and tables |
| BigQuery Job User | Run queries |
| Artifact Registry Administrator | Push Docker images |
| Secret Manager Admin | Create and manage secrets |
| Cloud Run Admin | Create and execute Cloud Run jobs/services |
| Service Account User | Allow Cloud Run to use the service account |
| Service Usage Admin | Enable GCP APIs via `make setup` |

Save the JSON key as `secret.json` in the project root (gitignored).

## Environment Variables

Copy `env.example` to `.env` and fill in your values. All variables used across the project:

### GCP

| Variable | Default | Used By | Description |
|----------|---------|---------|-------------|
| `PROJECT_ID` | — | ingest, enrich, terraform | GCP project ID |
| `GCS_BUCKET` | — | ingest, app | GCS bucket name |
| `BIGQUERY_DATASET` | — | enrich | BigQuery dataset name |
| `GOOGLE_APPLICATION_CREDENTIALS` | — | all | Path to service account key JSON |

### Data Source URLs

| Variable | Default | Description |
|----------|---------|-------------|
| `IUCN_REDLIST_URL` | — | IUCN Red List DwCA zip URL |
| `GISD_URL` | — | GISD DwCA zip URL |
| `WORMS_URL_TEMPLATE` | — | WoRMS download URL template (contains `{full_date}` placeholder) |
| `BASE_PADI_GUIDE_URL` | — | PADI dive guide API base URL |
| `BASE_PADI_MAP_URL` | — | PADI dive map API base URL |
| `WORMS_LOGIN` | `""` | WoRMS authenticated download login |
| `WORMS_PASSWORD` | `""` | WoRMS authenticated download password |

### Pipeline Tuning

| Variable | Default | Description |
|----------|---------|-------------|
| `ENRICH_BATCH_SIZE` | `500` | Number of species per enrichment batch |
| `OBIS_BATCH_SIZE` | `1` | Number of OBIS parquet files to download in parallel |
| `PROXIMITY_METERS` | `3000` | Radius (meters) for matching occurrences to dive sites (used by dbt) |
| `TEMP_DIR` | `/tmp/marine-data` | Local temp directory for downloaded files |

### App

| Variable | Default | Description |
|----------|---------|-------------|
| `EXPORT_PREFIX` | `app-export` | GCS prefix for exported app data |
| `PORT` | `8080` | Port the FastAPI server listens on |
| `LOCAL_DATA_DIR` | `data` | Local directory for parquet files (relative to `app/backend/`) |

### Development

| Variable | Default | Description |
|----------|---------|-------------|
| `DEV=1` (Makefile) | off | Pass to `make deploy`/`make refresh` for sampled data and smaller batches |

## Troubleshooting

### `PERMISSION_DENIED: Service Usage API has not been enabled`

Enable the three prerequisite APIs manually (see [GCP APIs](#gcp-apis) above), then re-run `make setup`.

### `invalid_grant` errors from `gcloud`

Your service account key or auth token has expired. Re-authenticate:

```bash
gcloud auth activate-service-account --key-file=secret.json
gcloud config set project gbif-412615
```

### Docker image fails silently on Cloud Run (no logs)

You likely built for the wrong architecture. Always build with `--platform linux/amd64`:

```bash
docker build --platform linux/amd64 -f Dockerfile.ingest -t <image> .
```

`make deploy` and `make setup` handle this automatically.

### `NOT_FOUND: Table not found` after `dbt run`

The upstream data hasn't been ingested yet. Run ingestion first:

```bash
uv run python -m ingest --all    # local
make refresh                      # Cloud Run
```

### WoRMS download returns 401/403

WoRMS requires authentication. Set `WORMS_LOGIN` and `WORMS_PASSWORD` in `.env`. These credentials are obtained from the WoRMS team upon request.

### `requests` drops auth on redirect

The `requests` library strips Basic Auth headers when following HTTPS-to-HTTP redirects. This affects WoRMS downloads. The ingest code handles this automatically.

### BigQuery MERGE fails with "must match at most one source row"

The target `species_enrichment` table has duplicate rows. Deduplicate before running enrichment:

```sql
CREATE OR REPLACE TABLE marine_data.species_enrichment AS
SELECT DISTINCT * FROM marine_data.species_enrichment;
```
