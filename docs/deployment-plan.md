# Deployment Plan — Workshop Feedback Portal

Phase: DEPLOYMENT_PREPARATION (SDLC_WORKFLOW.md, Workflow A)
Owner: DevOps Engineer
Mode: Deployment Preparation — `terraform apply` is FORBIDDEN in this phase and was **not** run.

## Preconditions (all met)

```text
FRONTEND_STATUS: PASS
BACKEND_STATUS:  PASS
INFRA_STATUS:    PASS
QA_STATUS:       PASS
SECURITY_STATUS: PASS
```

## Environment

- Terraform: v1.16.1 (windows_amd64)
- Providers (from lock file): hashicorp/aws v5.100.0, hashicorp/archive v2.8.0, hashicorp/random v3.9.0
- Working directory: `terraform/`
- AWS credentials: **NOT available** in this environment (no static creds, no EC2 IMDS role reachable).

## Commands run and actual results

### 1. `terraform fmt -check -recursive`

Exit code: `0` — no output. All `.tf` files are already canonically formatted. PASS.

### 2. `terraform init`

Exit code: `0`.

```text
Initializing the backend...
Initializing provider plugins...
- Reusing previous version of hashicorp/aws from the dependency lock file
- Reusing previous version of hashicorp/archive from the dependency lock file
- Reusing previous version of hashicorp/random from the dependency lock file
- Using previously-installed hashicorp/random v3.9.0
- Using previously-installed hashicorp/aws v5.100.0
- Using previously-installed hashicorp/archive v2.8.0
Terraform has been successfully initialized!
```

Backend: local (no remote backend configured; state is local for this POC). PASS.

### 3. `terraform validate`

Exit code: `0`.

```text
Success! The configuration is valid.
```

PASS.

### 4. `terraform plan`

Exit code: `1` — **plan could not produce a full live diff.** Terraform began evaluating the plan
(it successfully read the `archive_file.lambda` data source and rendered the `random_password.organizer_key[0]`
resource), then failed when the AWS provider tried to refresh credentials:

```text
data.archive_file.lambda: Reading...
data.archive_file.lambda: Read complete after 0s [id=9fe832e405efab5b1a88cf29e11f7caa3d1ccb44]

Terraform planned the following actions, but then encountered a problem:

  # random_password.organizer_key[0] will be created
  + resource "random_password" "organizer_key" { ... }

Plan: 1 to add, 0 to change, 0 to destroy.

Changes to Outputs:
  + organizer_key              = (sensitive value)
  + organizer_key_is_generated = true

Error: No valid credential sources found
  with provider["registry.terraform.io/hashicorp/aws"], on main.tf line 1
Error: failed to refresh cached credentials, no EC2 IMDS role found ...
  169.254.169.254:80: ... network unreachable
```

This is an environment limitation, not a configuration defect: `fmt`, `init`, and `validate` all pass,
and the credential-independent portion of the plan evaluated cleanly. A full live diff requires AWS
credentials and will be produced at apply time in the target account.

## Expected plan (derived from configuration — NOT a live plan)

> The counts below are derived by static analysis of the Terraform configuration because no live plan
> could be produced without credentials. They are the expected result of a first `terraform plan`/`apply`
> against an empty account with **no** `organizer_key` supplied and **no** built frontend/backend artifacts present.

The configuration declares 22 `resource` blocks (21 AWS + 1 `random`). Resource instances expected to be **created**:

| # | Resource | Type | Notes |
|---|----------|------|-------|
| 1 | `aws_dynamodb_table.feedback` | DynamoDB | PAY_PER_REQUEST, hash key `feedbackId` |
| 2 | `aws_cloudwatch_log_group.lambda` | CloudWatch Logs | `/aws/lambda/<prefix>-api`, 14-day retention |
| 3 | `aws_cloudwatch_log_group.api_access` | CloudWatch Logs | API access logs, 14-day retention |
| 4 | `aws_iam_role.lambda` | IAM | Lambda execution role |
| 5 | `aws_iam_role_policy.lambda` | IAM | Inline least-privilege policy (logs + scoped DynamoDB) |
| 6 | `aws_lambda_function.api` | Lambda | python3.12, handler `handler.lambda_handler` |
| 7 | `aws_lambda_permission.apigw` | Lambda | Allow invoke from HTTP API |
| 8 | `aws_apigatewayv2_api.http` | API Gateway v2 | HTTP API + CORS to CloudFront origin |
| 9 | `aws_apigatewayv2_integration.lambda` | API Gateway v2 | AWS_PROXY, payload v2.0 |
| 10 | `aws_apigatewayv2_route.health` | API Gateway v2 | `GET /health` |
| 11 | `aws_apigatewayv2_route.post_feedback` | API Gateway v2 | `POST /feedback` |
| 12 | `aws_apigatewayv2_route.get_feedback` | API Gateway v2 | `GET /feedback` |
| 13 | `aws_apigatewayv2_stage.default` | API Gateway v2 | `$default`, auto_deploy, access logging |
| 14 | `aws_s3_bucket.frontend` | S3 | Private frontend bucket (bucket_prefix) |
| 15 | `aws_s3_bucket_public_access_block.frontend` | S3 | All 4 public-access blocks = true |
| 16 | `aws_s3_bucket_ownership_controls.frontend` | S3 | BucketOwnerEnforced |
| 17 | `aws_s3_bucket_server_side_encryption_configuration.frontend` | S3 | AES256 |
| 18 | `aws_cloudfront_origin_access_control.frontend` | CloudFront | OAC, sigv4, always sign |
| 19 | `aws_cloudfront_distribution.frontend` | CloudFront | Default cert, PriceClass_100, SPA 403/404 fallback |
| 20 | `aws_s3_bucket_policy.frontend` | S3 | OAC-scoped read via SourceArn condition |
| 21 | `random_password.organizer_key[0]` | random | Created only because `organizer_key` var is empty |
| — | `aws_s3_object.frontend` | S3 | **0 instances** — `frontend/dist` absent, `for_each` is empty |

