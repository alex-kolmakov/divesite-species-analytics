output "bucket_name" {
  value = google_storage_bucket.data.name
}

output "ingestion_job_name" {
  value = google_cloud_run_v2_job.ingestion.name
}

output "enrichment_job_name" {
  value = google_cloud_run_v2_job.enrichment.name
}

output "service_account_email" {
  value = google_service_account.ingestion.email
}

output "registry_url" {
  value = local.registry_url
}
