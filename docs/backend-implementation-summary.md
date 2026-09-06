# Backend Implementation Summary — Workshop Feedback Portal (POC)

Status: Implemented
Owner: Backend Developer
Gates honored: `BA_STATUS: PASS`, `ARCH_STATUS: PASS`
Sources of truth: `WORKSHOP_CONSTRAINTS.md`, `docs/requirements.md`, `docs/architecture.md`, `docs/api-contract.md`, `docs/data-model.md`

## 1. Approved scope implemented

A single, path-routed Python AWS Lambda handler behind an API Gateway HTTP API (v2), persisting to one DynamoDB table (`feedbackId` partition key), per architecture ADR-2 and the data model. No API or persistence scope was expanded. No new AWS services introduced. No IAM/Terraform/frontend changes (owned by DevOps/Frontend).

Endpoints:

- `GET /health` — returns `{"status":"ok"}`, no auth (FR-010, AC-010).
- `POST /feedback` — server-side validation, generate `feedbackId`+`createdAt`, `PutItem`, return 201 (FR-002–FR-006).
- `GET /feedback` — gated by `X-Organizer-Key` header (401 missing / 403 invalid), `Scan`, return items+count (FR-007–FR-009).
- Unknown route → controlled `404 NOT_FOUND`.

## 2. Files created

Backend (`backend/`):
- `__init__.py` — package marker.
- `config.py` — env-based config (`FEEDBACK_TABLE_NAME`, `ORGANIZER_KEY`); no hardcoded secrets/resource names.
- `validation.py` — server-authoritative validation (BR-001–BR-005, BR-008).
- `repository.py` — `FeedbackRepository` protocol + `DynamoDBFeedbackRepository` (lazy `boto3`, `PutItem`, paginated `Scan`).
- `handler.py` — event parsing, routing, endpoint logic, HTTP/error shaping; `lambda_handler` alias.
- `requirements.txt` — runtime dependency reference (`boto3`, provided by Lambda runtime).

Tests (`tests/`):
- `conftest.py` — fixtures (fake in-memory repo, config, fixed clock); sets up import paths.
- `backend_test_helpers.py` — API Gateway event builders / response parsing.
- `test_health.py`, `test_feedback_submit.py`, `test_feedback_validation.py`, `test_feedback_list.py`, `test_routing_and_config.py`.

Root: `pytest.ini` (pytest config; `--import-mode=importlib`, `pythonpath`).

## 3. Endpoints / behaviors implemented

### POST /feedback
- Parses JSON body; malformed JSON → `400 MALFORMED_REQUEST`. Empty/absent body → `400 VALIDATION_ERROR` listing missing required fields.
- Validation: `workshopId` required, trimmed, non-empty, ≤200 chars; `rating` required strict integer 1–5 (rejects float incl. `4.0`, string `"4"`, bool, null, out-of-range); `comment` optional ≤1000 chars, empty string/null/omitted = no comment. Unknown fields ignored.
- On success: server-generated UUIDv4 `feedbackId` and ISO-8601 UTC `createdAt` (e.g. `2026-09-05T08:34:33Z`); `PutItem`; `comment` attribute omitted in store when absent; returns `201` with `comment: null` when none.
- Persistence error → `500 INTERNAL_ERROR` (generic message, exception logged, nothing leaked).

### GET /feedback
- Missing `X-Organizer-Key` → `401 UNAUTHORIZED`; present-but-wrong → `403 FORBIDDEN`; neither returns any data (AC-009). Header match is case-insensitive; key comparison uses `hmac.compare_digest` (constant-time). Empty server-side key denies all access.
- Valid key → `Scan` (paginated), returns `{items, count}`; each item has `feedbackId`, `workshopId`, `rating` (Decimal→int coerced), `comment` (null when absent), `createdAt`. Empty table → `{"items":[],"count":0}`.

### GET /health
- Returns `200 {"status":"ok"}`, no auth, trailing slash tolerated.

## 4. Validation & persistence decisions

