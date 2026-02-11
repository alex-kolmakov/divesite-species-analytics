## Prerequisites

- Python 3.11+ and [uv](https://docs.astral.sh/uv/)
- Docker
- [Google Cloud SDK](https://cloud.google.com/sdk/docs/install)
- [Terraform](https://developer.hashicorp.com/terraform/install)
- A GCP project (default: `gbif-412615`)

## GCP Project Preparation

Before Terraform can manage your infrastructure, several GCP APIs must be enabled manually in the console. These are **one-time** steps per project.

### Required APIs

Enable each of these in the GCP console (click the link, then click **Enable**):

| API | Link | Why |
|-----|------|-----|
| Service Usage API | [Enable](https://console.cloud.google.com/apis/api/serviceusage.googleapis.com/metrics?project=gbif-412615) | Required for Terraform to enable other APIs |
| Cloud Resource Manager API | [Enable](https://console.cloud.google.com/apis/api/cloudresourcemanager.googleapis.com/metrics?project=gbif-412615) | Required for Terraform to manage project-level resources |
| Secret Manager API | [Enable](https://console.cloud.google.com/apis/api/secretmanager.googleapis.com/metrics?project=gbif-412615) | Stores WoRMS credentials securely |

After enabling these three, `make bootstrap` will enable the remaining APIs automatically:
- Cloud Run API
- Artifact Registry API
- BigQuery API
- IAM API
- Cloud Scheduler API

### Service Account

1. Go to **IAM & Admin > Service Accounts** in the GCP console
2. Create a service account (or use an existing one like `dbt-325@gbif-412615`)
3. Grant it the following roles:
   - **Storage Admin** - manage GCS buckets and objects
   - **BigQuery Data Editor** + **BigQuery Job User** - manage datasets and run queries
   - **Artifact Registry Administrator** - push Docker images
   - **Secret Manager Admin** - create and manage secrets
   - **Cloud Run Admin** - create and execute Cloud Run jobs
   - **Service Account User** - allow Cloud Run to use the ingestion service account
   - **Service Usage Admin** - enable GCP APIs via `make bootstrap`
4. Create a JSON key and save it as `secret.json` in the project root

## Local Setup

1. Clone the repository:

```sh
git clone https://github.com/alex-kolmakov/divesite-species-analytics.git
cd divesite-species-analytics
```

2. Install dependencies:

```sh
uv venv .venv && source .venv/bin/activate
uv pip install -r requirements-ingest.txt -r requirements-enrich.txt -r requirements-dev.txt
```

3. Place your `secret.json` in the project root (it's gitignored).

4. Configure environment variables:

```sh
cp env.example .env
# Edit .env with your values
```

See [TESTING.md](TESTING.md) for the full list of environment variables.

## First-Time Deployment

After enabling the 3 APIs above and placing `secret.json`:

```sh
# Authenticate, enable remaining APIs, and import existing resources
make bootstrap

# Build and push Docker images to Artifact Registry
make push

# Deploy all GCP infrastructure
make infra
```

## Subsequent Deployments

```sh
# Re-authenticate (if you see "invalid_grant" errors)
make auth

# Full deploy: rebuild images, push, and run Cloud Run jobs
make deploy

# Or just re-run jobs without rebuilding
make refresh
```

## Local Development

```sh
source .env

# 1. Ingest data sources to GCS
python -m ingest --source iucn          # single source
python -m ingest --source all           # everything

# 2. Build dbt models in BigQuery (requires data in GCS)
cd dbt && dbt run && cd ..

# 3. Enrich species table via GBIF/Wikipedia/Wikidata (requires species table from dbt)
python -m enrich
```

Run `make help` for all available targets.
