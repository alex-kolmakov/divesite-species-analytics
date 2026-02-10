#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-gbif-412615}"
REGION="${REGION:-us-central1}"
REPO="${REPO:-marine-analytics}"
REGISTRY="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO}"

echo "==> Configuring Docker for Artifact Registry"
gcloud auth configure-docker "${REGION}-docker.pkg.dev" --quiet

echo "==> Building ingest image"
docker build -f Dockerfile.ingest -t "${REGISTRY}/ingest:latest" .

echo "==> Building enrich image"
docker build -f Dockerfile.enrich -t "${REGISTRY}/enrich:latest" .

echo "==> Pushing ingest image"
docker push "${REGISTRY}/ingest:latest"

echo "==> Pushing enrich image"
docker push "${REGISTRY}/enrich:latest"

echo "==> Done. Images pushed to ${REGISTRY}"
