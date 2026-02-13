# Marine Species Analytics — Makefile
#
# Local Development:
#   make update-data  Enrich + rebuild dbt + export + download fresh data
#   make app          Run app locally in Docker
#
# Cloud Deployment:
#   make app-deploy   Build, push, deploy app to Cloud Run
#   make app-destroy  Remove Cloud Run app (keeps all data)
#
# Data Pipeline (Cloud Run):
#   make deploy       Build images + run full pipeline
#   make refresh      Re-run pipeline without rebuilding images
#
# Infrastructure:
#   make setup        One-time GCP setup
#   make infra        Apply Terraform changes
#   make help         Show all targets
#
#   Add DEV=1 for development mode (sampled data, smaller batches):
#     make deploy DEV=1
#     make refresh DEV=1

# ─── Configuration ────────────────────────────────────────────────────────────

PROJECT_ID   ?= gbif-412615
REGION       ?= us-central1
BUCKET       ?= marine_data_412615
AR_REPO      ?= marine-analytics
REGISTRY     := $(REGION)-docker.pkg.dev/$(PROJECT_ID)/$(AR_REPO)
SERVICE_KEY  ?= secret.json
INGEST_JOB   := marine-data-ingestion
PLATFORM     := linux/amd64
APP_SERVICE  := marine-species-explorer

export GOOGLE_APPLICATION_CREDENTIALS ?= $(CURDIR)/$(SERVICE_KEY)

# Sources to ingest — each runs as a parallel Cloud Run execution
INGEST_SOURCES := iucn gisd worms divesites obis

# BigQuery export settings
BQ_DATASET   ?= marine_data
EXPORT_PREFIX := app-export
APP_TABLES   := species_divesite_summary divesite_species_detail divesite_summary
LOCAL_DATA    := app/backend/data

APP_IMAGE := $(REGISTRY)/app:latest

ifdef DEV
  TF_DEV_FLAG := -var="development=true"
else
  TF_DEV_FLAG :=
endif

# ─── Help ─────────────────────────────────────────────────────────────────────

.PHONY: help
help: ## Show all targets
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "  Add DEV=1 for development mode (sampled data, smaller batches)"
	@echo ""

# ─── Setup (one-time) ────────────────────────────────────────────────────────

.PHONY: setup
setup: ## One-time: authenticate, enable GCP APIs, build images, deploy infrastructure
	gcloud auth activate-service-account --key-file=$(SERVICE_KEY)
	gcloud config set project $(PROJECT_ID)
	gcloud auth configure-docker $(REGION)-docker.pkg.dev
	gcloud services enable serviceusage.googleapis.com --project $(PROJECT_ID)
	gcloud services enable secretmanager.googleapis.com --project $(PROJECT_ID)
	gcloud services enable run.googleapis.com --project $(PROJECT_ID)
	gcloud services enable artifactregistry.googleapis.com --project $(PROJECT_ID)
	gcloud services enable cloudscheduler.googleapis.com --project $(PROJECT_ID)
	gcloud services enable bigquery.googleapis.com --project $(PROJECT_ID)
	gcloud services enable iam.googleapis.com --project $(PROJECT_ID)
	cd terraform && terraform init
	cd terraform && terraform import google_storage_bucket.data $(PROJECT_ID)/$(BUCKET) 2>/dev/null || true
	cd terraform && terraform import google_bigquery_dataset.marine_data projects/$(PROJECT_ID)/datasets/marine_data 2>/dev/null || true
	@echo "\n→ Building and pushing Docker images (required before Cloud Run jobs)..."
	docker build --platform $(PLATFORM) -f Dockerfile.ingest -t $(REGISTRY)/ingest:latest .
	docker build --platform $(PLATFORM) -f Dockerfile.dbt    -t $(REGISTRY)/dbt:latest .
	docker build --platform $(PLATFORM) -f Dockerfile.enrich -t $(REGISTRY)/enrich:latest .
	docker build --platform $(PLATFORM) -t $(APP_IMAGE) .
	docker push $(REGISTRY)/ingest:latest
	docker push $(REGISTRY)/dbt:latest
	docker push $(REGISTRY)/enrich:latest
	docker push $(APP_IMAGE)
	@echo "\n→ Applying Terraform..."
	cd terraform && terraform apply -auto-approve $(TF_DEV_FLAG)
	@echo "\n✓ Setup complete. Next: make deploy"

# ─── Local Development ───────────────────────────────────────────────────────

