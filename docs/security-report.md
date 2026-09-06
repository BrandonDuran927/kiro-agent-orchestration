# Security Review Report — Workshop Feedback Portal (POC)

Status: Validation — RERUN after F-01 remediation (env var rename)
Owner: Security Reviewer (independent of implementation)
Sources of truth: `WORKSHOP_CONSTRAINTS.md`, `docs/requirements.md`, `docs/architecture.md`, `docs/api-contract.md`, `docs/data-model.md`
Artifacts reviewed: `backend/`, `frontend/`, `terraform/`, implementation summaries (`docs/*-implementation-summary.md`)
Review type: Risk-based security review across frontend, backend, data flow, IAM, and Terraform/IaC. No implementation was modified.

---

## 0. Rerun summary (post-F-01 remediation)

This is a re-validation triggered by the F-01 remediation. A Terraform change renamed the Lambda environment variable from `FEEDBACK_TABLE` to `FEEDBACK_TABLE_NAME` in `terraform/lambda.tf` to match the backend contract.

**F-01 re-verification — RESOLVED:**
- `terraform/lambda.tf` now sets `FEEDBACK_TABLE_NAME = aws_dynamodb_table.feedback.name` in the Lambda `environment.variables` block. Confirmed by direct read of the file.
- No bare `FEEDBACK_TABLE` env key remains in the Terraform source. The only occurrences of the token `FEEDBACK_TABLE` are as the substring of the corrected `FEEDBACK_TABLE_NAME` name; there is no standalone `FEEDBACK_TABLE = ...` assignment.
- The backend contract is now aligned end-to-end: `backend/config.py` reads `TABLE_NAME_ENV = "FEEDBACK_TABLE_NAME"`; the injected key matches. `ORGANIZER_KEY` and `LOG_LEVEL` env keys are unchanged and still correct.

**No new security issue introduced by the fix:**
- The change is a single key rename inside the environment block. The value source is unchanged (`aws_dynamodb_table.feedback.name` — a non-secret resource name, not a credential).
- IAM policy, S3/OAC, CORS, organizer-key handling, and error paths are untouched by the diff. No new environment variable, permission, service, or public exposure was added.
- No secret was introduced into the environment block (table name is non-sensitive; the organizer key remains sourced from the `sensitive` variable / generated `random_password`).

**Re-confirmed controls (unchanged, still hold):** no embedded secrets (frontend/Terraform/backend); private S3 + Block Public Access (all four flags) + OAC with `AWS:SourceArn`; least-privilege, resource-scoped IAM (no wildcards); safe organizer-key handling (in-memory only, `X-Organizer-Key`, `hmac.compare_digest`, fail-closed); non-leaking generic `500 INTERNAL_ERROR`; CORS scoped to the CloudFront origin only; approved AWS services only; HTTPS enforced end to end (CloudFront redirect-to-HTTPS, API Gateway HTTPS-only).

**Rerun gate:** PASS. F-01 resolved; no new findings. Remaining F-02/F-03/F-04 are unchanged Low/Informational and non-blocking.

---

## 1. Scope and architecture reviewed

The reviewed system is the approved two-path serverless topology:

- **Static delivery path:** browser → CloudFront (default `*.cloudfront.net`, HTTPS) → private S3 (OAC-signed) for the attendee/organizer static SPA.
- **API path:** browser JavaScript → API Gateway HTTP API (default `execute-api` URL, HTTPS) → single path-routed Python Lambda → DynamoDB (`PAY_PER_REQUEST`).
- Observability via CloudWatch (Lambda log group + API access log group). Access control via IAM (Lambda execution role) plus an application-level shared organizer key.

Only approved-catalog AWS services are present (S3, CloudFront, API Gateway, Lambda, DynamoDB, CloudWatch, IAM). Terraform-internal `random`/`archive` providers are provisioning helpers, not AWS services.

Endpoints reviewed against `docs/api-contract.md`:

| Method | Path | Auth | Notes |
|--------|------|------|-------|
| GET | `/health` | none | Returns `{"status":"ok"}` |
| POST | `/feedback` | none (A-001) | Server-side validation, write-once persist |
| GET | `/feedback` | organizer shared key (`X-Organizer-Key`) | Gated in Lambda |

---

## 2. Assets and trust boundaries

