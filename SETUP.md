# Setup Guide

Complete guide to deploying Marine Species Analytics — from a fresh GCP account to a running application.

For architecture details, see [ARCHITECTURE.md](ARCHITECTURE.md). For local development, see [LOCAL_DATA_WORKFLOW.md](LOCAL_DATA_WORKFLOW.md).

---

## Prerequisites

- Python 3.11+ and [uv](https://docs.astral.sh/uv/)
- [Docker](https://docs.docker.com/get-docker/)
- [Google Cloud SDK](https://cloud.google.com/sdk/docs/install) (`gcloud`, `bq`, `gsutil`)
- [Terraform](https://developer.hashicorp.com/terraform/install)
- A GCP project with billing enabled

## Starting from a Fresh GCP Account

If you don't have a GCP project yet:

```bash
# Create a new project (pick a unique ID)
gcloud projects create <YOUR_PROJECT_ID> --name="Marine Species Analytics"
gcloud config set project <YOUR_PROJECT_ID>

# Link a billing account (required for BigQuery, Cloud Run, etc.)
gcloud billing accounts list
gcloud billing projects link <YOUR_PROJECT_ID> --billing-account=<BILLING_ACCOUNT_ID>
```

> **Note:** GCS bucket names must be globally unique across all of Google Cloud. The default `marine_data_412615` will only work for the original project. Choose a unique name like `marine_data_<YOUR_PROJECT_ID>`.

---

## Step-by-Step Deployment

### 1. Clone & Install

```bash
git clone https://github.com/alex-kolmakov/divesite-species-analytics.git
cd divesite-species-analytics
uv sync --all-extras
```

### 2. Create a GCP Service Account

Create a service account with the required roles:

```bash
# Create the service account
gcloud iam service-accounts create marine-analytics \
  --display-name="Marine Analytics Pipeline" \
  --project=<YOUR_PROJECT_ID>

# Grant required roles
SA_EMAIL="marine-analytics@<YOUR_PROJECT_ID>.iam.gserviceaccount.com"

for role in \
  roles/storage.admin \
  roles/bigquery.dataEditor \
  roles/bigquery.jobUser \
  roles/artifactregistry.admin \
  roles/run.admin \
  roles/secretmanager.admin \
  roles/iam.serviceAccountUser \
  roles/serviceusage.serviceUsageAdmin; do
  gcloud projects add-iam-policy-binding <YOUR_PROJECT_ID> \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="${role}" \
    --quiet
done

# Create and download the JSON key
gcloud iam service-accounts keys create secret.json \
  --iam-account="${SA_EMAIL}"
```

The `secret.json` file is gitignored and should never be committed.

### Service Account Roles Reference

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

### 3. Enable Required GCP APIs

Three APIs must be enabled **manually** before `make setup` can handle the rest:

| API | Console Link | Why |
|-----|-------------|-----|
| Service Usage API | [Enable](https://console.cloud.google.com/apis/api/serviceusage.googleapis.com) | Lets Terraform enable other APIs |
| Cloud Resource Manager API | [Enable](https://console.cloud.google.com/apis/api/cloudresourcemanager.googleapis.com) | Lets Terraform manage project-level resources |
| Secret Manager API | [Enable](https://console.cloud.google.com/apis/api/secretmanager.googleapis.com) | Stores WoRMS credentials securely |

Or via CLI:

```bash
gcloud services enable serviceusage.googleapis.com --project=<YOUR_PROJECT_ID>
gcloud services enable cloudresourcemanager.googleapis.com --project=<YOUR_PROJECT_ID>
gcloud services enable secretmanager.googleapis.com --project=<YOUR_PROJECT_ID>
```

`make setup` automatically enables the remaining APIs (Cloud Run, Artifact Registry, BigQuery, IAM, Cloud Scheduler).

### 4. Configure Environment

```bash
cp env.example .env
# Edit .env with your project ID, bucket name, dataset URLs, etc.
```

See the [Environment Variables](#environment-variables) section below for the full reference.

### 5. Configure Terraform

```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars with your project ID, region, bucket name
cd ..
```

### 6. One-Time Setup

```bash
make setup
```

This authenticates with GCP, enables remaining APIs, builds and pushes all Docker images, and applies Terraform infrastructure.

### 7. Deploy the Pipeline

```bash
make deploy       # Build images + run: Ingest → dbt → Enrich
```

This runs the full data pipeline: ingest all sources in parallel, build dbt models, then enrich species data. Takes ~1 hour on first run (OBIS is ~47 min).

### 8. Deploy the App

```bash
make app-deploy   # Export data to GCS + build + deploy FastAPI/React app to Cloud Run
```

The app URL will be printed when deployment completes.

---

## Environment Variables

Copy `env.example` to `.env` and fill in your values. The `.env` file uses quoted values for shell `source` compatibility; `Config.from_env()` strips quotes for Docker `--env-file` compatibility.

### GCP

| Variable | Default | Used By | Description |
|----------|---------|---------|-------------|
| `PROJECT_ID` | — | ingest, enrich, terraform | GCP project ID |
| `GCS_BUCKET` | — | ingest, app | GCS bucket name (must be globally unique) |
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

---

## Troubleshooting

### `PERMISSION_DENIED: Service Usage API has not been enabled`

Enable the three prerequisite APIs manually (see [step 3](#3-enable-required-gcp-apis) above), then re-run `make setup`.

### `invalid_grant` errors from `gcloud`

Your service account key or auth token has expired. Re-authenticate:

```bash
gcloud auth activate-service-account --key-file=secret.json
gcloud config set project <YOUR_PROJECT_ID>
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
CREATE OR REPLACE TABLE <YOUR_DATASET>.species_enrichment AS
SELECT DISTINCT * FROM <YOUR_DATASET>.species_enrichment;
```
