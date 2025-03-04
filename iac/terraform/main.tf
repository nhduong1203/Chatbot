terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "4.80.0" # Provider version
    }
  }
  required_version = "1.9.2" # Terraform version
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# Define GKE Cluster
resource "google_container_cluster" "primary" {
  name                     = "${var.project_id}-gke"
  location                 = var.region
  remove_default_node_pool = true
  initial_node_count       = 1
}

# Node Pool for System Services
resource "google_container_node_pool" "system_services" {
  name       = "${var.project_id}-sys-svc-pool"
  location   = var.region
  cluster    = google_container_cluster.primary.name
  node_count = 1

  node_config {
    machine_type = "e2-standard-2"
    disk_size_gb = 40
    preemptible  = false
    image_type   = "COS_CONTAINERD"
    labels = {
      workload = "system-services"
    }
  }

  autoscaling {
    min_node_count = 1
    max_node_count = 3
  }
}

# Node Pool for Cassandra
resource "google_container_node_pool" "cassandra" {
  name       = "${var.project_id}-cassandra-pool"
  location   = var.region
  cluster    = google_container_cluster.primary.name
  node_count = 1

  node_config {
    machine_type = "e2-highmem-4"
    disk_size_gb = 40 # Reduced from 200GB
    preemptible  = false
    image_type   = "COS_CONTAINERD"
    labels = {
      workload = "cassandra"
    }
  }

  autoscaling {
    min_node_count = 1
    max_node_count = 2
  }
}

# Node Pool for Backend Doc Management
resource "google_container_node_pool" "backend_doc" {
  name       = "${var.project_id}-doc-pool"
  location   = var.region
  cluster    = google_container_cluster.primary.name
  node_count = 1

  node_config {
    machine_type = "e2-standard-4" # Optimized for balanced workloads
    disk_size_gb = 40
    preemptible  = false
    image_type   = "COS_CONTAINERD"
    labels = {
      workload = "backend-doc"
    }
  }

  autoscaling {
    min_node_count = 1
    max_node_count = 2
  }
}

# Node Pool for Backend Chat
resource "google_container_node_pool" "backend_chat" {
  name       = "${var.project_id}-chat-pool"
  location   = var.region
  cluster    = google_container_cluster.primary.name
  node_count = 1

  node_config {
    machine_type = "e2-standard-4" # Optimized for balanced workloads
    disk_size_gb = 40
    preemptible  = false
    image_type   = "COS_CONTAINERD"
    labels = {
      workload = "backend-chat"
    }
  }

  autoscaling {
    min_node_count = 1
    max_node_count = 2
  }
}

# Node Pool for Frontend and NGINX
resource "google_container_node_pool" "frontend" {
  name       = "${var.project_id}-fe-pool"
  location   = var.region
  cluster    = google_container_cluster.primary.name
  node_count = 1

  node_config {
    machine_type = "e2-medium"
    disk_size_gb = 40
    preemptible  = true
    image_type   = "COS_CONTAINERD"
    labels = {
      workload = "frontend"
    }
  }

  autoscaling {
    min_node_count = 1
    max_node_count = 1
  }
}

# Outputs
output "kubernetes_cluster_name" {
  value = google_container_cluster.primary.name
}

output "kubernetes_cluster_endpoint" {
  value = google_container_cluster.primary.endpoint
}

output "kubernetes_cluster_ca_certificate" {
  value = google_container_cluster.primary.master_auth.0.cluster_ca_certificate
}
