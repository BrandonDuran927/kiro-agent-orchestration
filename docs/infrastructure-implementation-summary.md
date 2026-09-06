# Infrastructure Implementation Summary — Workshop Feedback Portal (POC)

Status: Implementation (Mode 1 — Infrastructure Implementation)
Owner: DevOps Engineer
Source of truth: `WORKSHOP_CONSTRAINTS.md`, `docs/requirements.md`, `docs/architecture.md`, `docs/api-contract.md`, `docs/data-model.md`
Scope: `terraform/` only. No `terraform apply` performed in this mode.

This document describes the Terraform that provisions the approved serverless
topology, how each resource maps to the architecture, how the workshop
constraints are satisfied, and the assumptions about application artifacts.

---

## 1. Resources implemented

All resources live under `terraform/` and use only approved-catalog services
(S3, CloudFront, API Gateway, Lambda, DynamoDB, CloudWatch, IAM).

| File | Resources |
|------|-----------|
| `versions.tf` | Terraform `>= 1.5.0`; providers `aws ~> 5.40`, `archive ~> 2.4`, `random ~> 3.6`. |
| `variables.tf` | Input variables: region, project/environment names, organizer key (sensitive), Lambda runtime/handler, Lambda & frontend artifact paths, log retention, CloudFront price class. |
| `main.tf` | AWS provider (region + default tags), caller identity / region data sources, optional `random_password` for the organizer key, shared `locals`. |
| `dynamodb.tf` | `aws_dynamodb_table.feedback` — `PAY_PER_REQUEST`, hash key `feedbackId` (S), no sort key, no GSIs. |
| `lambda.tf` | `archive_file` packaging, `aws_cloudwatch_log_group.lambda`, IAM assume-role + scoped policy, `aws_lambda_function.api` (Python). |
| `apigateway.tf` | `aws_apigatewayv2_api` (HTTP API) with CORS, `AWS_PROXY` integration, routes `GET /health`, `POST /feedback`, `GET /feedback`, `$default` stage with access logging, access-log group, `aws_lambda_permission`. |
| `s3_cloudfront.tf` | Private `aws_s3_bucket` + Block Public Access + ownership controls + SSE, `aws_cloudfront_origin_access_control`, `aws_cloudfront_distribution`, OAC-scoped bucket policy, `aws_s3_object` asset upload. |
| `outputs.tf` | CloudFront URL/ID, API base URL, bucket name, table name, Lambda name/log group, organizer-key metadata. |
| `lambda_bootstrap/handler.py` | Infra-owned placeholder handler (packaging fallback only; not the application). |
| `.gitignore`, `example.tfvars` | Exclude state/secrets/artifacts; document non-secret variable supply. |

---

## 2. Mapping to the architecture

| Architecture component (docs/architecture.md §3) | Terraform |
|---|---|
| **S3 — frontend asset store** (private, OAC-only) | `aws_s3_bucket.frontend` + `aws_s3_bucket_public_access_block` (all four blocks true) + `BucketOwnerEnforced` ownership + AES256 SSE + `aws_s3_bucket_policy` granting only `s3:GetObject` to `cloudfront.amazonaws.com` with `AWS:SourceArn` = the distribution ARN. Assets uploaded via `aws_s3_object`. |
| **CloudFront — content delivery** | `aws_cloudfront_distribution.frontend` with `origin_access_control_id`, `viewer_protocol_policy = redirect-to-https`, `default_root_object = index.html`, `cloudfront_default_certificate = true` (no ACM/custom domain), `PriceClass_100`. |
| **API Gateway (HTTP API) — backend entry** | `aws_apigatewayv2_api.http` (protocol `HTTP`), CORS limited to the CloudFront origin and `x-organizer-key`/`content-type` headers, three routes matching the API contract, `$default` auto-deploy stage with JSON access logging to CloudWatch. |
| **Lambda (Python) — application logic** | `aws_lambda_function.api` (single path-routed handler), env vars `FEEDBACK_TABLE_NAME`, `ORGANIZER_KEY`, `LOG_LEVEL`. Packaged deterministically via `archive_file` with `source_code_hash` for content-based change detection. |
| **DynamoDB — feedback persistence** | `aws_dynamodb_table.feedback`, on-demand, PK `feedbackId`, matching `docs/data-model.md`. |
| **CloudWatch — observability** | Explicit Lambda log group and API Gateway access-log group with configurable retention (NFR-013). |
| **IAM — access control** | Lambda assume-role for `lambda.amazonaws.com`; inline policy scoped to (a) `logs:CreateLogStream`/`PutLogEvents` on this function's log group ARN and (b) `dynamodb:PutItem`/`GetItem`/`Scan` on the Feedback table ARN only. No wildcard resources. |

