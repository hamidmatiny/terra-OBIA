# Infrastructure (Placeholders)

Infrastructure-as-code and container definitions for deploying Terra OBIA.

## Layout

| Path | Purpose |
|------|---------|
| `docker/` | Container images for API, pipeline workers, and future web dashboard |
| `terraform/` | Cloud resources (object storage, compute, networking, IAM) |

## Status

Scaffolding only. Production deployment targets (AWS, Azure, GCP, or on-prem)
will be documented in a future ADR once customer hosting requirements are
finalized.

## Local development

For now, run services directly via Poetry (see root `README.md`). Docker
Compose will be added when the pipeline worker and API are ready for
containerized deployment.
