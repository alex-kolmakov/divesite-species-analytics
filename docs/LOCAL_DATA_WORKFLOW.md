# Local Data Refresh & UI Launch Workflow

This guide documents the process to refresh BigQuery data, sync it to your local environment, and launch the UI with the latest data.

## Prerequisites

- **Tools**: `uv`, `docker`, `gcloud`, `bq`
- **Authentication**: Ensure you are authenticated with GCP (`gcloud auth login`, `gcloud config set project ...`)
- **Environment**: Ensure `.env` exists and contains necessary variables (including `PROXIMITY_METERS`).

## 1. Update Remote Data (BigQuery)

Run `dbt` to refresh the aggregation tables in BigQuery.

```bash
# Load environment variables (needed for PROXIMITY_METERS)
source .env

# Run dbt models
cd dbt
uv run dbt run --select species_divesite_summary divesite_species_detail divesite_summary
cd ..
```

## 2. Export Data to GCS

Export the refreshed BigQuery tables to Google Cloud Storage as Parquet files.

```bash
# Export tables to GCS bucket (replace project/dataset IDs if different)
bq extract --destination_format=PARQUET --compression=SNAPPY \
  'gbif-412615:marine_data.species_divesite_summary' \
  'gs://marine_data_412615/app-export/species_divesite_summary.parquet'

bq extract --destination_format=PARQUET --compression=SNAPPY \
  'gbif-412615:marine_data.divesite_species_detail' \
  'gs://marine_data_412615/app-export/divesite_species_detail.parquet'

bq extract --destination_format=PARQUET --compression=SNAPPY \
  'gbif-412615:marine_data.divesite_summary' \
  'gs://marine_data_412615/app-export/divesite_summary.parquet'
```

## 3. Download Data Locally

Fetch the Parquet files from GCS to your local backend data directory.

```bash
# Ensure directory exists
mkdir -p app/backend/data

# Download files (use quotes to prevent shell globbing issues with wildcard)
gcloud storage cp 'gs://marine_data_412615/app-export/*.parquet' app/backend/data/
```

## 4. Launch UI Locally (Docker)

Build and run the application Docker container, mounting the local data directory so the app uses the fresh data.

```bash
# 1. Build the image
docker build -t marine-species-analytics .

# 2. Stop any existing container on port 8080
docker rm -f marine-app || true

# 3. Run container with volume mount
# Maps local 'app/backend/data' -> container '/app/data'
docker run --rm -d \
  -p 8080:8080 \
  -v $(pwd)/app/backend/data:/app/data \
  --name marine-app \
  marine-species-analytics

# 4. Check logs
docker logs -f marine-app
```

The application will be available at [http://localhost:8080](http://localhost:8080).