Wiring matches the two-path topology (ADR-1): browser → CloudFront → private S3
for static assets, and browser → API Gateway → Lambda → DynamoDB for the API.
A single path-routed Lambda is used (ADR-2): one function, one role, one log group.

### Routes → API contract

| Route | Purpose | Contract |
|-------|---------|----------|
| `GET /health` | Health smoke test | api-contract §2.1 |
| `POST /feedback` | Submit feedback (unauth) | api-contract §2.2 |
| `GET /feedback` | List for review (organizer key checked in Lambda) | api-contract §2.3 |

Organizer gating (ADR-3) is enforced inside the Lambda against the
`ORGANIZER_KEY` env var; the API itself has no authorizer, consistent with the
approved design (no identity service in the catalog).

---

## 3. Constraint compliance

| Constraint | How satisfied |
|------------|---------------|
| AWS only, Terraform-provisioned (NFR-001) | All resources are AWS, defined entirely in `terraform/`. |
| Python backend, static frontend, no framework (NFR-002) | Lambda `runtime = python3.12`; frontend delivered as static S3 objects; no framework infra introduced. |
| Approved services only (NFR-003) | Only S3, CloudFront, API Gateway v2, Lambda, DynamoDB, CloudWatch, IAM. `random`/`archive` are Terraform-internal providers (no AWS service). |
| No Route 53 / ACM / custom domain (NFR-004) | `cloudfront_default_certificate = true`; default `execute-api` endpoint; no DNS/cert resources. |
| Frontend storage not public (NFR-005, AC-012) | Block Public Access (all true), `BucketOwnerEnforced`, bucket policy grants read only to the specific CloudFront distribution via OAC + `AWS:SourceArn`. |
| Least privilege IAM (NFR-006) | Resource-scoped inline policy; no `*` resources; separate log-group and table ARNs. |
| No embedded secrets (NFR-007, AC-013) | Organizer key supplied via `sensitive` variable / `TF_VAR_organizer_key`, injected into Lambda env by Terraform; `.gitignore` excludes `*.tfvars` and state; `example.tfvars` contains no real value. |
| On-demand / negligible idle (NFR-008) | DynamoDB `PAY_PER_REQUEST`; Lambda per-invoke; HTTP API per-request; CloudFront/S3 minimal idle. |
| Minimal footprint (NFR-009) | Single Lambda, single table, single distribution, no GSIs, no modules/remote state/pipelines. |
| Deploy/teardown simplicity (NFR-010) | Single root module; fully removable via `terraform destroy`. |
| HTTPS transport (NFR-011) | CloudFront redirect-to-HTTPS; API Gateway HTTPS-only default endpoint. |
| Durable persistence (NFR-012) | DynamoDB durable store; PK `feedbackId`. |
| Observability (NFR-013) | Dedicated CloudWatch log groups for Lambda and API access logs; default metrics apply. |

No prohibited services (EC2/ECS/EKS, ELB, VPC/NAT, Route 53, ACM) are present.

---

## 4. Variables and outputs

Key variables (see `variables.tf` for full list and defaults):

