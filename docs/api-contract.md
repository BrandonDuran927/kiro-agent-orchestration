# Workshop Feedback Portal — API Contract (POC)

Status: Design
Owner: Solution Architect
Source of truth: `docs/requirements.md`, `WORKSHOP_CONSTRAINTS.md`
Companion: `docs/architecture.md`, `docs/data-model.md`

This contract is implementation-independent. Frontend and Backend must be able to implement against it without further coordination. All endpoints are served over HTTPS via the API Gateway default (`execute-api`) URL.

---

## 1. Conventions

- **Base URL:** the API Gateway default endpoint (a Terraform output), e.g. `https://{api-id}.execute-api.{region}.amazonaws.com`. No custom domain (NFR-004).
- **Content type:** `application/json` for all request and response bodies. Requests with a body must send `Content-Type: application/json`.
- **Character encoding:** UTF-8.
- **Time format:** ISO-8601 UTC, e.g. `2026-09-05T08:34:33Z` (server-generated).
- **All validation is server-authoritative** (BR-008). Client-side checks are convenience only.
- **CORS:** the API allows the CloudFront distribution origin for the methods below.

### Standard error response shape

Every 4xx/5xx error returns:

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Human-readable explanation.",
    "details": [
      { "field": "rating", "issue": "Rating must be an integer between 1 and 5." }
    ]
  }
}
```

- `code` — stable machine-readable string (see per-endpoint tables).
- `message` — human-readable, safe to display (FR-005).
- `details` — optional array of field-level issues; present for validation errors, omitted otherwise.
- Internal/unexpected errors must **not** leak stack traces or infrastructure details in `message`.

---

## 2. Endpoints

### 2.1 `GET /health` — Service health (FR-010, AC-010)

- **Purpose:** confirm the backend is reachable and functioning; used as a deployment smoke test.
- **Auth:** none.
- **Request:** no body, no required parameters.
- **Success — 200 OK:**

```json
{ "status": "ok" }
```

- **Errors:** none expected under normal operation. A 5xx indicates the backend is unhealthy.

---

### 2.2 `POST /feedback` — Submit feedback (FR-002–FR-006)

- **Purpose:** create one feedback record (write-once; no update/delete in scope).
- **Auth:** none (attendees are unauthenticated — A-001).
- **Request body:**

| Field | Type | Required | Rules |
|-------|------|----------|-------|
| `workshopId` | string | **Yes** | Non-empty after trimming whitespace; max 200 chars. (BR-004) |
| `rating` | integer | **Yes** | Integer 1–5 inclusive. Must be a JSON number with no fractional part; reject non-integer, string, null, or out-of-range. (BR-001, BR-002, BR-003) |
| `comment` | string | No | If present and non-empty: max 1000 characters. Omitted, `null`, or empty string all mean "no comment". (BR-005) |

- **No other fields are accepted; unknown fields are ignored (not an error).**
- **No PII is requested or required** (BR-007).

**Example request:**

```json
{
  "workshopId": "aws-serverless-2026-09",
  "rating": 4,
  "comment": "Great pacing, more hands-on labs please."
}
```

- **Success — 201 Created:**

```json
{
  "feedbackId": "6f9619ff-8b86-4d01-b42d-00cf4fc964ff",
  "workshopId": "aws-serverless-2026-09",
  "rating": 4,
  "comment": "Great pacing, more hands-on labs please.",
  "createdAt": "2026-09-05T08:34:33Z",
  "message": "Feedback submitted successfully."
}
```

  - `feedbackId` and `createdAt` are **server-generated** (FR-006, AC-002). The record is persisted before the 201 is returned (FR-004).
  - When no comment was submitted, `comment` is returned as `null`.

- **Client-error responses:**

| Status | `code` | Trigger |
|--------|--------|---------|
| 400 | `VALIDATION_ERROR` | Missing/empty `workshopId` (AC-005); missing `rating` (AC-003); `rating` not an integer or outside 1–5 (AC-004); `comment` > 1000 chars (AC-006). No record persisted (FR-005). |
| 400 | `MALFORMED_REQUEST` | Body is not valid JSON, or `Content-Type` is not JSON. |
| 415 | `UNSUPPORTED_MEDIA_TYPE` | (Optional) non-JSON content type; may be folded into `MALFORMED_REQUEST` at implementer discretion. |

  On any 400, **no record is persisted** (FR-005, AC-003–AC-006). `details` should list each failing field.

- **Server-error response:**

| Status | `code` | Trigger |
|--------|--------|---------|
| 500 | `INTERNAL_ERROR` | Unexpected failure (e.g., persistence error). No partial/duplicate record guarantee beyond DynamoDB write semantics; message is generic. |

---

### 2.3 `GET /feedback` — List feedback for review (FR-007, FR-008, FR-009)

- **Purpose:** return the collected feedback records for organizer review.
- **Auth:** **required** — organizer shared access key (A-005). The attendee submission flow never calls this and never receives other attendees' feedback (BR-006, AC-009).
- **Auth mechanism:** the caller sends the organizer key in a request header:

```
X-Organizer-Key: <shared-secret>
```

  - The key value is configured server-side (Terraform-managed Lambda environment variable) and is **never** embedded in frontend assets or source (NFR-007, AC-013).
  - Comparison should be constant-time where practical.

- **Request:** no body. No query parameters required (no filtering/sorting/pagination in scope — see out-of-scope in requirements).
- **Success — 200 OK:**

```json
{
  "items": [
    {
      "feedbackId": "6f9619ff-8b86-4d01-b42d-00cf4fc964ff",
      "workshopId": "aws-serverless-2026-09",
      "rating": 4,
      "comment": "Great pacing, more hands-on labs please.",
      "createdAt": "2026-09-05T08:34:33Z"
    },
    {
      "feedbackId": "a1b2c3d4-0000-4aaa-9bbb-ccccdddd1111",
      "workshopId": "aws-serverless-2026-09",
      "rating": 5,
      "comment": null,
      "createdAt": "2026-09-05T08:40:10Z"
    }
  ],
  "count": 2
}
```

  - Each item includes workshop identifier, rating, comment (or `null`), and submission timestamp (FR-009, AC-008).
  - `count` is the number of returned items. Ordering is unspecified for the POC (no sort requirement); implementers may return records in natural store order.
  - When no feedback exists, returns `200` with `{ "items": [], "count": 0 }`.

- **Client-error responses:**

| Status | `code` | Trigger |
|--------|--------|---------|
| 401 | `UNAUTHORIZED` | `X-Organizer-Key` header missing. |
| 403 | `FORBIDDEN` | `X-Organizer-Key` present but does not match. |

  On 401/403, **no feedback data is returned** (FR-008, BR-006, AC-009).

- **Server-error response:**

| Status | `code` | Trigger |
|--------|--------|---------|
| 500 | `INTERNAL_ERROR` | Unexpected retrieval failure; generic message. |

---

## 3. Method / path summary

| Method | Path | Auth | Purpose | Requirements |
|--------|------|------|---------|--------------|
| GET | `/health` | none | Health smoke test | FR-010 |
| POST | `/feedback` | none | Submit feedback | FR-002–FR-006 |
| GET | `/feedback` | organizer key | List feedback for review | FR-007–FR-009 |

No other endpoints are defined; none are justified by approved requirements (write-once, no update/delete, no analytics, no workshop CRUD — see requirements out-of-scope).

---

## 4. Status-code semantics

- `200` — successful read/health.
- `201` — feedback created and persisted.
- `400` — client validation/format error; nothing persisted.
- `401` — organizer key missing.
- `403` — organizer key invalid.
- `415` — unsupported media type (optional; may map to 400).
- `500` — unexpected server error; generic message, details logged to CloudWatch only.

---

## 5. Compatibility expectations

- Response fields are additive-only for the POC; consumers must ignore unknown fields.
- `feedbackId`, `createdAt`, `rating`, `workshopId`, and `comment` are stable field names shared with `docs/data-model.md`.
- The organizer auth header name (`X-Organizer-Key`) and error `code` values are part of the contract; changes require a change request.

---

## 6. Requirement coverage

| Endpoint / rule | Requirements / ACs |
|-----------------|--------------------|
| `POST /feedback` fields & validation | FR-002, FR-003, BR-001–BR-005, BR-008, AC-001, AC-003–AC-007 |
| `POST /feedback` persistence & confirmation | FR-004, FR-006, AC-001, AC-002 |
| `POST /feedback` rejection behavior | FR-005, AC-003–AC-006 |
| `GET /feedback` retrieval & fields | FR-007, FR-009, AC-008, NFR-012 |
| `GET /feedback` gating | FR-008, BR-006, A-005, AC-009 |
| `GET /health` | FR-010, AC-010 |
| No embedded secrets | NFR-007, AC-013 |
| HTTPS transport | NFR-011, AC-010, AC-011 |

ARCH_STATUS: PASS
