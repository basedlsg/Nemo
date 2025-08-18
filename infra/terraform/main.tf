provider "google" {
  project = var.project_id
  region  = var.region
}

# Artifact Registry for container images
resource "google_artifact_registry_repository" "gaea" {
  location      = var.region
  repository_id = "gaea"
  format        = "DOCKER"
  description   = "GAEA Energy Assistant container registry"
}

# GKE Autopilot cluster for microservices
resource "google_container_cluster" "gaea" {
  name     = "gaea-autopilot"
  location = var.region
  
  enable_autopilot = true
  
  # Network configuration
  network    = "default"
  subnetwork = "default"
  
  # Workload Identity for secure secret access
  workload_identity_config {
    workload_pool = "${var.project_id}.svc.id.goog"
  }
}

# AlloyDB cluster for vector database
resource "google_alloydb_cluster" "gaea" {
  cluster_id   = "gaea-cluster"
  location     = var.region
  network      = data.google_compute_network.default.id
  
  initial_user {
    user     = "gaea_admin"
    password = var.db_password
  }
  
  database_version = "POSTGRES_15"
  
  backup_policy {
    location = var.region
    backup_retention_count = 7
  }
}

resource "google_alloydb_instance" "gaea_primary" {
  cluster       = google_alloydb_cluster.gaea.name
  instance_id   = "gaea-primary"
  instance_type = "PRIMARY"
  
  machine_config {
    cpu_count = 2
  }
  
  database_flags = {
    "shared_preload_libraries" = "vector"
  }
}

# Get default network
data "google_compute_network" "default" {
  name = "default"
}

# Secret Manager secrets
resource "google_secret_manager_secret" "database_url" {
  secret_id = "DATABASE_URL"
  replication {
    auto {}
  }
}

resource "google_secret_manager_secret" "pplx_api_key" {
  secret_id = "PPLX_API_KEY"
  replication {
    auto {}
  }
}

resource "google_secret_manager_secret" "google_api_key" {
  secret_id = "GOOGLE_API_KEY"
  replication {
    auto {}
  }
}

resource "google_secret_manager_secret" "google_cse_id" {
  secret_id = "GOOGLE_CSE_ID"
  replication {
    auto {}
  }
}

# GCS buckets for data storage
resource "google_storage_bucket" "snapshots" {
  name          = "${var.project_id}-gaea-snapshots"
  location      = var.region
  force_destroy = true
  
  versioning {
    enabled = true
  }
  
  lifecycle_rule {
    condition {
      age = 90
    }
    action {
      type = "Delete"
    }
  }
}

resource "google_storage_bucket" "parsed" {
  name          = "${var.project_id}-gaea-parsed"
  location      = var.region
  force_destroy = true
}

resource "google_storage_bucket" "normalized" {
  name          = "${var.project_id}-gaea-normalized"
  location      = var.region
  force_destroy = true
}

resource "google_storage_bucket" "registry" {
  name          = "${var.project_id}-gaea-registry"
  location      = var.region
  force_destroy = true
}

# Pub/Sub topics for async processing
resource "google_pubsub_topic" "discover" {
  name = "gaea-discover"
}

resource "google_pubsub_topic" "verify" {
  name = "gaea-verify"
}

resource "google_pubsub_topic" "ingest" {
  name = "gaea-ingest"
}

resource "google_pubsub_topic" "embed" {
  name = "gaea-embed"
}

# Service accounts
resource "google_service_account" "gaea_services" {
  account_id   = "gaea-services"
  display_name = "GAEA Services Account"
  description  = "Service account for GAEA microservices"
}

# IAM bindings for service account
resource "google_project_iam_member" "gaea_services_storage" {
  project = var.project_id
  role    = "roles/storage.admin"
  member  = "serviceAccount:${google_service_account.gaea_services.email}"
}

resource "google_project_iam_member" "gaea_services_pubsub" {
  project = var.project_id
  role    = "roles/pubsub.editor"
  member  = "serviceAccount:${google_service_account.gaea_services.email}"
}

resource "google_project_iam_member" "gaea_services_alloydb" {
  project = var.project_id
  role    = "roles/alloydb.client"
  member  = "serviceAccount:${google_service_account.gaea_services.email}"
}

# Secret Manager access
resource "google_secret_manager_secret_iam_member" "database_url_access" {
  secret_id = google_secret_manager_secret.database_url.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.gaea_services.email}"
}

resource "google_secret_manager_secret_iam_member" "pplx_access" {
  secret_id = google_secret_manager_secret.pplx_api_key.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.gaea_services.email}"
}

resource "google_secret_manager_secret_iam_member" "google_api_access" {
  secret_id = google_secret_manager_secret.google_api_key.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.gaea_services.email}"
}

resource "google_secret_manager_secret_iam_member" "google_cse_access" {
  secret_id = google_secret_manager_secret.google_cse_id.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.gaea_services.email}"
}

# Outputs
output "alloydb_ip" {
  value = google_alloydb_instance.gaea_primary.ip_address
}

output "artifact_registry_url" {
  value = "${var.region}-docker.pkg.dev/${var.project_id}/gaea"
}

output "gke_cluster_name" {
  value = google_container_cluster.gaea.name
}

output "service_account_email" {
  value = google_service_account.gaea_services.email
}