| Asset | Sensitivity | Boundary |
|-------|-------------|----------|
| Frontend static assets (S3) | Low (public content, no secrets) | Private S3; readable only via CloudFront OAC |
| Feedback records (DynamoDB) | Low–moderate (no PII by design, BR-007; free-text comments unmoderated, R-003) | Reachable only by the Lambda execution role |
| Organizer shared key | Moderate (gates review capability) | Terraform `sensitive` var → Lambda env var; never in source/frontend |
| Lambda execution role | Privilege boundary | Least-privilege inline policy scoped to table + log-group ARNs |
| CloudWatch logs | Low | Must not contain the organizer key or raw PII |

Trust boundaries crossed:

1. **User → public edge (CloudFront/API Gateway):** internet-facing, HTTPS only. CloudFront `viewer_protocol_policy = redirect-to-https`; API Gateway default endpoint is HTTPS-only. (NFR-011 satisfied.)
2. **Browser → API:** all input is untrusted; validated server-side and authoritatively in Lambda (BR-008).
3. **Public edge → private storage:** S3 is never public; OAC + `AWS:SourceArn` bucket policy restrict reads to the specific distribution. (NFR-005 / AC-012 satisfied.)
4. **Compute → persistence:** DynamoDB reachable only via the scoped Lambda role. (NFR-006.)
5. **Organizer gate:** enforced inside Lambda via constant-time key comparison. (FR-008 / A-005.)
6. **Deployment/config boundary:** organizer key injected by Terraform; state and `*.tfvars` are git-ignored.

---

## 3. Checks performed and results

### Frontend
- **No embedded secrets / credentials:** PASS. `frontend/config.js` carries only the non-secret `apiBaseUrl` placeholder (`__API_BASE_URL__`). No AWS keys, no organizer key. (NFR-007, AC-013)
- **Organizer key handling:** PASS. Key is a runtime password-field input, held in memory only for the request, sent solely as the `X-Organizer-Key` header (`api.js` `listFeedback`), never persisted/logged.
- **Untrusted-content rendering (XSS):** PASS. All API/user values rendered exclusively via `textContent` / `createElement`; no `innerHTML`/`insertAdjacentHTML`/string-built markup anywhere (`app.js` `buildFeedbackCard`, `safeString`).
- **Client vs server validation:** PASS. Client validation is convenience only; server is authoritative and its messages take precedence.
- **PII:** PASS. Only workshop id, rating, optional comment collected/displayed (BR-007, A-004).
- **HTTPS:** PASS. All calls target the HTTPS API Gateway URL; assets served over CloudFront HTTPS.

### Backend / API
- **Server-side input validation matches contract:** PASS. `validation.py` enforces `workshopId` (required, trimmed, ≤200), `rating` (strict integer 1–5, rejects bool/float/string/null/out-of-range), `comment` (optional, ≤1000). Rejections return `400 VALIDATION_ERROR`; nothing persisted (FR-003/FR-005, BR-001–BR-005, BR-008).
- **Fail-safe request parsing:** PASS. Malformed JSON → `400 MALFORMED_REQUEST`; empty body → validation error, not a crash.
- **Server-owned fields not client-forgeable:** PASS. `feedbackId` (UUIDv4) and `createdAt` (ISO-8601 UTC) generated server-side; unknown client fields ignored (not persisted). No client-supplied id/timestamp is trusted.
- **Organizer key — safe handling & constant-time compare:** PASS. `handler._keys_match` uses `hmac.compare_digest`; empty server-side key denies all access (fail-closed). Missing header → 401, wrong key → 403; neither returns any data (AC-009).
- **Error handling does not leak internals:** PASS. Unexpected/persistence errors return generic `500 INTERNAL_ERROR`; stack traces go to CloudWatch via `logger.exception`, never to the client.
- **Logging avoids sensitive data:** PASS. Log lines record `feedbackId`, `workshopId`, `rating`, and `hasComment` (boolean) — not raw comment content and not the organizer key.
- **Data access scope:** PASS. Only AP-1 (`PutItem`) and AP-2 (`Scan`) used; no reads exposed to attendees.

### Infrastructure / IAM (Terraform)
- **Only approved services:** PASS. No EC2/ECS/EKS/ELB/VPC/NAT/Route 53/ACM present.
- **S3 private + OAC:** PASS. `aws_s3_bucket_public_access_block` all four flags true; `BucketOwnerEnforced`; SSE (AES256); bucket policy grants only `s3:GetObject` to `cloudfront.amazonaws.com` conditioned on `AWS:SourceArn = distribution ARN`. (NFR-005, AC-012)
- **HTTPS enforced:** PASS. CloudFront redirect-to-HTTPS + default certificate; API Gateway HTTPS-only default endpoint. No custom domain/ACM (NFR-004).
- **CORS scoped:** PASS. API `cors_configuration` allows only `https://<cloudfront-domain>` origin, methods `GET/POST/OPTIONS`, headers `content-type`/`x-organizer-key`. Not a primary control, but appropriately narrow (no `*`).
- **Least-privilege IAM:** PASS (with a minor hardening note, F-02). Lambda assume-role limited to `lambda.amazonaws.com`; inline policy scoped to the specific log-group ARN and the specific DynamoDB table ARN. No wildcard resources; no admin/deploy privileges on the app role.
- **No embedded secrets in Terraform:** PASS. Organizer key is a `sensitive` variable (or generated `random_password`); `.gitignore` excludes state and `*.tfvars`; `example.tfvars` contains no real value.
- **Cleanable/temporary resources:** PASS. Single root module, fully removable via `terraform destroy`; log-group retention bounded.

