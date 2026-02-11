variable "project_id" {
  description = "GCP project ID"
  type        = string
  default     = "gbif-412615"
}

variable "region" {
  description = "GCP region"
  type        = string
  default     = "us-central1"
}

variable "bucket_name" {
  description = "GCS bucket for raw data"
  type        = string
  default     = "marine_data_412615"
}

variable "bigquery_dataset" {
  description = "BigQuery dataset name"
  type        = string
  default     = "marine_data"
}

variable "artifact_registry_repo" {
  description = "Artifact Registry repository name"
  type        = string
  default     = "marine-analytics"
}

variable "enable_scheduler" {
  description = "Enable Cloud Scheduler for periodic ingestion"
  type        = bool
  default     = false
}

variable "development" {
  description = "Enable development mode (sampled data in dbt, smaller enrich batches)"
  type        = bool
  default     = false
}
