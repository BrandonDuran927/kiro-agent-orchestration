# QA Validation Report — Workshop Feedback Portal (POC)

Status: Validation (RERUN after F-01 remediation)
Owner: QA Engineer
Phase: VALIDATION (SDLC_WORKFLOW.md, Workflow A)
Sources of truth: `docs/requirements.md` (AC-001..AC-013), `docs/api-contract.md`, `docs/data-model.md`, `docs/architecture.md`, `WORKSHOP_CONSTRAINTS.md`
Artifacts reviewed: `backend/`, `frontend/`, `terraform/`, `tests/`, `docs/backend-implementation-summary.md`, `docs/frontend-implementation-summary.md`

---

## 0. Rerun summary (F-01 remediation)

Trigger: Remediation of finding **F-01** — the Lambda environment variable in `terraform/lambda.tf` was renamed from `FEEDBACK_TABLE` to `FEEDBACK_TABLE_NAME` to match the name expected by `backend/config.py`.

Re-verification performed on rerun:

- **Env-var name match — CONFIRMED.** `terraform/lambda.tf` (line 109) now injects `FEEDBACK_TABLE_NAME = aws_dynamodb_table.feedback.name`, which matches `backend/config.py` (line 18) `TABLE_NAME_ENV = "FEEDBACK_TABLE_NAME"`. A repo-wide scan (`*.py`, `*.tf`, `*.js`) found **zero** remaining references to the old `FEEDBACK_TABLE` name; all references consistently use `FEEDBACK_TABLE_NAME`. At runtime the deployed Lambda will now resolve a non-empty `table_name`, so the repository targets the provisioned DynamoDB table rather than failing safe with an empty name.
- **Backend suite re-run — GREEN.** `python -m pytest` → **50 passed, 0 failed, 0 skipped** (see §3). No regressions.
- **Acceptance criteria AC-001..AC-013 — ALL STILL PASS.** The rename is a Terraform-only wiring fix; it does not alter application logic. Business-logic ACs remain covered by the green suite, and the infra-verified ACs (AC-011/AC-012) are unaffected by the env-var change. The fix directly strengthens the AC-001/AC-002 persistence path in the deployed environment (correct table name now supplied). No AC regressed.

Rerun gate: **PASS**.

---

## 1. Scope

Requirements-traceability and risk-based QA of the integrated POC against the approved requirements, the API contract, the data model, and workshop engineering constraints. Validation covers:

- Every acceptance criterion AC-001..AC-013.
- Submission happy path and persisted-field completeness.
- Rating boundary handling (1–5 accepted; 0/6/negative and non-integer rejected).
- Required `workshopId`; optional and length-bounded `comment`.
- Organizer-key auth behavior (401 missing / 403 invalid / 200 valid).
- Health endpoint.
- Attendee flow never exposes other attendees' feedback.
- Frontend UI states (IDLE / LOADING / SUCCESS / ERROR / EMPTY).
- Verifiable non-functional constraints (S3 privacy, HTTPS/no-custom-domain, no embedded secrets).

Out of scope for this gate (verified at DESIGN/DEPLOYMENT/VERIFICATION per requirements §10 note): live deployment smoke tests, actual DynamoDB round-trip against a provisioned table, and the fixed platform constraints validated during design/security.

## 2. Method

- **Static review** of backend (`handler.py`, `validation.py`, `repository.py`, `config.py`) against the API contract and data model, field by field.
- **Static review** of frontend (`index.html`, `app.js`, `api.js`, `config.js`) for request/response conformance, UI states, safe rendering, and secrets.
- **Terraform review** of `s3_cloudfront.tf` to substantiate AC-011 and AC-012 (infrastructure-level ACs).
- **Dynamic test execution**: ran the backend suite with `python -m pytest`. Business logic is exercised via an injected in-memory repository and a fixed clock, so no AWS credentials or network are required.
- **Traceability mapping** of each AC to concrete code paths and automated tests.

## 3. Test execution results

Command (from project root):

```
python -m pytest -v
```

Actual result (rerun after F-01 remediation):