### Data protection / privacy
- **Data minimization:** PASS. Persisted fields match the approved data model exactly; no PII fields.
- **Response exposure:** PASS. `GET /feedback` returns only approved fields to an authenticated organizer; attendee flow never calls it.

---

## 4. Findings

No Critical or High severity findings were identified. No mandatory security constraint is violated. The findings below are Low / Informational and are **non-blocking** for the security gate.

### F-01 — Lambda environment variable name mismatch (`FEEDBACK_TABLE` vs `FEEDBACK_TABLE_NAME`) — RESOLVED (rerun)
- **Severity:** Low (security), functional-availability impact
- **Status:** RESOLVED — verified in this rerun.
- **Affected component:** `terraform/lambda.tf` (env var block) vs `backend/config.py`
- **Original evidence:** Terraform previously injected `FEEDBACK_TABLE = aws_dynamodb_table.feedback.name`, but the backend reads `os.environ.get("FEEDBACK_TABLE_NAME", "")` (`TABLE_NAME_ENV = "FEEDBACK_TABLE_NAME"`). The backend implementation summary and architecture §7 specify `FEEDBACK_TABLE_NAME`.
- **Remediation applied:** `terraform/lambda.tf` now sets `FEEDBACK_TABLE_NAME = aws_dynamodb_table.feedback.name`. Re-verified: the env key matches the backend contract, no bare `FEEDBACK_TABLE` assignment remains, and no new security issue was introduced (value is a non-secret resource name; IAM/S3/CORS/auth paths untouched).
- **Threat/impact:** Was not a confidentiality/integrity/authz weakness — the organizer-gate env var (`ORGANIZER_KEY`) matched on both sides throughout, so access control was never affected. The prior availability defect (empty table name → failing `PutItem`/`Scan` → generic `500 INTERNAL_ERROR`) is now corrected.
- **REMEDIATION_OWNER: devops-engineer**

### F-02 — IAM grants unused `dynamodb:GetItem` action
- **Severity:** Informational (least-privilege hardening)
- **Affected component:** `terraform/lambda.tf` (`data.aws_iam_policy_document.lambda_permissions`)
- **Evidence:** The Lambda policy grants `dynamodb:PutItem`, `dynamodb:GetItem`, `dynamodb:Scan`. The implemented access patterns are only AP-1 (`PutItem`) and AP-2 (`Scan`); `GetItem` (AP-3) is explicitly "reserved/unused" in `docs/data-model.md`.
- **Threat/impact:** Minimal. The action is resource-scoped to the single Feedback table ARN, so blast radius is confined to already-authorized data. Removing it would tighten least privilege (NFR-006) with zero functional impact. Architecture §3 (IAM) and data-model §6 also list `GetItem`, so this is consistent with the approved design and is a hardening opportunity rather than a defect.
- **Remediation (optional hardening):** Drop `dynamodb:GetItem` until AP-3 is actually required. Not required to pass the gate.
- **REMEDIATION_OWNER: devops-engineer**

### F-03 — Organizer key exposed via Terraform state and `organizer_key` output
- **Severity:** Informational (accepted POC residual risk)
- **Affected component:** `terraform/outputs.tf` (`output "organizer_key"`), Terraform state
- **Evidence:** The effective organizer key is exposed as a `sensitive` output (retrievable via `terraform output -raw organizer_key`) and, as with any Terraform-managed secret, is stored in state.
- **Threat/impact:** Low for the POC. The output is marked `sensitive` (masked in CLI/plan output) and state is local and git-ignored (`.gitignore` excludes `*.tfstate*`). This is the intended, documented mechanism to distribute the generated key out-of-band to organizers (A-005). No embedding in source or frontend occurs (NFR-007 upheld). Residual risk: anyone with read access to the state file or the deploying workstation can read the key — acceptable for a single-operator, short-lived POC.
- **Remediation:** None required for POC. Accepted residual risk. For any production follow-on, move to a managed secret store and remove the plaintext output. (Out of POC scope.)
- **REMEDIATION_OWNER: devops-engineer**

