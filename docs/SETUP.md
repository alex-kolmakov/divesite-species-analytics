## Prerequisites

- Python 3.11+ and [uv](https://docs.astral.sh/uv/)
- Docker
- Google Cloud SDK
- Terraform
- GCP project with BigQuery and GCS enabled

## Setup

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

3. Create a `secret.json` file with your Google Cloud credentials from a Service Account and put it in the root of the project.

4. Configure environment variables:

```sh
cp env.example .env
# Edit .env with your values
```

See [TESTING.md](TESTING.md) for the full list of environment variables.

5. Configure your Google Cloud SDK:

```sh
gcloud init
```

6. Deploy infrastructure with Terraform:

```sh
cd terraform
terraform init
terraform plan    # review changes
terraform apply   # deploy
```

7. Run ingestion:

```sh
source .env
python -m ingest --source all
```

8. For Docker-based runs:

```sh
docker build -f Dockerfile.ingest -t ingest:local .
docker run --env-file .env ingest:local --source all
```
