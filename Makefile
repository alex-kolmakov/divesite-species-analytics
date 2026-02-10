# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║  Marine Species Analytics - Production Deployment                          ║
# ║                                                                            ║
# ║  Usage:  make <target>                                                     ║
# ║  Help:   make help                                                         ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
#
# This Makefile automates the production deployment workflow on GCP:
#
#   1. Provision infrastructure      make infra
#   2. Build & push Docker images    make push
#   3. Execute Cloud Run jobs        make refresh
#
# Or do it all in one shot:          make deploy
#
# Prerequisites:
#   - gcloud CLI authenticated (gcloud auth login)
#   - Docker authenticated with Artifact Registry:
#       gcloud auth configure-docker us-central1-docker.pkg.dev
#   - WoRMS credentials stored in GCP Secret Manager

# ─── Configuration ──────────────────────────────────────────────────────────────
# Defaults match terraform/variables.tf. Override via environment:
#   export PROJECT_ID=my-project && make deploy

PROJECT_ID   ?= gbif-412615
REGION       ?= us-central1
AR_REPO      ?= marine-analytics
REGISTRY     := $(REGION)-docker.pkg.dev/$(PROJECT_ID)/$(AR_REPO)

# ─── Help ───────────────────────────────────────────────────────────────────────

.PHONY: help
help: ## Show this help message
	@echo ""
	@echo "Marine Species Analytics - Production Deployment"
	@echo "================================================"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'
	@echo ""

# ─── Terraform / Infrastructure ─────────────────────────────────────────────────
# Provisions all GCP resources: GCS bucket, BigQuery dataset, Artifact Registry,
# Cloud Run jobs, service account with IAM bindings, and (optionally) Cloud
# Scheduler. Run 'make infra-plan' first to review changes before applying.

.PHONY: infra-init
infra-init: ## Initialize Terraform (downloads providers)
	cd terraform && terraform init

.PHONY: infra-plan
infra-plan: ## Preview infrastructure changes (dry run)
	cd terraform && terraform plan

.PHONY: infra-apply
infra-apply: ## Deploy infrastructure to GCP
	cd terraform && terraform apply

.PHONY: infra
infra: infra-init infra-plan infra-apply ## Full infra deploy (init + plan + apply)

# ─── Build & Push ───────────────────────────────────────────────────────────────
# Builds Docker images and pushes them to Google Artifact Registry.
# The Cloud Run jobs pull the :latest tag from this registry.

.PHONY: push-ingest
push-ingest: ## Build and push ingest image to Artifact Registry
	docker build -f Dockerfile.ingest -t $(REGISTRY)/ingest:latest .
	docker push $(REGISTRY)/ingest:latest

.PHONY: push-enrich
push-enrich: ## Build and push enrich image to Artifact Registry
	docker build -f Dockerfile.enrich -t $(REGISTRY)/enrich:latest .
	docker push $(REGISTRY)/enrich:latest

.PHONY: push
push: push-ingest push-enrich ## Build and push all images

# ─── Run Cloud Jobs ─────────────────────────────────────────────────────────────
# Executes Cloud Run jobs that were created by Terraform. The ingestion job
# downloads all data sources, converts to Parquet, and uploads to GCS. The
# enrichment job queries BigQuery for species missing images/common names
# and fills them from Wikipedia.

.PHONY: run-ingest
run-ingest: ## Execute ingestion Cloud Run job
	gcloud run jobs execute marine-data-ingestion --region $(REGION) --wait

.PHONY: run-enrich
run-enrich: ## Execute enrichment Cloud Run job
	gcloud run jobs execute marine-data-enrichment --region $(REGION) --wait

# ─── Composite Targets ──────────────────────────────────────────────────────────

.PHONY: deploy
deploy: push run-ingest run-enrich ## Full deploy: push images + run both Cloud Run jobs

.PHONY: refresh
refresh: run-ingest run-enrich ## Re-run both Cloud Run jobs (no image rebuild)
