# ProjectView — DevOps Engineer Assessment

## Project Goal
Build a production-grade cloud infrastructure for a DevOps job interview assessment.
Demonstrate proficiency in IaC, Kubernetes, GitOps, CI/CD, and secrets management.

## The Full Stack

- **Terragrunt/Terraform** — Two EKS clusters (dev + prod), VPC, IAM, security groups
- **ArgoCD** — App of Apps pattern on both clusters, GitOps CD, RBAC per environment
- **AWS ALB Ingress Controller** — External traffic routing with proper annotations
- **External Secrets Operator** — ClusterSecretStore backed by AWS Secrets Manager, at least one working ExternalSecret
- **Helm chart** — Generic/reusable chart with per-env values (dev/staging/production)
- **GitHub Actions CI** — Build, test, push to registry (ECR/GHCR), tag by Git SHA
- **Sample app** — Simple web server to drive the whole pipeline

## Environment Layout

- **Dev cluster:** `dev` + `staging` namespaces
- **Prod cluster:** `production` namespace
- **Promotion flow:** dev → staging → production via GitOps (ArgoCD)

## Repo Structure (planned)

```
ProjectView/
├── infra/                  # Terragrunt + Terraform modules
│   ├── modules/            # Reusable TF modules (eks, vpc, iam, addons)
│   └── environments/
│       ├── dev/
│       └── prod/
├── gitops/                 # ArgoCD application definitions
│   ├── apps/               # App of Apps root + child apps
│   └── argocd/             # ArgoCD install config + RBAC
├── helm/                   # Generic Helm chart
│   ├── templates/
│   └── values/
│       ├── dev.yaml
│       ├── staging.yaml
│       └── production.yaml
├── app/                    # Sample application (simple web server)
│   └── Dockerfile
├── .github/
│   └── workflows/          # GitHub Actions CI pipeline
└── README.md
```

## Key Decisions

- **AWS Region:** us-east-1
- **Container Registry:** ECR
- **Terraform module source:** terraform-aws-modules (official community modules)
- **Cluster naming:** projectview-dev, projectview-prod
- **AWS Account:** available and ready

## Project Phases

### Phase 0 — Bootstrap
- Verify tools installed: terraform, terragrunt, aws cli, kubectl, helm
- Create S3 bucket for Terraform remote state
- Create DynamoDB table for state locking
- Create ECR repository for Docker images
- Verify AWS CLI is configured

### Phase 1 — Infrastructure (Terragrunt)
- Write 4 Terraform modules: `vpc`, `eks`, `iam`, `addons`
- Write Terragrunt environment configs for dev + prod
- Deploy order: vpc → eks → iam → addons
- Dev cluster: t3.medium nodes | Prod cluster: t3.large nodes

### Phase 2 — Sample App + GitHub Actions CI
- Python Flask app returning `{"status":"ok","env":"...","version":"<git-sha>"}`
- Multi-stage Dockerfile
- GitHub Actions: build → lint → push to ECR with git SHA tag → update Helm values

### Phase 3 — Helm Chart
- Generic chart: Deployment, Service, Ingress, ConfigMap, ExternalSecret templates
- Per-environment values files: dev.yaml, staging.yaml, production.yaml

### Phase 4 — GitOps (ArgoCD)
- App of Apps pattern — one root app manages all child apps
- Promotion flow: CI auto-deploys to dev → manual PR to staging → manual PR to production
- Rollback: git revert values file → ArgoCD auto-syncs

### Phase 5 — Documentation & Diagram
- README with setup, decisions, limitations
- HTML/SVG architecture diagram
- Keep `documentation.md` updated throughout

## Submission Requirements

- README with setup instructions, assumptions, design decisions, prerequisites, known limitations
- Architecture diagram (HTML/SVG preferred)
- Submit at least 1 business day before review session

## Two Repos
- `ProjectView` (this repo) — app, helm, gitops, CI pipeline
- `ProjectView-infra` — Terraform modules + Terragrunt environments (local: `C:\Users\USER\ProjectView-infra`)

## Docs Location
All documentation lives in `ProjectView` (this repo) only:
- `progress.md` — progress tracker with timestamps
- `documentation.md` — step-by-step log of everything we did
- `explanations.md` — technology and concept explanations

**IMPORTANT:** Always update these files when working in `ProjectView-infra` too. Never let them go out of sync.

## How to work on files together
When writing any file:
1. Explain what the file does and what each block means BEFORE writing it
2. Wait for the user to ask questions — don't move on until they say ready
3. Write the file with a comment on every line
4. Review the full file together after writing
5. Only move to the next file after the user confirms
6. After the user understands a concept, add it to explanations.md

## Branch & PR Workflow

Every feature, bug fix, chore, or version update must follow this flow:

### Branch naming
Format: `type/short-description`
Types: `feature`, `bug-fix`, `chore`, `version-update`
Examples: `feature/vpc-module`, `bug-fix/eks-iam-role`, `chore/update-node-version`

### Rules
1. Never work directly on `main`
2. Open a new branch before starting any work — announce the branch name to the user
3. All work for that task stays on that branch only
4. When work is complete, open a PR using the format in `.github/PRformat.md`
5. Issue format for new issues is in `.github/issue-format.md`

## instructions to work
- every command you write me on CLI, write below it what it does. if the command it important write why we need it now.
- i want to learn! from this project. i need to know everything about it. so we will do it step-step so i can understand.
- in the file "documentation" write every step we did, and why we did it. split it to infra, bug-fixes, app, workflow, gitops, and another category i you think is neccesary.
- in the file "progress", mention the progress we done with date and time. make sure to do it.
- in the file "explanations", add every technology or concept explained. do it automatically without being asked.
- at the end of every phase, write a short summary paragraph in progress.md.

