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
  
    }
  
    metadata_startup_script = "sudo apt-get update && sudo apt-get install -y git && git clone <YOUR_REPO_URL> && cd <YOUR_REPO_DIR> && pip install -r requirements.txt"
  }
  
  resource "google_storage_bucket" "bucket" {
    name     = "<YOUR_BUCKET_NAME>"
    location = "US"
  }
  