### Expected add/change/destroy counts

**Plan: 21 to add, 0 to change, 0 to destroy** (empty account, no `organizer_key`, no built `frontend/dist`).

Conditional variations:
- If `TF_VAR_organizer_key` **is** supplied → `random_password.organizer_key[0]` is **not** created → **20 to add**.
- If `frontend/dist` **is** built before apply → `aws_s3_object.frontend` expands to **N** instances (one per built file) → add count increases by N.
- Subsequent applies after building the real backend artifact will show a **change** to `aws_lambda_function.api` (new `source_code_hash`) rather than a create.

## Target account / region

- Account: **not detectable** — no credentials available; `data.aws_caller_identity.current` was not resolved.
- Region: **parameterized** via `var.aws_region`, default `us-east-1` (also the CloudFront/OAC requirement).
- All resource names are prefixed with `${var.project_name}-${var.environment}` (default `workshop-feedback-poc`).

## IAM / security-relevant changes

- **New IAM execution role** (`aws_iam_role.lambda`) assumable only by `lambda.amazonaws.com`.
- **Inline least-privilege policy** grants:
  - `logs:CreateLogStream`, `logs:PutLogEvents` scoped to this function's log group ARN only.
  - `dynamodb:PutItem`, `GetItem`, `Scan` scoped to the Feedback table ARN only.
- **S3 bucket is private**: public access block (all 4 true), BucketOwnerEnforced, AES256 SSE. Read is granted **only** to the specific CloudFront distribution via OAC + `AWS:SourceArn` condition.
- **CloudFront** uses the default `*.cloudfront.net` certificate; `redirect-to-https`. No Route 53/ACM/custom domain (NFR-004).
- **Organizer key** is marked `sensitive`, never committed; injected into Lambda env at apply time. If not supplied, a random 32-char key is generated (retrievable via `terraform output -raw organizer_key`).
- **API access logging** to CloudWatch is enabled on the `$default` stage.

## Prerequisite steps before `terraform apply`

1. **Configure AWS credentials** for the target account/region (env vars, shared profile, or role). Required for `plan`/`apply` to contact AWS.
2. **Build the backend Lambda artifact** into `backend/build/` (must contain `handler.py` exposing `lambda_handler` plus dependencies from `backend/requirements.txt`). Until this exists, Terraform packages the `lambda_bootstrap/` placeholder which returns HTTP 503.
3. **Set the organizer key**: `export TF_VAR_organizer_key="<strong-shared-key>"` (bash) / `$Env:TF_VAR_organizer_key="<strong-shared-key>"` (PowerShell). Otherwise a random key is generated.
4. **Build the frontend assets** into `frontend/dist/` (including `index.html`) so `aws_s3_object.frontend` uploads them.
5. **Substitute `__API_BASE_URL__`** in the frontend config with the deployed `api_base_url` output. Because CloudFront depends on the bucket and the API's CORS depends on CloudFront's domain, the typical flow is: apply → read `api_base_url` and `cloudfront_url` outputs → inject the API base URL into the built frontend config → re-run apply (or re-upload the affected object) so the corrected asset is served → invalidate the CloudFront cache if needed.
6. Run a fresh `terraform plan` in the credentialed environment and review the live diff before `apply`.

## Risks and accepted POC trade-offs

- **Local Terraform state** (no remote backend/locking) — acceptable for a single-operator POC; not for shared/production use.
- **Bootstrap Lambda placeholder** will be deployed if step 2 is skipped; the API would return 503 until the real artifact is packaged and re-applied.
- **CORS ↔ CloudFront ↔ frontend config circular bootstrapping**: the API base URL is known only after the API exists, and CORS references the CloudFront domain. Expect a two-pass apply/upload for the first deployment (see prerequisite 5).
- **Generated organizer key** is stored in Terraform state and marked sensitive; treat state as sensitive. Prefer supplying `TF_VAR_organizer_key` explicitly.
- **CloudFront distribution create/destroy is slow** (deploy and workshop cleanup can each take several minutes).
- **No custom domain / WAF / throttling** — explicitly out of scope per WORKSHOP_CONSTRAINTS.md; documented rather than mitigated with extra services.

## Validation summary

| Check | Result |
|-------|--------|
| `terraform fmt -check -recursive` | PASS (exit 0) |
| `terraform init` | PASS (exit 0) |
| `terraform validate` | PASS ("Success! The configuration is valid.") |
| `terraform plan` (live diff) | Not produced — no AWS credentials in this environment (expected/non-blocking) |
| Expected plan (derived) | 21 add / 0 change / 0 destroy (defaults, no key, no built assets) |
| `terraform apply` | NOT run (forbidden in this phase) |

Configuration is format-clean, initializes, and validates. The only reason a live plan diff was not
produced is the absence of AWS credentials in this preparation environment, which does not indicate any
defect. The stack is ready for human approval; the live plan will be generated in the credentialed target
account immediately before apply.

DEVOPS_STATUS: READY_FOR_APPROVAL
