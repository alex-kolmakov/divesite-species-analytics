# Stage 1 Testing Guide

## A. Environment Setup

### Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (`curl -LsSf https://astral.sh/uv/install.sh | sh`)
- Docker (for container testing)
- `gcloud` CLI (for GCS/Terraform testing)
- Terraform (for infrastructure testing)

### Install dependencies

```bash
uv venv .venv
source .venv/bin/activate
uv pip install -r requirements-ingest.txt -r requirements-enrich.txt -r requirements-dev.txt
```

### Configure environment

```bash
cp env.example .env
# Edit .env with your values (see below)
set -a && source .env && set +a
```

**Environment variables:**

| Variable | Required | Description |
|----------|----------|-------------|
| `PROJECT_ID` | Yes | GCP project ID (`gbif-412615`) |
| `GCS_BUCKET` | Yes | GCS bucket name (`marine_data_412615`) |
| `IUCN_REDLIST_URL` | Yes | IUCN Red List DwCA zip URL |
| `GISD_URL` | Yes | GISD DwCA zip URL |
| `WORMS_URL_TEMPLATE` | Yes | WoRMS download URL template |
| `BASE_PADI_GUIDE_URL` | Yes | PADI dive guide API base URL |
| `BASE_PADI_MAP_URL` | Yes | PADI dive map API base URL |
| `WORMS_LOGIN` | Only for WoRMS | WoRMS authenticated download login |
| `WORMS_PASSWORD` | Only for WoRMS | WoRMS authenticated download password |
| `GOOGLE_APPLICATION_CREDENTIALS` | For GCS upload | Path to service account key JSON |
| `BIGQUERY_DATASET` | Enrich only | BigQuery dataset name (`marine_data`) |
| `TEMP_DIR` | No | Temporary directory (default: `/tmp/marine-data`) |

**Note:** OBIS reads directly from the public AWS S3 bucket (`s3://obis-open-data`) via DuckDB - no URL config needed.

---

## B. Local Source Testing

Load env vars and run each source individually:

```bash
source .venv/bin/activate
set -a && source .env && set +a
```

```bash
# Test a fast, small source first
python -m ingest --source iucn

# Test another small source
python -m ingest --source gisd

# Test the async dive sites scraper
python -m ingest --source divesites

# Test OBIS (queries S3 directly via DuckDB, needs internet + 2GB+ RAM)
python -m ingest --source obis

# Test WoRMS (requires WORMS_LOGIN and WORMS_PASSWORD)
python -m ingest --source worms

# Run everything
python -m ingest --source all
```

### Verify parquet output

```bash
# With DuckDB CLI
duckdb -c "SELECT COUNT(*) FROM read_parquet('/tmp/marine-data/redlist.parquet')"

# Or with Python
python -c "import pyarrow.parquet as pq; print(pq.read_metadata('/tmp/marine-data/redlist.parquet'))"
```

---

## C. GCS Upload Testing

Requires GCP authentication:

```bash
# Option 1: Service account key (set in .env)
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/secret.json

# Option 2: Application Default Credentials
gcloud auth application-default login
```

After running a source, verify the upload:

```bash
gsutil ls gs://marine_data_412615/
gsutil ls -l gs://marine_data_412615/redlist.parquet
```

---

## D. dbt Testing

After ingestion has uploaded parquet files to GCS, run dbt locally:

```bash
cd dbt

# Dry run — check compiled SQL without executing
dbt compile

# Run all models
dbt run

# Run with dev sampling (reduces bytes scanned)
dbt run --vars '{development: true}'

# Run a single model and its upstream dependencies
dbt run --select +species

# Run data tests
dbt test

# Run a specific test
dbt test --select assert_species_type_consistent_with_flags
```

### Verify models

```bash
# Check the species table was created
bq query --use_legacy_sql=false 'SELECT COUNT(*) FROM marine_data.species'

# Spot-check species flags
bq query --use_legacy_sql=false \
  'SELECT species_type, COUNT(*) FROM marine_data.species GROUP BY 1'
```

---

## E. Docker Testing

### Build

```bash
docker build -f Dockerfile.ingest -t ingest:local .
docker build -f Dockerfile.dbt -t dbt:local .
docker build -f Dockerfile.enrich -t enrich:local .
```

### Run

```bash
# Test with a small source (mount service account key)
docker run --env-file .env \
  -v /path/to/secret.json:/app/secret.json:ro \
  -e GOOGLE_APPLICATION_CREDENTIALS=/app/secret.json \
  ingest:local --source iucn

# Test dbt (needs BigQuery access via ADC or service account)
docker run --env-file .env \
  -v /path/to/secret.json:/app/secret.json:ro \
  -e GOOGLE_APPLICATION_CREDENTIALS=/app/secret.json \
  dbt:local

# Test enrichment (needs species table from dbt)
docker run --env-file .env \
  -v /path/to/secret.json:/app/secret.json:ro \
  -e GOOGLE_APPLICATION_CREDENTIALS=/app/secret.json \
  enrich:local
```

Check container logs for `Wrote parquet` and `Upload complete` messages to confirm success.

---

## F. Terraform Testing

```bash
cd terraform

# Initialize providers
terraform init

# Dry run - review what would be created
terraform plan

# Expected resources in plan output:
#  - google_storage_bucket.marine_data
#  - google_bigquery_dataset.marine_data
#  - google_cloud_run_v2_job.ingestion
#  - google_cloud_run_v2_job.dbt
#  - google_cloud_run_v2_job.enrichment
#  - google_artifact_registry_repository.marine
#  - google_service_account.ingest_sa
#  - google_project_iam_member (several bindings)
#  - google_cloud_scheduler_job.ingest_schedule (if enabled)

# Apply only when ready for real GCP changes
terraform apply
```

---

## G. CI / Linting Testing

### Pre-commit hooks

```bash
# Install hooks (one-time)
pre-commit install

# Run all hooks on all files
pre-commit run --all-files
```

### Manual lint and typecheck (same as CI)

```bash
# Lint
ruff check ingest/ enrich/

# Format check
ruff format --check ingest/ enrich/

# Type check
pyrefly check
```

---

## H. Expected Results per Source

| Source | Rows | File Size | Time | Output File |
|--------|------|-----------|------|-------------|
| IUCN | ~255K | ~20MB | ~15s | `redlist.parquet` |
| GISD | ~830 | <1MB | <1s | `invasive.parquet` |
| WoRMS | ~593K | ~90MB | ~60s | `worms.parquet` |
| OBIS | ~5M+ | ~80MB | 10-30min | `obis.parquet` |
| Divesites | ~3.4K | <1MB | ~90s | `divesites.parquet` |

**Notes:**
- WoRMS requires authentication credentials. Without them, the download will fail with a 401/403 error.
- OBIS queries the public S3 bucket directly via DuckDB (no ZIP download). Needs internet access and 2GB+ RAM.
- Divesites scrapes a paginated REST API. Timing varies with network conditions.
- Row counts and file sizes are approximate and will change as upstream datasets are updated.