- `aws_region` (default `us-east-1`), `project_name`, `environment` — parameterize region and resource naming/tags.
- `organizer_key` — sensitive; empty default triggers a generated random key so the stack is internally consistent for validation.
- `lambda_source_dir` (default `../backend/build`), `lambda_handler` (default `handler.lambda_handler`), `lambda_runtime` (default `python3.12`).
- `frontend_source_dir` (default `../frontend/dist`).
- `log_retention_days`, `cloudfront_price_class`.

Outputs: `cloudfront_url`, `cloudfront_distribution_id`, `api_base_url`,
`frontend_bucket_name`, `dynamodb_table_name`, `lambda_function_name`,
`lambda_log_group`, `organizer_key_is_generated`, and `organizer_key`
(sensitive). `api_base_url` is the non-secret value the frontend consumes.

---

## 5. Validation performed (no deployment)

Run from `terraform/`:

```
terraform fmt -recursive        # applied; no diffs
terraform fmt -check -recursive # exit 0 (formatting compliant)
terraform init -backend=false   # providers installed (aws 5.100.0, archive 2.8.0, random 3.9.0)
terraform validate              # "Success! The configuration is valid."
```

`terraform init`/`validate` were run with `-backend=false` and no cloud
credentials/backend. No `terraform plan` against real credentials and no
`terraform apply` were executed, per Infrastructure Implementation mode. The
`.terraform/` working dir and lock file created for validation were removed and
are git-ignored.

---

## 6. Assumptions about the Lambda artifact path

The backend and frontend workstreams run in parallel, so their build outputs may
not exist when this Terraform is authored. The following artifact contract is
assumed; adjust the variables if the backend/frontend workstreams choose
different paths.

- **Lambda source:** `var.lambda_source_dir` (default `../backend/build`) must
  contain the deployable Python package, including a module whose name matches
  the first segment of `var.lambda_handler` (default `handler` → `handler.py`)
  exposing `lambda_handler(event, context)`. It is zipped by `archive_file`.
- **Packaging fallback:** if that build output is absent at plan time,
  `terraform/lambda_bootstrap/handler.py` (an infra-owned placeholder returning
  503) is packaged instead so `fmt/validate/plan` succeed. This placeholder is
  **not** the application and must be replaced by the real backend build output
  before deployment. Detection is via `fileexists(...)` on the handler module.
- **Frontend assets:** `var.frontend_source_dir` (default `../frontend/dist`)
  must contain the built static site including `index.html`. Objects are
  uploaded with content types inferred by extension. If absent at plan time the
  upload set is empty (no objects), keeping validation green; assets must be
  present before deployment for the frontend to load.
- **API base URL injection:** the non-secret `api_base_url` output is intended
  for the frontend's runtime/build configuration. The exact injection mechanism
  is a downstream (frontend/deployment) detail; only the non-secret URL is
  exposed — never the organizer key.
- **Dependencies:** the backend is assumed to require no third-party Python
  packages beyond the AWS Lambda runtime + `boto3` (bundled in the runtime). If
  the backend adds external dependencies, they must be vendored into the build
  output directory before packaging.

---

## 7. Known limitations (accepted for POC)

- Organizer gating uses a shared key in the Lambda environment (ADR-3, R-001) —
  weaker than identity-based authz, accepted POC risk.
- `GET /feedback` uses a DynamoDB `Scan` (ADR-4) — appropriate at workshop scale
  only.
- No WAF/rate limiting/DDoS protection beyond platform defaults (R-002, out of
  scope).
- Local Terraform state only (no remote backend) — acceptable for a short-lived,
  single-operator POC; do not commit state (`.gitignore` enforces this).
- CloudFront `custom_error_response` maps 403/404 to `index.html` for static
  delivery robustness; no application data is exposed by this behavior.

---

## 8. Terminal status

Only approved-catalog resources are provisioned; the topology, routes, data
model, IAM boundaries, and public/private boundaries match the approved
architecture, API contract, and data model; no Route 53/ACM/custom domain or
prohibited compute is present; no secrets are embedded; and `terraform fmt`,
`init -backend=false`, and `validate` all pass. No deployment was performed.

INFRA_STATUS: PASS