### F-04 — CloudFront maps S3 403/404 to `index.html` (200)
- **Severity:** Informational
- **Affected component:** `terraform/s3_cloudfront.tf` (`custom_error_response`)
- **Evidence:** 403 and 404 from the S3 origin return `/index.html` with HTTP 200 (SPA/static fallback).
- **Threat/impact:** None to confidentiality. The bucket remains private (OAC required for any object read); this behavior only affects how missing-path errors are presented for the static site and does not expose S3 listing or objects outside OAC. Documented and benign.
- **Remediation:** None. Accepted.
- **REMEDIATION_OWNER: devops-engineer**

---

## 5. Accepted limitations / residual risks

These are pre-approved in `docs/requirements.md` §11 and the architecture ADRs; they do not violate any mandatory constraint and are acceptable for the stated POC scope:

- **R-001 / ADR-3 — Shared-key organizer gate:** weaker than identity-based authz, but the approved catalog forbids an identity service. Implemented safely (env-var key, constant-time compare, fail-closed). Accepted.
- **R-002 — Unauthenticated/duplicate submissions:** no rate limiting/DDoS beyond platform defaults. Accepted for an internal, short-lived workshop.
- **R-003 — No content moderation:** free-text comments are length-bounded and validated but not moderated. Rendered XSS-safe via `textContent`. Accepted.
- **R-004 — No retention/backup:** data exists only for the POC lifetime and is removed at `terraform destroy`. Accepted.
- **A-001 — Anonymous attendees:** no PII collected (BR-007). Accepted and privacy-positive.

---

## 6. Remediation ownership summary

| Finding | Severity | Blocking? | Owner |
|---------|----------|-----------|-------|
| F-01 env var name mismatch | Low | RESOLVED (rerun-verified) | devops-engineer |
| F-02 unused `GetItem` | Informational | No | devops-engineer |
| F-03 key in state/output | Informational | No (accepted POC risk) | devops-engineer |
| F-04 CF 403/404 → index.html | Informational | No | devops-engineer |

No blocking (Critical/High) security findings. F-01 is now resolved and rerun-verified. The remaining items are Low/Informational and do not gate the release on security grounds.

---

## 7. Constraint compliance (WORKSHOP_CONSTRAINTS.md)

| Constraint | Status | Evidence |
|------------|--------|----------|
| AWS only, Terraform-provisioned | PASS | All resources in `terraform/`; AWS-only |
| Python backend, static frontend, no framework | PASS | `python3.12` Lambda; plain HTML/CSS/JS |
| Approved service catalog only | PASS | S3/CloudFront/API GW/Lambda/DynamoDB/CloudWatch/IAM only |
| No Route 53 / ACM / custom domain | PASS | `cloudfront_default_certificate = true`; default endpoints |
| Frontend storage not directly public | PASS | Block Public Access (all) + OAC + `AWS:SourceArn` policy |
| Least privilege IAM | PASS (F-02 hardening) | Resource-scoped policies; no wildcards |
| No embedded credentials/secrets | PASS | Env-var key; no secrets in source/frontend; state git-ignored |
| Consumption/on-demand capacity | PASS | DynamoDB PAY_PER_REQUEST; Lambda/API per-request |
| Minimal footprint | PASS | Single Lambda/table/distribution, no GSIs |
| Deploy/teardown simplicity | PASS | Single root module; `terraform destroy` |
| HTTPS transport | PASS | CloudFront redirect-to-HTTPS; API GW HTTPS-only |

---

## 8. Final gate decision

No Critical or High findings. This rerun confirms F-01 is RESOLVED: `terraform/lambda.tf` now injects `FEEDBACK_TABLE_NAME` (matching `backend/config.py`), no bare `FEEDBACK_TABLE` assignment remains, and the rename introduced no new security issue. No mandatory security constraint is violated: frontend and Terraform contain no embedded AWS credentials or secrets; the organizer key is not embedded, is transported as the `X-Organizer-Key` header, and is compared in constant time with a fail-closed default; the frontend S3 bucket is private (Block Public Access + OAC); IAM is least-privilege and resource-scoped with no wildcards; server-side input validation matches the contract; error handling does not leak internals; CORS is scoped to the CloudFront origin; only approved services are used; and HTTPS is enforced end to end. The remaining findings (F-02/F-03/F-04) are Low/Informational and non-blocking.

SECURITY_STATUS: PASS
