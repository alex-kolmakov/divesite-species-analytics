# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║  Marine Species Analytics - Makefile                                       ║
# ║                                                                            ║
# ║  Usage:  make <target>                                                     ║
# ║  Help:   make help                                                         ║
# ╚══════════════════════════════════════════════════════════════════════════════╝

# ─── Configuration ──────────────────────────────────────────────────────────────
# These defaults match terraform/variables.tf. Override via environment or .env:
#   export PROJECT_ID=my-project && make deploy

PROJECT_ID   ?= gbif-412615
REGION       ?= us-central1
BUCKET       ?= marine_data_412615
AR_REPO      ?= marine-analytics
REGISTRY     := $(REGION)-docker.pkg.dev/$(PROJECT_ID)/$(AR_REPO)

# ─── Help ───────────────────────────────────────────────────────────────────────

.PHONY: help
help: ## Show this help message
	@echo ""
	@echo "Marine Species Analytics"
	@echo "========================"
	@echo ""
	@echo "Local Development:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; /Local|Setup/ {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "Cloud Deployment:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; /Cloud|Deploy|Push/ {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "CI / Quality:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; /Lint|Format|Type|Check|CI/ {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'
	@echo ""

# ─── Setup ──────────────────────────────────────────────────────────────────────
# First-time project setup. Creates a virtualenv, installs all Python packages,
# copies the env template, and installs pre-commit hooks.

.PHONY: setup
setup: ## [Setup] One-time project setup (venv, deps, env file, pre-commit hooks)
	uv venv .venv
	. .venv/bin/activate && \
		uv pip install -r requirements-ingest.txt \
		               -r requirements-enrich.txt \
		               -r requirements-dev.txt
	@test -f .env || (cp env.example .env && echo "Created .env from template - edit it with your values")
	. .venv/bin/activate && pre-commit install
	@echo ""
	@echo "Setup complete. Activate the venv with:  source .venv/bin/activate"
	@echo "Then edit .env with your GCP project details."

# ─── Local Ingestion ────────────────────────────────────────────────────────────
# Runs the Python ingestion CLI on your local machine.
# Downloads data from external sources, converts to Parquet, and uploads to GCS.
# Requires: .env populated, GCS bucket exists (via 'make infra').
#
# Examples:
#   make ingest                      # all sources
#   make ingest SOURCE=iucn          # single source
#   make ingest SOURCE=iucn,gisd     # multiple sources

SOURCE ?= all

.PHONY: ingest
ingest: ## [Local] Run ingestion locally (SOURCE=all|iucn|gisd|worms|obis|divesites)
	. .venv/bin/activate && set -a && . ./.env && set +a && \
		python -m ingest --source $(SOURCE)

# ─── Local Enrichment ──────────────────────────────────────────────────────────
# Runs the Wikipedia enrichment pipeline. Queries BigQuery for species without
# images/common names, fetches from Wikipedia API, and writes results back.
# Requires: .env populated, BigQuery dataset with species data.

.PHONY: enrich
enrich: ## [Local] Run Wikipedia enrichment locally
	. .venv/bin/activate && set -a && . ./.env && set +a && \
		python -m enrich

# ─── Docker ─────────────────────────────────────────────────────────────────────
# Build container images locally. Useful for testing before pushing to cloud.

.PHONY: docker-build
docker-build: ## [Local] Build both Docker images locally
	docker build -f Dockerfile.ingest -t ingest:local .
	docker build -f Dockerfile.enrich -t enrich:local .

.PHONY: docker-run-ingest
docker-run-ingest: ## [Local] Run ingestion in Docker (SOURCE=all|iucn|...)
	docker run --env-file .env \
		-v $(shell pwd)/secret.json:/app/secret.json:ro \
		-e GOOGLE_APPLICATION_CREDENTIALS=/app/secret.json \
		ingest:local --source $(SOURCE)

.PHONY: docker-run-enrich
docker-run-enrich: ## [Local] Run enrichment in Docker
	docker run --env-file .env \
		-v $(shell pwd)/secret.json:/app/secret.json:ro \
		-e GOOGLE_APPLICATION_CREDENTIALS=/app/secret.json \
		enrich:local

# ─── Terraform / Infrastructure ─────────────────────────────────────────────────
# Provisions all GCP resources: GCS bucket, BigQuery dataset, Artifact Registry,
# Cloud Run jobs, service account with IAM bindings, and (optionally) Cloud Scheduler.
# Run 'make infra-plan' first to review changes before applying.

.PHONY: infra-init
infra-init: ## [Cloud] Initialize Terraform (downloads providers)
	cd terraform && terraform init

.PHONY: infra-plan
infra-plan: ## [Cloud] Preview infrastructure changes (dry run)
	cd terraform && terraform plan

.PHONY: infra-apply
infra-apply: ## [Cloud] Deploy infrastructure to GCP
	cd terraform && terraform apply

.PHONY: infra
infra: infra-init infra-plan infra-apply ## [Cloud] Full infra deploy (init + plan + apply)

# ─── Cloud Deploy ───────────────────────────────────────────────────────────────
# Build Docker images, push them to Artifact Registry, then execute the Cloud Run
# jobs. This is the production deployment path.
#
# Prerequisites:
#   1. 'make infra' completed (GCP resources exist)
#   2. Docker authenticated: gcloud auth configure-docker $(REGION)-docker.pkg.dev
#   3. Secrets populated in GCP Secret Manager (WoRMS credentials)

.PHONY: push-ingest
push-ingest: ## [Deploy] Build and push ingest image to Artifact Registry
	docker build -f Dockerfile.ingest -t $(REGISTRY)/ingest:latest .
	docker push $(REGISTRY)/ingest:latest

.PHONY: push-enrich
push-enrich: ## [Deploy] Build and push enrich image to Artifact Registry
	docker build -f Dockerfile.enrich -t $(REGISTRY)/enrich:latest .
	docker push $(REGISTRY)/enrich:latest

.PHONY: push
push: push-ingest push-enrich ## [Deploy] Build and push all images

.PHONY: run-cloud-ingest
run-cloud-ingest: ## [Cloud] Execute ingestion Cloud Run job
	gcloud run jobs execute marine-data-ingestion --region $(REGION) --wait

.PHONY: run-cloud-enrich
run-cloud-enrich: ## [Cloud] Execute enrichment Cloud Run job
	gcloud run jobs execute marine-data-enrichment --region $(REGION) --wait

# ─── Full Deploy & Refresh ──────────────────────────────────────────────────────
# End-to-end: build images, push to registry, run both Cloud Run jobs.

.PHONY: deploy
deploy: push run-cloud-ingest run-cloud-enrich ## [Deploy] Full deploy: push images + run both Cloud Run jobs

.PHONY: refresh
refresh: run-cloud-ingest run-cloud-enrich ## [Cloud] Re-run both Cloud Run jobs (no image rebuild)

# ─── CI / Quality ───────────────────────────────────────────────────────────────
# These match exactly what runs in GitHub Actions (.github/workflows/ci.yml).

.PHONY: lint
lint: ## [CI] Run ruff linter on ingest/ and enrich/
	ruff check ingest/ enrich/

.PHONY: format-check
format-check: ## [CI] Check code formatting with ruff
	ruff format --check ingest/ enrich/

.PHONY: format
format: ## [CI] Auto-format code with ruff
	ruff format ingest/ enrich/
	ruff check --fix ingest/ enrich/

.PHONY: typecheck
typecheck: ## [CI] Run pyrefly type checker
	pyrefly check

.PHONY: check
check: lint format-check typecheck ## [CI] Run all checks (lint + format + typecheck)

.PHONY: tf-validate
tf-validate: ## [CI] Validate Terraform configuration
	cd terraform && terraform fmt -check -recursive && terraform init -backend=false && terraform validate
