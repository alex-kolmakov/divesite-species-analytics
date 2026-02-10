# ─── GCS Bucket ───────────────────────────────────────────────────────────────

resource "google_storage_bucket" "data" {
  name                        = var.bucket_name
  location                    = "US"
  storage_class               = "STANDARD"
  uniform_bucket_level_access = true

  versioning {
    enabled = true
  }

  lifecycle_rule {
    condition {
      num_newer_versions = 3
    }
    action {
      type = "Delete"
    }
  }
}

# ─── BigQuery Dataset ─────────────────────────────────────────────────────────

resource "google_bigquery_dataset" "marine_data" {
  dataset_id = var.bigquery_dataset
  location   = "US"
}

# ─── Artifact Registry ───────────────────────────────────────────────────────

resource "google_artifact_registry_repository" "images" {
  location      = var.region
  repository_id = var.artifact_registry_repo
  format        = "DOCKER"
}

# ─── Service Account ─────────────────────────────────────────────────────────

resource "google_service_account" "ingestion" {
  account_id   = "marine-ingestion-sa"
  display_name = "Marine Data Ingestion"
}

# IAM: GCS access
resource "google_storage_bucket_iam_member" "ingestion_gcs" {
  bucket = google_storage_bucket.data.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.ingestion.email}"
}

# IAM: BigQuery data editor
resource "google_project_iam_member" "ingestion_bq_editor" {
  project = var.project_id
  role    = "roles/bigquery.dataEditor"
  member  = "serviceAccount:${google_service_account.ingestion.email}"
}

# IAM: BigQuery job user
resource "google_project_iam_member" "ingestion_bq_job" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.ingestion.email}"
}

# IAM: Artifact Registry reader
resource "google_project_iam_member" "ingestion_ar_reader" {
  project = var.project_id
  role    = "roles/artifactregistry.reader"
  member  = "serviceAccount:${google_service_account.ingestion.email}"
}

# IAM: Secret Manager accessor
resource "google_project_iam_member" "ingestion_secrets" {
  project = var.project_id
  role    = "roles/secretmanager.secretAccessor"
  member  = "serviceAccount:${google_service_account.ingestion.email}"
}

# ─── Secrets ──────────────────────────────────────────────────────────────────

resource "google_secret_manager_secret" "worms_login" {
  secret_id = "worms-login"

  replication {
    auto {}
  }
}

resource "google_secret_manager_secret" "worms_password" {
  secret_id = "worms-password"

  replication {
    auto {}
  }
}

# ─── Cloud Run Job: Ingestion ────────────────────────────────────────────────

locals {
  registry_url = "${var.region}-docker.pkg.dev/${var.project_id}/${var.artifact_registry_repo}"
}

resource "google_cloud_run_v2_job" "ingestion" {
  name     = "marine-data-ingestion"
  location = var.region

  template {
    template {
      containers {
        image = "${local.registry_url}/ingest:latest"

        resources {
          limits = {
            cpu    = "2"
            memory = "8Gi"
          }
        }

        env {
          name  = "GCS_BUCKET"
          value = var.bucket_name
        }
        env {
          name  = "PROJECT_ID"
          value = var.project_id
        }
        env {
          name  = "IUCN_REDLIST_URL"
          value = "https://hosted-datasets.gbif.org/datasets/iucn_2024-1.zip"
        }
        env {
          name  = "GISD_URL"
          value = "https://hosted-datasets.gbif.org/datasets/gisd_2011-11-20.zip"
        }
        env {
          name  = "WORMS_URL_TEMPLATE"
          value = "https://www.marinespecies.org/dwca/WoRMS_DwC-A_{full_date}.zip"
        }
        env {
          name  = "BASE_PADI_GUIDE_URL"
          value = "https://travel.padi.com/api/v2/travel/dive-guide/world/all/dive-sites"
        }
        env {
          name  = "BASE_PADI_MAP_URL"
          value = "https://travel.padi.com/api/v2/travel/dsl/dive-sites/map/"
        }
        env {
          name = "WORMS_LOGIN"
          value_source {
            secret_key_ref {
              secret  = google_secret_manager_secret.worms_login.secret_id
              version = "latest"
            }
          }
        }
        env {
          name = "WORMS_PASSWORD"
          value_source {
            secret_key_ref {
              secret  = google_secret_manager_secret.worms_password.secret_id
              version = "latest"
            }
          }
        }
      }

      timeout     = "3600s"
      max_retries = 1

      service_account = google_service_account.ingestion.email
    }
  }

  lifecycle {
    ignore_changes = [
      template[0].template[0].containers[0].image,
    ]
  }
}

# ─── Cloud Run Job: Enrichment ───────────────────────────────────────────────

resource "google_cloud_run_v2_job" "enrichment" {
  name     = "marine-data-enrichment"
  location = var.region

  template {
    template {
      containers {
        image = "${local.registry_url}/enrich:latest"

        resources {
          limits = {
            cpu    = "1"
            memory = "2Gi"
          }
        }

        env {
          name  = "PROJECT_ID"
          value = var.project_id
        }
        env {
          name  = "BIGQUERY_DATASET"
          value = var.bigquery_dataset
        }
      }

      timeout     = "1800s"
      max_retries = 1

      service_account = google_service_account.ingestion.email
    }
  }

  lifecycle {
    ignore_changes = [
      template[0].template[0].containers[0].image,
    ]
  }
}

# ─── Cloud Scheduler (optional) ──────────────────────────────────────────────

resource "google_project_iam_member" "ingestion_run_invoker" {
  count   = var.enable_scheduler ? 1 : 0
  project = var.project_id
  role    = "roles/run.invoker"
  member  = "serviceAccount:${google_service_account.ingestion.email}"
}

resource "google_cloud_scheduler_job" "weekly_ingestion" {
  count     = var.enable_scheduler ? 1 : 0
  name      = "marine-data-weekly-refresh"
  region    = var.region
  schedule  = "0 2 * * 0" # Sunday 2 AM
  time_zone = "UTC"

  http_target {
    http_method = "POST"
    uri         = "https://${var.region}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${var.project_id}/jobs/marine-data-ingestion:run"

    oauth_token {
      service_account_email = google_service_account.ingestion.email
    }
  }
}
