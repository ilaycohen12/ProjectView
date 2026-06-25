# ProjectView — Documentation Log

A living document of every step taken in this project, explained in plain English.
Updated throughout the build.

---

## Infra
> Everything related to AWS infrastructure: VPC, EKS clusters, IAM roles, Terraform/Terragrunt.

### Phase 0 — Bootstrap

#### S3 Bucket for Terraform State
- **What:** Created an S3 bucket to store Terraform state files remotely.
- **Why:** Terraform tracks what it has deployed in a "state file". If we store it locally, it gets lost or causes conflicts. S3 keeps it safe and shared.

#### DynamoDB Table for State Locking
- **What:** Created a DynamoDB table used by Terragrunt to lock the state.
- **Why:** Prevents two Terraform runs from happening at the same time and corrupting the state file.

#### ECR Repository
- **What:** Created an Elastic Container Registry repository.
- **Why:** This is where GitHub Actions will push the Docker image after building it. EKS then pulls from here to deploy.

---

## App
> Everything related to the sample Flask application and its Dockerfile.

---

## Workflow
> Everything related to GitHub Actions CI pipeline.

---

## GitOps
> Everything related to ArgoCD, App of Apps, and deployment promotion flow.

---

## Secrets
> Everything related to External Secrets Operator and AWS Secrets Manager integration.

---

## Bug Fixes
> Issues encountered and how they were resolved.

---
