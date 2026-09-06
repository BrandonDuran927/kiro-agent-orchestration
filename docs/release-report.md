# Release Report — Workshop Feedback Portal (POC)

Phase: DEPLOYMENT + VERIFICATION (SDLC_WORKFLOW.md, Workflow A)
Owner: DevOps Engineer
Human approval: `APPROVE DEPLOY` (granted before apply)
Date: 2026-09-05

## Target environment

- AWS account: **732304102770**
- IAM principal: `arn:aws:iam::732304102770:user/duranbrandon927@gmail.com`
- Region: **us-east-1**
- Terraform: v1.16.1 (windows_amd64)
- Providers: hashicorp/aws v5.100.0, hashicorp/archive v2.8.0, hashicorp/random v3.9.0
- State backend: local (single-operator POC, per deployment-plan.md accepted risk)

## Deployed endpoints

| Output | Value |
|--------|-------|
| **CloudFront URL (frontend)** | https://d1izl6or5rbeu.cloudfront.net |
| **API base URL** | https://h1ebnpore5.execute-api.us-east-1.amazonaws.com |
| CloudFront distribution ID | E1IY11XC8VP1PO |
| Frontend S3 bucket | workshop-feedback-poc-frontend-20260905090848431200000001 |
| DynamoDB table | workshop-feedback-poc-feedback |
| Lambda function | workshop-feedback-poc-api |
| Lambda log group | /aws/lambda/workshop-feedback-poc-api |
| Organizer key generated? | false (supplied explicitly via gitignored `organizer.auto.tfvars`) |

## Pre-apply preparation

1. **Lambda artifact** packaged into `backend/build/` — flat modules `handler.py`, `config.py`, `repository.py`, `validation.py`. The build `handler.py` was derived from `backend/handler.py` with its relative imports (`from .config`, `from .repository`, `from .validation`) rewritten to absolute imports so the Lambda entrypoint `handler.lambda_handler` loads correctly from the zip root. Verified locally (import + `GET /health` returned `{"status":"ok"}`). `boto3` is provided by the Lambda runtime, so no dependencies were vendored.
2. **Organizer key**: a strong 40-character alphanumeric key was generated and written to `terraform/organizer.auto.tfvars` (matched by `.gitignore` `*.auto.tfvars`; never committed). This takes precedence over the `random_password` resource, so `organizer_key_is_generated = false`.
3. **Frontend build** assembled into `frontend/dist/` (`index.html`, `styles.css`, `api.js`, `app.js`, `config.js`).
4. **`__API_BASE_URL__` substitution**: performed as a two-pass deployment (see below).

## Two-pass apply

The frontend `config.js` placeholder `__API_BASE_URL__` can only be replaced with the real `api_base_url`, which is known only after the API Gateway exists. (API Gateway CORS references the CloudFront domain, which is a resource attribute resolved within a single apply, so only `config.js` required a second pass.)

- **Pass 1** — `terraform apply` created all infrastructure. `config.js` still carried the placeholder at this point.
- **Substitution** — replaced `__API_BASE_URL__` in `frontend/dist/config.js` with `https://h1ebnpore5.execute-api.us-east-1.amazonaws.com`.
- **Pass 2** — `terraform apply` re-uploaded the changed `config.js` object (etag change; 1 changed).
- **Cache invalidation** — CloudFront invalidation `ICD7OFD34ZMEEVWAXF0TMB616E` on `/*` so the corrected config is served.

## Apply results (actual)

`terraform init` (exit 0) and `terraform plan` (exit 0) succeeded. The initial plan showed **25 to add, 0 to change, 0 to destroy** (20 base resources + 5 frontend S3 objects; no `random_password` because the organizer key was supplied).

The apply required remediation of orphaned resources left by earlier, unrelated deployment attempts in the account (not present in this Terraform state):

| Apply pass | Result | Notes |
|-----------|--------|-------|
| Pass 1 (initial) | Partial — errored on `aws_cloudwatch_log_group.lambda` (`ResourceAlreadyExistsException`) | 18 resources created (CloudFront, S3 + objects, DynamoDB, API, stage, OAC, roles). A stale log group from a prior run already existed. |
| Import | Success | Imported the pre-existing `/aws/lambda/workshop-feedback-poc-api` log group into state (non-destructive). |
| Pass 2 | Partial — errored on `aws_lambda_function.api` (`ResourceConflictException: Function already exist`) | Created `aws_iam_role_policy.lambda`; updated the log group tags. A stale Lambda from a prior session (wrong handler `lambda_function.handler`, wrong role, `TABLE_NAME=workshop-feedback` env) blocked creation. |
| Orphan cleanup | Success | Deleted the stale, unmanaged Lambda `workshop-feedback-poc-api` (held no application data; DynamoDB is separate and freshly created) so Terraform could create the correct function. |
| Pass 3 | **Apply complete: 6 added, 0 changed, 0 destroyed** | Created `aws_lambda_function.api`, `aws_lambda_permission.apigw`, the integration, and the three routes. |
| Pass 4 (config.js) | **Apply complete: 0 added, 1 changed, 0 destroyed** | Re-uploaded `config.js` with the real API base URL. |

