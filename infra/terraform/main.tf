# Terraform root module (placeholder)
#
# Future resources:
#   - Object storage for COG archives and vector outputs
#   - Compute (batch/Kubernetes) for tiled OBIA jobs
#   - IAM roles for pipeline workers and API service accounts
#
# Initialize when a cloud provider is selected:
#   cd infra/terraform && terraform init

terraform {
  required_version = ">= 1.5"

  required_providers {
    # Provider block will be added in a future ADR (AWS, Azure, or GCP).
  }
}
