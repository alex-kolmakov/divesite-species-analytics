# Local Data Refresh & UI Launch Workflow

This guide documents the process to refresh BigQuery data, sync it to your local environment, and launch the UI with the latest data.

## Quick Way

The Makefile provides a single command that runs all steps below:

```bash
set -a && source .env && set +a
export GOOGLE_APPLICATION_CREDENTIALS=secret.json

make update-data   # Enrich → rebuild dbt coral models → export → download
make app           # Run app locally in Docker (http://localhost:8080)
```

## Manual Steps

If you need more control, follow the steps below individually.

### Prerequisites

- **Tools**: `uv`, `docker`, `gcloud`, `bq`
- **Authentication**: Ensure you are authenticated with GCP (`gcloud auth login`, `gcloud config set project ...`)
- **Environment**: Ensure `.env` exists and contains necessary variables (including `PROXIMITY_METERS`).

### 1. Update Remote Data (BigQuery)

Run `dbt` to refresh the aggregation tables in BigQuery.

```bash
# Load environment variables (needed for PROXIMITY_METERS)
source .env

# Run dbt models
cd dbt
uv run dbt run --select species_divesite_summary divesite_species_detail divesite_summary
cd ..
```

### 2. Export Data to GCS

Export the refreshed BigQuery tables to Google Cloud Storage as Parquet files. Replace `$PROJECT_ID`, `$BIGQUERY_DATASET`, and `$GCS_BUCKET` with your values (or source `.env` first).

```bash
bq extract --destination_format=PARQUET --compression=SNAPPY \
  "${PROJECT_ID}:${BIGQUERY_DATASET}.species_divesite_summary" \
  "gs://${GCS_BUCKET}/app-export/species_divesite_summary.parquet"

bq extract --destination_format=PARQUET --compression=SNAPPY \
  "${PROJECT_ID}:${BIGQUERY_DATASET}.divesite_species_detail" \
  "gs://${GCS_BUCKET}/app-export/divesite_species_detail.parquet"

bq extract --destination_format=PARQUET --compression=SNAPPY \
  "${PROJECT_ID}:${BIGQUERY_DATASET}.divesite_summary" \
  "gs://${GCS_BUCKET}/app-export/divesite_summary.parquet"
```

### 3. Download Data Locally

Fetch the Parquet files from GCS to your local backend data directory.

```bash
# Ensure directory exists
mkdir -p app/backend/data

# Download files
gcloud storage cp "gs://${GCS_BUCKET}/app-export/*.parquet" app/backend/data/
```

### 4. Launch UI Locally (Docker)

Build and run the application Docker container, mounting the local data directory so the app uses the fresh data.

```bash
# Build the image
docker build -t marine-species-analytics .

# Stop any existing container on port 8080
docker rm -f marine-app || true

# Run container with volume mount
docker run --rm -d \
  -p 8080:8080 \
  -v $(pwd)/app/backend/data:/app/data \
  --name marine-app \
  marine-species-analytics

# Check logs
docker logs -f marine-app
```

The application will be available at [http://localhost:8080](http://localhost:8080).

Alternatively, use `make app` which handles the build and run steps automatically.
