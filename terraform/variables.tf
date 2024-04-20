variable "credentials" {
  description = "My Credentials"
  default     = "secret.json"
}


variable "project" {
  description = "Project"
  default     = "gbif-412615"
}

variable "region" {
  description = "Region"
  default     = "us-central1"
}

variable "location" {
  description = "Project Location"
  default     = "US"
}

variable "bq_dataset_name" {
  description = "My BigQuery Dataset Name"
  default     = "marine_data"
}

variable "gcs_bucket_name" {
  description = "Storage Bucket Name"
  default     = "marine_data_412615"
}

variable "gcs_storage_class" {
  description = "Bucket Storage Class"
  default     = "STANDARD"
}