.PHONY: update-data
update-data: ## Enrich + rebuild dbt + export + download fresh data locally
	@echo "→ Step 1/4: Enriching species data..."
	python -m enrich --new-only
	@echo "→ Step 2/4: Rebuilding dbt coral models..."
	cd dbt && dbt run --select species_divesite_summary divesite_species_detail divesite_summary
	@echo "→ Step 3/4: Exporting tables to GCS..."
	@for table in $(APP_TABLES); do \
		echo "  → $$table"; \
		bq extract --destination_format=PARQUET \
			'$(PROJECT_ID):$(BQ_DATASET).'"$$table" \
			'gs://$(BUCKET)/$(EXPORT_PREFIX)/'"$$table"'.parquet'; \
	done
	@echo "→ Step 4/4: Downloading parquets to $(LOCAL_DATA)/..."
	@mkdir -p $(LOCAL_DATA)
	@for table in $(APP_TABLES); do \
		echo "  → $$table.parquet"; \
		gsutil cp 'gs://$(BUCKET)/$(EXPORT_PREFIX)/'"$$table"'.parquet' $(LOCAL_DATA)/; \
	done
	@echo "✓ Data update complete. Run: make app"

.PHONY: app
app: ## Run app locally in Docker (uses local parquet data)
	docker build -t marine-species-app .
	docker run --rm -p 8080:8080 \
		-v $(CURDIR)/$(LOCAL_DATA):/app/data \
		-e LOCAL_DATA_DIR=/app/data \
		marine-species-app

# ─── Cloud Deployment (App) ──────────────────────────────────────────────────

.PHONY: app-deploy
app-deploy: ## Build, push, deploy app to Cloud Run
	docker build --platform $(PLATFORM) -t $(APP_IMAGE) .
	docker push $(APP_IMAGE)
	cd terraform && terraform apply -auto-approve $(TF_DEV_FLAG)
	gcloud run services update $(APP_SERVICE) \
		--region $(REGION) \
		--image $(APP_IMAGE)
	@echo "✓ App deployed. URL:"
	@gcloud run services describe $(APP_SERVICE) --region $(REGION) --format='value(status.url)'

.PHONY: app-destroy
app-destroy: ## Remove Cloud Run app (keeps all data)
	gcloud run services delete $(APP_SERVICE) --region $(REGION) --quiet
	@echo "✓ App removed. Data in GCS and BigQuery is preserved."
	@echo "  Run 'make app-deploy' to recreate."

# ─── Data Pipeline (Cloud Run) ───────────────────────────────────────────────
#
#   1. Ingest  — all sources run in PARALLEL (same image, different --args)
#   2. dbt     — waits for all ingestion to finish, then builds models
#   3. Enrich  — waits for dbt, then enriches species table
#
#   deploy  = build images + push + run pipeline
#   refresh = re-run pipeline without rebuilding

.PHONY: deploy
deploy: ## Build images, push to Artifact Registry, and run full pipeline
	docker build --platform $(PLATFORM) -f Dockerfile.ingest -t $(REGISTRY)/ingest:latest .
	docker build --platform $(PLATFORM) -f Dockerfile.dbt    -t $(REGISTRY)/dbt:latest .
	docker build --platform $(PLATFORM) -f Dockerfile.enrich -t $(REGISTRY)/enrich:latest .
	docker push $(REGISTRY)/ingest:latest
	docker push $(REGISTRY)/dbt:latest
	docker push $(REGISTRY)/enrich:latest
	@$(MAKE) --no-print-directory run-pipeline

.PHONY: refresh
refresh: run-pipeline ## Re-run pipeline without rebuilding images

.PHONY: run-pipeline
run-pipeline:
	@echo "→ Step 1/3: Ingesting sources in parallel..."
	@$(MAKE) --no-print-directory run-ingest
	@echo "→ Step 2/3: Running dbt models..."
	gcloud run jobs execute marine-data-dbt --region $(REGION) --wait
	@echo "→ Step 3/3: Enriching species data..."
	gcloud run jobs execute marine-data-enrichment --region $(REGION) --wait
	@echo "\n✓ Pipeline complete."

# Launch each source as a separate execution, wait for all to finish.
# gcloud --args overrides the Dockerfile CMD, so each gets --source <name>.
.PHONY: run-ingest
run-ingest:
	@PIDS=""; SRCS=""; \
	for src in $(INGEST_SOURCES); do \
		echo "  → Launching ingest: $$src"; \
		gcloud run jobs execute $(INGEST_JOB) \
			--region $(REGION) \
			--args="--source,$$src" \
			--wait & \
		PIDS="$$PIDS $$!"; SRCS="$$SRCS $$src"; \
	done; \
	echo "  → Waiting for all ingest jobs to complete..."; \
	FAILED=""; \
	set -- $$SRCS; \
	for pid in $$PIDS; do \
		if ! wait $$pid; then FAILED="$$FAILED $$1"; fi; \
		shift; \
	done; \
	if [ -n "$$FAILED" ]; then \
		echo "⚠ Failed sources:$$FAILED (continuing with existing data)"; \
	else \
		echo "  ✓ All ingest jobs complete."; \
	fi

# ─── Infrastructure ──────────────────────────────────────────────────────────

.PHONY: infra
infra: ## Apply Terraform changes (after editing terraform/)
	cd terraform && terraform init -input=false && terraform apply -auto-approve $(TF_DEV_FLAG)