- Validation centralized in `validation.py`, transport/routing in `handler.py`, persistence isolated behind a `FeedbackRepository` protocol — keeps business logic testable without AWS.
- `bool` explicitly rejected as `rating` (Python `bool` subclasses `int`); floats like `4.0` rejected (contract requires no fractional part).
- `boto3` imported lazily inside the repository so unit tests need neither `boto3` nor credentials/network.
- Config read from environment only; the organizer key is never in source or returned to clients.
- Access patterns limited to the approved AP-1 (`PutItem`) and AP-2 (`Scan`); no indexes, no extra reads.

## 5. Tests added

50 tests across health, submit/happy-path+persistence, validation/boundary, organizer auth/listing, and routing/config. Categories: contract/handler, validation boundary, persistence interaction (fake repo), privacy/data-minimization (unknown fields dropped, comment omission), error-shape, unknown-route, and event-shape (HTTP API v2 + REST v1 fallback).

Key coverage: happy path + persisted fields (AC-001/AC-002); no-comment optional (AC-007); missing rating (AC-003); rating 0/6/negative and non-integer 3.5/4.0/"4"/bool (AC-004, BR-001/002); missing/empty/whitespace/oversize workshopId (AC-005, BR-004); comment >1000 (AC-006); comment at 1000 accepted; organizer missing/invalid/valid (401/403/200, FR-008/BR-006/AC-009); health (AC-010); 500 on persistence/scan failure without leaking internals.

## 6. Commands executed and actual results

```
python -m pytest      → 50 passed in 0.26s
python -m compileall backend  → OK (no errors)
```

Environment note: `pytest 9.1.1` was installed (`pip install --user pytest`) because no runner was present; `boto3` is not installed locally and is intentionally not required by the tests (lazy import; provided by the Lambda runtime). Tests use `--import-mode=importlib` and an explicit `pythonpath` to avoid an unrelated `tests` package on `sys.path`.

## 7. Contract / AC mapping

| Behavior | Contract | Requirements / AC |
|----------|----------|-------------------|
| `GET /health` → `{"status":"ok"}` | api-contract 2.1 | FR-010, AC-010 |
| `POST /feedback` fields & validation | api-contract 2.2 | FR-002/FR-003, BR-001–BR-005, BR-008, AC-003–AC-006 |
| `POST /feedback` persist + confirm (server id/timestamp) | api-contract 2.2 | FR-004, FR-006, AC-001, AC-002, AC-007 |
| `POST /feedback` reject → no persist | api-contract 2.2 | FR-005, AC-003–AC-006 |
| `GET /feedback` gating (401/403) | api-contract 2.3 | FR-008, BR-006, A-005, AC-009 |
| `GET /feedback` list fields | api-contract 2.3 | FR-007, FR-009, AC-008 |
| Error shape `{error:{code,message,details?}}` | api-contract 1 | FR-005 |
| No embedded secrets (env-only key) | api-contract 2.3 | NFR-007, AC-013 |
| DynamoDB `PutItem`/`Scan`, PK `feedbackId` | data-model AP-1/AP-2 | FR-004, FR-007, NFR-012 |

## 8. Known limitations / accepted risks

- Shared-key organizer gate (ADR-3/R-001), unauthenticated submissions (R-002), no content moderation (R-003) — accepted POC risks per requirements.
- `Scan` for listing (ADR-4) — acceptable at workshop scale; not intended to scale.
- `boto3` not installed in this local environment, so the DynamoDB path is exercised via an injected fake, not a live table (live verification is DevOps's VERIFICATION step).

## 9. Infrastructure actions required from DevOps (documented, not implemented)

- DynamoDB `Feedback` table, `PAY_PER_REQUEST`, PK `feedbackId` (S).
- Lambda env vars: `FEEDBACK_TABLE_NAME`, `ORGANIZER_KEY` (sensitive Terraform input; not in source).
- Lambda handler entry: `backend.handler.lambda_handler` (packaging path per DevOps).
- Least-privilege IAM for the Lambda role: `dynamodb:PutItem` and `dynamodb:Scan` scoped to the table ARN, plus its CloudWatch Logs group. (`GetItem` reserved/unused.)
- API Gateway HTTP API routes: `GET /health`, `POST /feedback`, `GET /feedback`; CORS for the CloudFront origin.

BACKEND_STATUS: PASS
