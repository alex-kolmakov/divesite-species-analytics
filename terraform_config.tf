provider "google" {
    credentials = file("<PATH_TO_YOUR_SERVICE_ACCOUNT_KEY>")
    project     = "<YOUR_PROJECT_ID>"
    region      = "us-central1"
  }
  
  resource "google_compute_instance" "default" {
    name         = "terraform-instance"
    machine_type = "n1-standard-1"
    zone         = "us-central1-a"
  
    boot_disk {
      initialize_params {
        image = "debian-cloud/debian-9"
      }
    }
  
    network_interface {
      network = "default"
  
      access_config {
        // Include this section to give the VM an external IP
      }
    }
  
    metadata_startup_script = "sudo apt-get update && sudo apt-get install -y git && git clone <YOUR_REPO_URL> && cd <YOUR_REPO_DIR> && pip install -r requirements.txt"
  }
  
  resource "google_storage_bucket" "bucket" {
    name     = "<YOUR_BUCKET_NAME>"
    location = "US"
  }
  
  resource "null_resource" "download_data" {
    provisioner "local-exec" {
      command = "gsutil cp <DATA_URL> gs://${google_storage_bucket.bucket.name}/data"
    }
  }
  
  resource "google_dataproc_cluster" "cluster" {
    name   = "<YOUR_CLUSTER_NAME>"
    region = "us-central1"
  
    cluster_config {
      master_config {
        num_instances = 1
        machine_type  = "n1-standard-1"
      }
      worker_config {
        num_instances = 2
        machine_type  = "n1-standard-1"
      }
    }
  }
  
  resource "google_dataproc_job" "pyspark_job" {
    region   = "us-central1"
    placement {
      cluster_name = google_dataproc_cluster.cluster.name
    }
  
    pyspark_config {
      main_python_file_uri = "gs://${google_storage_bucket.bucket.name}/notebook.py"
      args                 = ["gs://${google_storage_bucket.bucket.name}/output"]
  
      python_file_uris = [
        "gs://${google_storage_bucket.bucket.name}/additional_python_file.py",
      ]
    }
  }
  
  resource "null_resource" "run_dbt" {
    provisioner "local-exec" {
      command = "dbt run --profiles-dir ."
    }
  
    depends_on = [google_dataproc_job.pyspark_job]
  }