```
platform win32 -- Python 3.12.10, pytest-9.1.1, pluggy-1.6.0
configfile: pytest.ini
testpaths: tests
collected 50 items

tests\test_feedback_list.py .........        [ 18%]
tests\test_feedback_submit.py .......        [ 32%]
tests\test_feedback_validation.py ........   [ 80%]
tests\test_health.py ...                     [ 86%]
tests\test_routing_and_config.py .......     [100%]

50 passed in 0.08s
```

**Summary: 50 passed, 0 failed, 0 skipped. Exit code 0.**

Coverage by module:
- `test_health.py` (3) — health 200, no-auth, trailing-slash normalization.
- `test_feedback_submit.py` (7) — happy path + persisted fields, no-comment optional, empty-string comment, boundary ratings 1 & 5, unknown-field drop, workshopId trim, comment at max length.
- `test_feedback_validation.py` (24) — missing/null rating, out-of-range (0/6/-1/100), non-integer (3.5/4.0/"4"/bool/list/dict), missing/empty/whitespace/non-string/oversize workshopId, comment >1000, multi-error, malformed JSON, empty body, persistence-failure 500.
- `test_feedback_list.py` (9) — 401 missing / 403 invalid / 200 valid, case-insensitive header, empty collection, comment-null, Decimal→int coercion, empty-server-key denial, scan-failure 500.
- `test_routing_and_config.py` (7) — unknown route/path 404, POST to /health 404, REST v1 event shape, config env read/defaults, `lambda_handler` alias.

## 4. Per-AC traceability

| AC | Requirement | Evidence (code / test) | Result |
|----|-------------|------------------------|--------|
| AC-001 | Submit id+rating(4)+comment → success + persist | `handle_create_feedback` returns 201; `test_submit_valid_feedback_returns_201_and_persists` | PASS |
| AC-002 | Stored record has workshopId, rating, comment, timestamp | Item build in `handler.py`; server-generated `feedbackId`/`createdAt`; same test asserts stored fields | PASS |
| AC-003 | No rating → rejected, no persist | `validate_feedback` rating-required; `test_missing_rating_rejected`, `test_null_rating_rejected` (assert `repo.items == []`) | PASS |
| AC-004 | Rating 0/6 (out of range) → rejected | `RATING_MIN/MAX` check; `test_out_of_range_rating_rejected[0,6,-1,100]`, `test_non_integer_rating_rejected` | PASS |
| AC-005 | Empty workshopId → rejected | trim + non-empty check; `test_missing_workshop_id_rejected`, `test_empty_or_whitespace_workshop_id_rejected` | PASS |
| AC-006 | Comment > max (1000) → rejected | `COMMENT_MAX_LEN` check; `test_comment_over_max_length_rejected` (and `test_comment_at_max_length_accepted` for boundary) | PASS |
| AC-007 | Valid rating + id, no comment → accepted | comment optional; `test_submit_without_comment_persists_and_returns_null_comment`, `test_empty_string_comment_treated_as_no_comment` | PASS |
| AC-008 | Organizer retrieval returns id/rating/comment/timestamp | `handle_list_feedback` + `_to_api_item`; `test_valid_organizer_key_returns_items`, `test_item_without_comment_returned_as_null` | PASS |
| AC-009 | Attendee flow never shows others' feedback | GET /feedback gated (401/403 leak no data); frontend submission never calls listFeedback; `test_missing_organizer_key_returns_401`/`_invalid_..._403` assert `"items" not in body` | PASS |
| AC-010 | Health returns healthy response | `handle_health` → `{"status":"ok"}`; `test_health_returns_200_ok` | PASS |
| AC-011 | Frontend loads over HTTPS via generated distribution URL, no custom domain | `terraform/s3_cloudfront.tf`: CloudFront `viewer_protocol_policy = redirect-to-https`, `cloudfront_default_certificate = true`, no ACM/Route53; static assets served via `*.cloudfront.net` | PASS (design/infra-verified; live check deferred to VERIFICATION) |
| AC-012 | Frontend object storage not directly public | `aws_s3_bucket_public_access_block` all four flags true; `BucketOwnerEnforced`; bucket policy limits `s3:GetObject` to the CloudFront OAC via `AWS:SourceArn` | PASS (infra-verified) |
| AC-013 | No AWS credentials/secrets in assets or source | `frontend/config.js` holds only `__API_BASE_URL__` placeholder; organizer key entered at runtime, never stored; backend reads `ORGANIZER_KEY` from env (`config.py`), never hardcoded or returned | PASS |

