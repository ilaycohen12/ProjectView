# ProjectView — Documentation Log

A living document of every step and decision made in this project, explained in plain English.
Updated throughout the build.

---

## Table of Contents
1. [Key Decisions](#key-decisions)
2. [Infrastructure (Phase 0 — Bootstrap)](#phase-0--bootstrap)
3. [Infrastructure (Phase 1 — Modules + Deploy)](#phase-1--infrastructure-modules--deploy)
4. [App](#app)
5. [CI/CD Workflow](#cicd-workflow)
6. [GitOps](#gitops)
7. [Secrets](#secrets)
8. [Bug Fixes](#bug-fixes)

---

## Key Decisions

> These are the big architectural choices made during the project and the reasoning behind each one.

### 1. Terragrunt over plain Terraform
**Decision:** Use Terragrunt as a wrapper around Terraform.
**Why:** We have two environments (dev and prod). Without Terragrunt, every module would need its own backend config, provider block, and region setting — duplicated for every environment. Terragrunt lets us define those once in a root `terragrunt.hcl` and inherit them everywhere. Less repetition = fewer mistakes.

### 2. S3 native locking instead of DynamoDB
**Decision:** Use `use_lockfile = true` in the S3 backend config (Terraform 1.10+) instead of a DynamoDB table.
**Why:** DynamoDB locking requires creating and managing a separate AWS resource. S3 native locking does the same thing with a `.tflock` file in the same bucket — no extra resource needed. We still created the DynamoDB table from the old approach, but the active lock mechanism is S3-native.

### 3. t3.small nodes for EKS
**Decision:** Use `t3.small` EC2 instances (2 vCPU, 2GB RAM) for the EKS node group.
**Why:** Cost. t3.small is ~$15/month per node. The cluster runs 2 nodes by default and scales to 3 max. This is enough for the demo app, 4 addon pods (ALB controller, ESO, ArgoCD, KEDA), and 2 worker pods. For a real production workload we'd use t3.medium or larger.

### 4. Two SQS queues (signed + free) instead of one
**Decision:** Create two separate SQS queues — one for signed (paying) users and one for free users.
**Why:** Priority processing. Signed users get their PDFs processed by a KEDA-scaled worker that spins up more pods under load. Free users get a single always-on worker that processes at a steady pace. One queue would mean both user types compete equally — defeating the priority logic.

### 5. KEDA only on the signed queue
**Decision:** KEDA ScaledObject watches only the signed queue, not the free queue.
**Why:** KEDA scales the signed worker from 0 to 3 pods based on queue depth. The free worker stays at exactly 1 pod always. This demonstrates the key concept: signed users get burst capacity, free users get guaranteed-but-limited throughput. Scaling both queues the same way would remove the distinction.

### 6. Two separate worker Deployments
**Decision:** `signed-worker` and `free-worker` are separate Kubernetes Deployments.
**Why:** They need different scaling behavior (KEDA vs fixed), different queue URLs as environment variables, and potentially different resource limits in the future. Same Docker image, different config.

### 7. PDF generation as the core feature
**Decision:** The app converts HTML to PDF using WeasyPrint, stores the result in S3, and saves metadata to RDS.
**Why:** It's a realistic async workload that justifies a queue, a worker, object storage, and a database all at once. Other ideas (image resize, currency exchange) either required external APIs or didn't naturally involve a database. PDF generation is entirely self-contained.

### 8. ECR over GitHub Container Registry (GHCR)
**Decision:** Store Docker images in AWS ECR, not GHCR.
**Why:** ECR lives in the same AWS account as the cluster. EKS can pull from ECR without any extra credentials — the node's IAM role already has access. GHCR would require creating and managing a Kubernetes image pull secret.

### 9. ArgoCD exposed via LoadBalancer
**Decision:** ArgoCD server is exposed as a `LoadBalancer` service type, not `ClusterIP` or `NodePort`.
**Why:** LoadBalancer creates a real AWS load balancer with a public DNS name, making the ArgoCD UI reachable from a browser. For a demo/interview this is the simplest approach. In production you'd put it behind an Ingress with TLS.

### 10. No Route 53 or CloudFront
**Decision:** Skip DNS and CDN for now.
**Why:** Route 53 requires a registered domain (~$12/year) and is only needed for a custom URL like `projectview.com`. CloudFront is a CDN for static assets — this project serves a dynamic API, so caching at the edge adds no value. The ALB URL works fine for a demo.

### 11. Destroy everything when not working
**Decision:** Run `terragrunt run-all destroy` at the end of each session.
**Why:** EKS costs $73/month for the control plane alone, even with 0 nodes running. Keeping it on overnight for no reason wastes money. `terragrunt run-all apply` rebuilds everything in ~40 minutes when needed.

### 12. Global module for cross-environment resources
**Decision:** Created an `infra/global/` directory (not inside `environments/dev` or `prod`) for ECR and the API key secret.
**Why:** ECR is shared — both dev and prod pull images from the same repository. The API key secret is also account-wide. Putting these inside an environment directory would suggest they belong to only that environment.

### 13. `recovery_window_in_days = 0` for Secrets Manager
**Decision:** Set the recovery window to 0 on the API key secret.
**Why:** By default AWS holds deleted secrets for 30 days (recovery period). With Terraform, if you run `destroy` you want the secret gone immediately — otherwise the next `apply` fails because a secret with that name already "exists" in recovery. Setting `0` allows immediate deletion.

---

## Phase 0 — Bootstrap

### Tool Installation
- **What:** Installed git, AWS CLI, kubectl, terraform, terragrunt, helm on Windows.
- **Why:** These are the core tools for the entire project. Without them nothing can be built or deployed.
- **How:** git/aws/kubectl were already present. terraform and helm installed via `winget`, then copied to `C:\Windows\System32`. terragrunt downloaded as a single `.exe` from the official GitHub release and placed in `System32`.
- **Tool roles:**
  | Tool | Role |
  |------|------|
  | `git` | Version control — GitHub Actions uses git SHA to tag Docker images |
  | `aws cli` | Talks to AWS from the terminal — creating resources, authenticating kubectl |
  | `kubectl` | Kubernetes CLI — inspect pods, nodes, services, ArgoCD status |
  | `terraform` | IaC tool — provisions AWS resources from `.tf` files |
  | `terragrunt` | Wrapper around Terraform — removes config repetition between dev and prod |
  | `helm` | Kubernetes package manager — installs ArgoCD, KEDA, ESO, ALB controller |

### AWS CLI Configuration
- **What:** Ran `aws configure` to authenticate the CLI.
- **Why:** Every AWS command needs to know which account to talk to and with what permissions.
- **Security decision:** Created a dedicated IAM user (`admin`) instead of root access keys. Root keys can never be restricted — one leak = entire AWS account compromised. IAM user keys can be revoked at any time.
- **Verified with:** `aws sts get-caller-identity` → Account `086241318869`, user `admin`.

### S3 Bucket for Terraform State
- **What:** Created `projectview-tf-state-086241318869` in `us-east-1` with versioning enabled.
- **Why:** Terraform state must live somewhere safe and shared. Local state only exists on your laptop — lose it, and Terraform loses track of all infrastructure. S3 keeps it safe and accessible from any machine.
- **Why versioning:** A corrupted state file (from a failed apply mid-run) can be restored from the previous S3 version.
- **Why account ID in bucket name:** S3 bucket names are globally unique across all AWS accounts worldwide.

### DynamoDB Table for State Locking
- **What:** Created `projectview-tf-locks` table in `us-east-1`.
- **Why:** Without locking, two Terraform runs starting at the same time would both write to the state file and corrupt it. DynamoDB acts as a distributed lock — one run writes a lock entry, any other run waits until it's released.
- **Note:** We now use S3 native locking (`use_lockfile = true`) — the DynamoDB table was created early but is no longer the active lock mechanism.

### ECR Repository
- **What:** Created `projectview-app` ECR repository in `us-east-1`.
- **URI:** `086241318869.dkr.ecr.us-east-1.amazonaws.com/projectview-app`
- **Why:** ECR is the bridge between CI and the cluster. GitHub Actions builds the Docker image and pushes it here. EKS pulls from here when deploying. Images are tagged by git SHA (e.g. `:a3f9c12`) so every deployment is traceable to an exact commit.

### GitHub Workflow Setup
- **What:** Created issue + PR templates, branch naming convention, authenticated `gh` CLI.
- **Convention:** Branch names follow `type/description` format (e.g. `feature/vpc-module`, `fix/iam-role`).
- **Why:** Every change has a paper trail — issue (the problem) → branch (the work) → PR (the solution). This is standard practice in real engineering teams and makes the project history readable.

---

## Phase 1 — Infrastructure Modules + Deploy

### Module Structure
All reusable Terraform code lives in `infra/modules/`. Environment-specific configuration lives in `infra/environments/dev/` and `infra/environments/prod/`. Each environment folder has a subfolder per module (e.g. `environments/dev/vpc/terragrunt.hcl`) that points to the shared module and passes environment-specific inputs.

### Modules Written

#### `vpc`
Creates the network layer: VPC, 3 tiers of subnets (public/private/database), Internet Gateway, NAT Gateway, route tables, and a DB subnet group.
- **Public subnets** — ALB and NAT Gateway live here (internet-facing)
- **Private subnets** — EKS worker nodes live here (no direct internet access)
- **Database subnets** — RDS lives here (no internet access at all)
- **NAT Gateway** — lets private subnet resources (pods) reach the internet for pulling images, without exposing them

#### `eks`
Creates the Kubernetes control plane and worker nodes.
- Control plane is fully managed by AWS — we don't manage the API server
- Node group: t3.small, min=1, max=3, desired=2
- Also creates the OIDC provider needed for IRSA (pods assuming IAM roles)

#### `iam`
Creates 4 IAM roles, each scoped to a specific Kubernetes service account via IRSA:
- **ALB controller role** — permission to create/update/delete AWS load balancers
- **ESO role** — permission to read secrets from AWS Secrets Manager
- **KEDA role** — permission to read SQS queue depth (`sqs:GetQueueAttributes`)
- **Worker role** — permission to read/delete messages from both SQS queues + read/write S3

IRSA (IAM Roles for Service Accounts) means each pod gets exactly the permissions it needs, and nothing else. No shared credentials, no overly broad roles.

#### `rds`
Creates a PostgreSQL 15 instance in the database subnet.
- Stores: PDF job metadata (user ID, S3 key, status, timestamps)
- Not publicly accessible — only reachable from within the VPC
- Password stored in AWS Secrets Manager, synced into Kubernetes by ESO

#### `sqs`
Creates two queues:
- `projectview-dev-signed` — for signed (paying) users, KEDA-watched
- `projectview-dev-free` — for free users, processed by 1 steady worker
- Both have 60s visibility timeout (message reappears for retry if worker crashes) and 1 hour retention

#### `s3`
Creates a private S3 bucket for storing generated PDFs.
- Bucket name includes account ID for global uniqueness
- All public access blocked — PDFs are served via presigned URLs (temporary, expiring links)

#### `global`
Contains resources shared across all environments:
- ECR repository (one repo, both dev and prod pull from it)
- Secrets Manager secret slot for the API key (value set manually after apply)

#### `addons`
Installs 4 Helm charts onto the EKS cluster:
- **ALB Ingress Controller** — watches Ingress resources, creates AWS ALBs
- **External Secrets Operator (ESO)** — syncs Secrets Manager values into K8s secrets
- **ArgoCD** — GitOps CD, watches the gitops repo and deploys changes automatically
- **KEDA** — watches ScaledObject resources, scales signed-worker based on SQS depth

### Deploy Order (dev)
Must apply in this exact order due to dependency chain:

| Step | Module | Depends On |
|------|--------|------------|
| 1 | vpc | nothing |
| 2 | eks | vpc (subnet IDs) |
| 3 | sqs | nothing |
| 4 | s3 | nothing |
| 5 | iam | eks (OIDC ARN) + sqs (queue ARNs) + s3 (bucket ARN) |
| 6 | rds | vpc (subnet group) + eks (node security group) |
| 7 | addons | eks (endpoint + CA cert) + iam (role ARNs) + vpc (VPC ID) |
| 8 | global | nothing (ECR + secret slot, no cross-module deps) |

---

## App

### Hello World (test deployment)
- **What:** Minimal Flask app with `/` (HTML page) and `/health` (JSON `{"status":"ok"}`)
- **Why:** Before building the full PDF app, we deploy a simple page to verify the entire pipeline works end-to-end: image build → ECR push → EKS deployment → ALB → browser.
- **Files:** `app/app.py`, `app/requirements.txt`, `app/Dockerfile`

---

## CI/CD Workflow

> To be documented when GitHub Actions pipelines are written.

---

## GitOps

> To be documented when ArgoCD App of Apps is configured.

---

## Secrets

> To be documented when ESO ClusterSecretStore and ExternalSecret are configured.

---

## Bug Fixes

### Bug 1 — `required_version` invalid in Terragrunt `terraform` block
- **Error:** `Unsupported argument` on line 37 of `infra/terragrunt.hcl`
- **Cause:** In Terragrunt, the `terraform {}` block only accepts `source`, `extra_arguments`, and hooks. `required_version` is a Terraform-native keyword — it belongs in a `.tf` file, not in a Terragrunt config.
- **Fix:** Moved `required_version = ">= 1.10.0"` into the `generate "provider"` block contents so Terragrunt writes it into the auto-generated `provider.tf` inside each module.

### Bug 2 — `remote_state` had no `generate` block
- **Error:** `Found remote_state settings but no backend block in the Terraform code`
- **Cause:** The `remote_state` block tells Terragrunt where to store state, but without a `generate` attribute Terragrunt doesn't know where to write the backend config file. Each module was missing a `backend.tf`.
- **Fix:** Added `generate = { path = "backend.tf", if_exists = "overwrite" }` to the `remote_state` block. Terragrunt now auto-creates `backend.tf` in every module before running.

### Bug 3 — Helm provider not declared in `required_providers`
- **Error:** `Blocks of type "kubernetes" are not expected here` in `addons/main.tf`
- **Cause:** The Helm provider uses a `kubernetes {}` nested block for cluster authentication. Without declaring the Helm provider in `required_providers`, Terraform doesn't know its schema and rejects the block.
- **Fix:** Created `infra/modules/addons/versions.tf` declaring `hashicorp/helm ~> 3.0` (bumped from `~> 2.0` after the lock file showed version 3.2.0 was cached).

### Bug 4 — Helm provider version constraint conflicted with lock file
- **Error:** `locked provider hashicorp/helm 3.2.0 does not match configured version constraint ~> 2.0`
- **Cause:** The lock file (created by a previous Terraform init) had Helm provider 3.2.0, but `versions.tf` said `~> 2.0`. These are incompatible — Terraform refuses to run.
- **Fix:** Updated the constraint to `~> 3.0` to match what was already locked.

### Bug 6 — Helm provider v3 breaking changes
- **Error:** Multiple errors: `kubernetes` block unsupported, `set {}` blocks unsupported, cluster unreachable
- **Cause:** The Helm provider jumped from 2.x to 3.x in the cached lock file. Version 3 removed the `kubernetes {}` nested block inside `provider "helm"` and changed `set {}` blocks to list syntax. Switching to a separate `kubernetes` provider also didn't work because Helm v3 doesn't automatically inherit it.
- **Fix:** Pinned the Helm provider back to `~> 2.0` in `versions.tf`, restored the `kubernetes {}` block inside `provider "helm"`, and restored `set {}` block syntax. Ran `terragrunt init -upgrade` to downgrade from 3.2.0 to latest 2.x.

### Bug 7 — Helm releases timing out on t3.small nodes
- **Error:** `context deadline exceeded` on ArgoCD helm release
- **Cause:** Default Terraform Helm release timeout is 5 minutes. ArgoCD takes longer to fully start on small nodes.
- **Fix:** Added `wait = false` to all helm releases so Terraform submits the install and doesn't wait for pod readiness. We verify pods manually with `kubectl get pods -A` afterward.

### Bug 8 — Namespaces stuck in Terminating state
- **Error:** `unable to create new content in namespace argocd because it is being terminated`
- **Cause:** Kubernetes namespace deletion is not instant — it waits for all resources and finalizers to clean up. KEDA registers a custom API group (`external.metrics.k8s.io/v1beta1`) and when KEDA was deleted mid-install, the stale API registration blocked namespace deletion indefinitely.
- **Fix:** Used `kubectl replace --raw /api/v1/namespaces/<name>/finalize` to forcefully clear the finalizers from all three stuck namespaces (argocd, external-secrets, keda).

### Bug 5 — IAM applied before SQS and S3
- **Error:** `Unknown variable` on `dependency.sqs.outputs.signed_queue_arn` in `dev/iam/terragrunt.hcl`
- **Cause:** The IAM module references SQS and S3 dependency outputs. When those modules haven't been applied yet, their state files don't exist in S3, so Terragrunt can't resolve the outputs.
- **Fix:** Apply SQS and S3 before IAM. The `mock_outputs` in the dependency blocks only work for `plan` and `validate`, not for `apply`.