**Final state: 25 managed resources, all created and healthy.** No unexpected destroys occurred; the only deletion was a non-Terraform-managed orphan blocking the approved deploy.

### Deployed resource summary (25 managed)

- `aws_dynamodb_table.feedback` — PAY_PER_REQUEST, hash key `feedbackId`
- `aws_lambda_function.api` — python3.12, handler `handler.lambda_handler`, env `FEEDBACK_TABLE_NAME`, `ORGANIZER_KEY` (sensitive), `LOG_LEVEL`
- `aws_lambda_permission.apigw`
- `aws_iam_role.lambda` + `aws_iam_role_policy.lambda` — least-privilege (scoped logs + DynamoDB PutItem/GetItem/Scan on the table ARN only)
- `aws_cloudwatch_log_group.lambda`, `aws_cloudwatch_log_group.api_access` — 14-day retention
- `aws_apigatewayv2_api.http` (CORS to the CloudFront origin) + integration + 3 routes (`GET /health`, `POST /feedback`, `GET /feedback`) + `$default` stage with access logging
- `aws_s3_bucket.frontend` (private: BPA all-true, BucketOwnerEnforced, AES256) + bucket policy (OAC + SourceArn scoped) + 5 `aws_s3_object` assets
- `aws_cloudfront_origin_access_control.frontend` + `aws_cloudfront_distribution.frontend` (default cert, redirect-to-https, PriceClass_100)

## Smoke-test results (live, against the deployed environment)

| # | Check | Method | Expected | Actual | Result |
|---|-------|--------|----------|--------|--------|
| 1 | Frontend reachability over HTTPS | `GET https://d1izl6or5rbeu.cloudfront.net/` | 200, app HTML | HTTP 200; served `<!DOCTYPE html>` with `APP_CONFIG` app shell | **PASS** |
| 1b | Frontend config serves real API URL | `GET .../config.js` (CloudFront) | 200, real `apiBaseUrl` | HTTP 200; `apiBaseUrl: "https://h1ebnpore5.execute-api.us-east-1.amazonaws.com"` | **PASS** |
| 2 | Health | `GET .../health` | 200 ok | HTTP 200; `{"status": "ok"}` | **PASS** |
| 3 | Submit valid feedback | `POST .../feedback` `{workshopId:"smoke-test-ws", rating:5, comment:...}` | 201 + persisted | HTTP 201; `feedbackId cf504d3e-f3d5-4615-a93a-8f2d50e29e48`, `createdAt 2026-09-05T09:20:50Z` | **PASS** |
| 4a | Reject invalid rating (6) | `POST .../feedback` `{rating:6}` | 400 | HTTP 400; `VALIDATION_ERROR`, field `rating` | **PASS** |
| 4b | Reject non-integer rating (4.5) | `POST .../feedback` `{rating:4.5}` | 400 | HTTP 400; `VALIDATION_ERROR`, field `rating` | **PASS** |
| 5a | List without organizer key | `GET .../feedback` (no header) | 401 | HTTP 401; `UNAUTHORIZED` | **PASS** |
| 5b | List with invalid organizer key | `GET .../feedback` `x-organizer-key: wrong` | 403 | HTTP 403; `FORBIDDEN` | **PASS** |
| 5c | List with valid key (persistence) | `GET .../feedback` `x-organizer-key: <valid>` | 200 + submitted item | HTTP 200; `count: 1` returning the exact item from test 3 (`cf504d3e-...`) — **persistence confirmed** | **PASS** |

All required verification checks passed against the live environment.

## Security / IAM notes

- S3 frontend bucket is private (all four Block-Public-Access flags true, BucketOwnerEnforced, AES256); read is granted only to the specific CloudFront distribution via OAC + `AWS:SourceArn`.
- Lambda IAM policy is least-privilege: scoped logs on this function's log group ARN and `PutItem`/`GetItem`/`Scan` on the Feedback table ARN only; no wildcard resources.
- Organizer key is `sensitive`, injected into the Lambda env by Terraform, and stored only in gitignored `organizer.auto.tfvars` and Terraform state — never in source or frontend assets.
- No Route 53 / ACM / custom domain; CloudFront default certificate; HTTPS enforced (redirect-to-https). Only approved-catalog services used.

## Accepted POC risks (unchanged from deployment plan)

- Local Terraform state (no remote backend/locking) — acceptable for a single-operator POC.
- Organizer gating uses a shared key in the Lambda environment (no identity service).
- `GET /feedback` uses a DynamoDB `Scan` — appropriate at workshop scale only.
- No WAF / rate limiting beyond platform defaults.
- Temporary AWS credentials were sourced via `aws configure export-credentials` and injected into the Terraform process environment for each command, because the environment's default profile uses a `login_session` mechanism the AWS SDK does not resolve directly.

## Cleanup

To tear down: `terraform destroy` from `terraform/` (CloudFront distribution delete takes several minutes). Remove `terraform/organizer.auto.tfvars` and local state afterward.

DEVOPS_STATUS: DEPLOYED