All 13 acceptance criteria are covered and pass. No gaps identified.

## 5. Contract & data-model conformance checks

- **Error shape** `{error:{code,message,details?}}` implemented consistently in `_error`; validation returns `details[]` with field/issue; internal errors return generic messages with no stack traces (`test_persistence_failure_returns_500_generic` asserts no "Traceback").
- **Status codes** match contract §4: 200 (health/list), 201 (create), 400 (VALIDATION_ERROR / MALFORMED_REQUEST), 401 (UNAUTHORIZED), 403 (FORBIDDEN), 404 (NOT_FOUND), 500 (INTERNAL_ERROR).
- **Field names/types** (`feedbackId`, `workshopId`, `rating`, `comment`, `createdAt`) align across API contract, data model, backend response, and frontend rendering. `comment` is `null` in responses and omitted from the stored item when absent — matches data-model §2.
- **`rating` integer-ness**: `_is_strict_int` rejects `bool` and floats (`4.0`), matching the contract's "no fractional part" rule.
- **Timestamp**: `createdAt` is server-generated ISO-8601 UTC with trailing `Z` (`_iso_utc`), matching AC-002 / FR-006.
- **Organizer auth**: header `X-Organizer-Key` matched case-insensitively; constant-time `hmac.compare_digest`; empty server-side key denies all (`test_no_server_key_configured_denies_access`). Matches contract §2.3 and A-005.
- **DynamoDB access patterns**: only `PutItem` (AP-1) and paginated `Scan` (AP-2); no GSIs, no update/delete — matches data-model §3–4 and NFR-009.
- **Frontend UI states** (IDLE/LOADING/SUCCESS/ERROR/EMPTY) all present in `app.js`; untrusted data rendered exclusively via `textContent`/`createElement` (no `innerHTML`) — XSS-safe; server-side field errors mapped back to inputs.

## 6. Constraint conformance (WORKSHOP_CONSTRAINTS.md)

- AWS-only, Terraform-provisioned, Python backend, framework-less static frontend — confirmed in `backend/`, `frontend/`, `terraform/`.
- Approved service catalog only (S3, CloudFront, API Gateway, Lambda, DynamoDB, CloudWatch, IAM); no Route 53/ACM/EC2/VPC observed in `s3_cloudfront.tf`.
- Frontend storage private (AC-012), least-privilege bucket policy, no embedded secrets (AC-013).

## 7. Defects

None. No blocking, major, or minor functional defects were identified. All acceptance criteria pass and the full automated suite is green.

(No `REMEDIATION_OWNER` lines are required because there are no blocking defects to route.)

## 8. Observations (non-blocking, no action required for POC)

These are consistent with documented accepted POC risks in `docs/requirements.md` §11; they are recorded for transparency and do **not** affect the gate:

- **OBS-1** — Shared-key organizer gate (A-005 / R-001) is weaker than identity-based auth. Accepted POC risk.
- **OBS-2** — Unauthenticated, unthrottled submissions (R-002) and no comment moderation (R-003). Accepted POC risk.
- **OBS-3** — `GET /feedback` uses `Scan` (ADR-4); appropriate at workshop scale, not intended to scale beyond the POC.
- **OBS-4** — Live DynamoDB round-trip and the CloudFront/S3 runtime behavior (AC-011/AC-012) are validated by design/Terraform review here and are confirmed against the live environment in the DevOps VERIFICATION step; that is by design per the workflow, not a QA gap.

## 9. Conclusion

The integrated Workshop Feedback Portal POC satisfies all approved acceptance criteria (AC-001..AC-013), conforms to the API contract and data model, respects the workshop engineering constraints, and passes its full automated backend suite (50/50). No blocking defects.

On this rerun, finding **F-01** is confirmed remediated: the Lambda env-var name in `terraform/lambda.tf` (`FEEDBACK_TABLE_NAME`) now matches `backend/config.py`, with no stale references remaining. Nothing regressed — all 13 acceptance criteria still hold and the suite remains green.

QA_STATUS: PASS
