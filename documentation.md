# ProjectView — Documentation Log

A living document of every step taken in this project, explained in plain English.
Updated throughout the build.

---

## Infra
> Everything related to AWS infrastructure: VPC, EKS clusters, IAM roles, Terraform/Terragrunt.

### Phase 0 — Bootstrap

#### Tool Installation
- **What:** Installed git, AWS CLI, kubectl, terraform, terragrunt, helm on Windows.
- **Why:** These are the core tools for the entire project. Without them nothing can be built or deployed.
- **How:** git/aws/kubectl were already present. terraform and helm installed via `winget`, then copied to `C:\Windows\System32` so they're available in any terminal. terragrunt downloaded directly from the official GitHub release as a single `.exe` and placed in `System32`.
- **Tools and their roles:**
  - `git` — version control, also used by GitHub Actions to tag Docker images by git SHA
  - `aws cli` — talks to your AWS account from the terminal
  - `kubectl` — CLI for Kubernetes, used to inspect clusters, pods, ArgoCD status
  - `terraform` — the IaC tool that provisions AWS resources from `.tf` files
  - `terragrunt` — thin wrapper around Terraform that removes config repetition between dev and prod environments
  - `helm` — Kubernetes package manager, used to deploy the app chart with per-environment values

#### AWS CLI Configuration
- **What:** Ran `aws configure` to authenticate the CLI with AWS credentials.
- **Why:** Every AWS command (creating S3, DynamoDB, ECR, EKS) needs to know which account to talk to and with what permissions.
- **Best practice applied:** Created a dedicated IAM user (`admin`) instead of using root access keys. Root keys have unlimited permissions and can never be restricted — if leaked, the entire AWS account is compromised. An IAM user can be deleted or have permissions revoked at any time.
- **Verified with:** `aws sts get-caller-identity` — returned Account ID `086241318869`, user `admin`.

#### S3 Bucket for Terraform State
- **What:** Created S3 bucket `projectview-tf-state-086241318869` in `us-east-1`. Enabled versioning on it.
- **Command:** `aws s3api create-bucket --bucket projectview-tf-state-086241318869 --region us-east-1`
- **Why:** Terraform tracks everything it has deployed in a state file (`terraform.tfstate`). Storing it in S3 means it's safe, shared, and never lost. Without remote state, the file lives only on your laptop — if you lose it, Terraform loses track of your entire infrastructure.
- **Why versioning:** If a state file gets corrupted during a failed apply, S3 versioning lets you restore the previous good version. Without it, a corrupted state = you lose track of everything Terraform manages.
- **Bucket name includes account ID** because S3 bucket names must be globally unique across all AWS accounts worldwide.

#### State Locking — Decision & Change
- **Original plan:** Create a DynamoDB table (`projectview-tf-locks`) to handle Terraform state locking — the traditional pattern used by most Terraform projects.
- **What we did:** Created the DynamoDB table, then deleted it after deciding to use S3 native locking instead.
- **Why we changed:** Terraform 1.10+ introduced `use_lockfile = true` — a built-in S3 locking option that creates a `.tflock` file directly in the S3 bucket next to the state file. This removes the need for a separate AWS resource entirely.
- **How it works:** When a Terraform run starts, it creates `dev/vpc/terraform.tfstate.tflock` in S3. Any other run that tries to start sees that file and waits. When the run finishes, the lockfile is deleted automatically.
- **Where `use_lockfile = true` lives:** In the root `terragrunt.hcl` backend config — not on the S3 bucket itself. The S3 bucket needs no changes.
- **Commands:**
  - Created: `aws dynamodb create-table --table-name projectview-tf-locks ...`
  - Deleted: `aws dynamodb delete-table --table-name projectview-tf-locks --region us-east-1`

#### ECR Repository
- **What:** Created ECR repository `projectview-app` in `us-east-1`.
- **Command:** `aws ecr create-repository --repository-name projectview-app --region us-east-1`
- **URI:** `086241318869.dkr.ecr.us-east-1.amazonaws.com/projectview-app`
- **Why:** ECR is AWS's private Docker registry — the bridge between CI and the cluster. GitHub Actions builds the Flask app into a Docker image and pushes it here tagged by git SHA (e.g. `projectview-app:a3f9c12`). EKS pulls from here when deploying.

### Phase 1 — Infrastructure (Terragrunt)

#### Step 1 — Folder structure in ProjectView-infra
- **What:** Created the full folder tree inside `ProjectView-infra/infra/`: `modules/` (vpc, eks, iam, addons) and `environments/` (dev + prod, each with vpc, eks, iam, addons subfolders).
- **Why:** Terragrunt expects a specific folder layout. Each subfolder under an environment becomes one independent Terraform root — they each get their own state file in S3 and can be applied independently or in order.

#### Step 2 — Root `terragrunt.hcl`
- **What:** Wrote `infra/terragrunt.hcl` — the top-level config inherited by every module in the project.
- **What it does:**
  - Defines shared locals (region, account ID, S3 bucket name)
  - Configures the S3 remote backend with `use_lockfile = true` (no DynamoDB needed)
  - Auto-generates a `provider.tf` in each module folder so no module needs its own AWS provider block
  - Pins minimum Terraform version to 1.10+ (required for `use_lockfile`)
- **Why:** Without this file, every single module (vpc, eks, iam, addons × dev + prod = 8 modules) would need to repeat the same backend config and provider block. This file writes it once and injects it everywhere automatically.

#### Step 3 — `env.hcl` for dev and prod
- **What:** Wrote `environments/dev/env.hcl` and `environments/prod/env.hcl`.
- **What each file contains:** A `locals {}` block with 3 values: `env_name`, `cluster_name`, `node_instance_type`.
- **Why:** Each module inside an environment (vpc, eks, iam, addons) needs to know which environment it belongs to and what cluster name/node size to use. Instead of repeating `"projectview-dev"` in 4 different module files, each module reads from its environment's `env.hcl` once. Change one file → all 4 modules pick it up.
- **Key difference between dev and prod:** `node_instance_type` — dev uses `t3.medium` (cheaper), prod uses `t3.large` (more CPU/RAM for real workloads).

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
