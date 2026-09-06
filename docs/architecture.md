# Workshop Feedback Portal — Architecture (POC)

Status: Design
Owner: Solution Architect
Source of truth: `docs/requirements.md`, `WORKSHOP_CONSTRAINTS.md`
Scope level: Proof of Concept (POC)

This document defines **how** the Workshop Feedback Portal satisfies the approved requirements within the workshop constraints. Companion artifacts: `docs/api-contract.md` and `docs/data-model.md`.

---

## 1. Architecture goals and constraints

### Goals (derived from requirements)

- Serve a static attendee feedback form over HTTPS from the generated CloudFront URL (FR-001, FR-011, NFR-011).
- Accept feedback submissions, validate them server-side, and persist accepted records durably (FR-002–FR-006, NFR-012).
- Let organizers retrieve collected feedback through a gated capability (FR-007, FR-008, FR-009).
- Expose a health indicator for smoke testing (FR-010).
- Keep idle cost negligible and teardown simple (NFR-008, NFR-009, NFR-010).

### Fixed constraints

- AWS only; provisioned/updated via Terraform (NFR-001, NFR-010).
- Backend in Python on a serverless runtime; frontend static HTML/CSS/JS, no framework (NFR-002).
- Approved services only: **S3, CloudFront, API Gateway, Lambda, DynamoDB, CloudWatch, IAM** (NFR-003).
- No Route 53, ACM, custom domain, EC2/ECS/EKS, load balancers, VPCs, NAT Gateways (NFR-003, NFR-004).
- Frontend S3 bucket must not be directly public; served only through CloudFront (NFR-005, AC-012).
- Least privilege for all IAM (NFR-006). No embedded secrets (NFR-007, AC-013).
- On-demand/consumption capacity everywhere (NFR-008).

---

## 2. Topology (component diagram description)

```
                         Attendee browser                 Organizer browser
                                │                                  │
                                │ HTTPS (GET static assets)        │ HTTPS (API + organizer key header)
                                ▼                                  │
                     ┌──────────────────────┐                      │
                     │  CloudFront (default  │                      │
                     │  *.cloudfront.net)    │                      │
                     │  + OAC to S3          │                      │
                     └───────┬──────────────┘                      │
              origin: static │  (private, OAC-signed)              │
                             ▼                                      │
                   ┌───────────────────┐                           │
                   │ S3 (frontend)     │                           │
                   │ private, no public│                           │
                   │ access            │                           │
                   └───────────────────┘                           │
                                                                    │
   Browser JS calls API directly ──────────────► ┌─────────────────▼──────────────┐
   (HTTPS, API Gateway default URL)               │ API Gateway (HTTP API)         │
                                                   │ default execute-api URL        │
                                                   │ routes: /health, /feedback,    │
                                                   │ /feedback (GET, gated)         │
                                                   └───────────────┬────────────────┘
                                                                   │ Lambda proxy
                                                                   ▼
                                                   ┌────────────────────────────────┐
                                                   │ AWS Lambda (Python)            │
                                                   │ single handler, path-routed:   │
                                                   │  - health check                │
                                                   │  - validate + create feedback  │
                                                   │  - list feedback (key-gated)   │
                                                   └───────────────┬────────────────┘
                                                                   │ DynamoDB API (on-demand)
                                                                   ▼
                                                   ┌────────────────────────────────┐
                                                   │ DynamoDB table: Feedback       │
                                                   │ PAY_PER_REQUEST                │
                                                   └────────────────────────────────┘

  Observability: Lambda + API Gateway → CloudWatch Logs & Metrics
  Config: organizer access key delivered to Lambda via environment variable (managed by Terraform, not in code/frontend)
```

Two independent entry paths:

1. **Static delivery path:** browser → CloudFront → (OAC) → private S3 (frontend assets).
2. **API path:** browser JavaScript → API Gateway (default URL) → Lambda → DynamoDB.

The frontend and API are decoupled; the browser calls the API Gateway URL directly. This is the smallest wiring that keeps S3 private while avoiding CloudFront-to-API-Gateway behaviors, extra origins, or a custom domain.

---

## 3. Component responsibilities

### S3 — Frontend asset store
- **Purpose:** durable storage of static frontend assets (HTML/CSS/JS).
- **Owned data:** frontend build artifacts only. No application data.
- **Interfaces:** inbound object reads only from CloudFront via Origin Access Control (OAC); Terraform manages object upload.
- **Trust boundary:** private. Block Public Access enabled; bucket policy grants read only to the specific CloudFront distribution (via OAC service principal + `AWS:SourceArn` condition).
- **Failure considerations:** static assets; failure surfaces as CloudFront 403/404. No state to lose.
- **Operational responsibility:** DevOps (Terraform) provisions bucket, policy, and uploads assets.
- **Satisfies:** NFR-005, AC-012, FR-011.

### CloudFront — Content delivery
- **Purpose:** serve the static frontend over HTTPS via the generated distribution domain; keep S3 private.
- **Owned behavior:** TLS termination using the default CloudFront certificate; edge caching of static assets; OAC signing to the S3 origin.
- **Interfaces:** inbound HTTPS from browsers; outbound signed origin requests to S3.
- **Trust boundary:** public edge. Viewer protocol policy = redirect-to-HTTPS. No custom domain/ACM.
- **Failure considerations:** origin errors return standard CloudFront error responses; default root object `index.html`.
- **Satisfies:** FR-011, NFR-004, NFR-005, NFR-011, AC-011, AC-012.

### API Gateway (HTTP API) — Backend HTTP entry
- **Purpose:** expose the backend HTTP interface at the default `execute-api` URL over HTTPS.
- **Owned behavior:** routing of `GET /health`, `POST /feedback`, `GET /feedback` to the Lambda proxy; CORS configuration allowing the CloudFront origin; TLS via the AWS-managed default endpoint.
- **Interfaces:** inbound HTTPS from browsers; outbound Lambda proxy integration.
- **Trust boundary:** public. No API-Gateway-level authorizer for the POC; organizer gating is enforced in Lambda via a shared key (A-005). Rationale: HTTP API + Lambda-side check is the smallest mechanism satisfying FR-008 without adding an identity service (which the catalog forbids).
- **Failure considerations:** returns Lambda-produced status codes; 5xx if Lambda fails.
- **Satisfies:** FR-002–FR-010, NFR-011.
- **Choice note:** HTTP API (API Gateway v2) is chosen over REST API for lower cost and simpler config; both are within the approved "Amazon API Gateway" catalog entry.

### Lambda (Python) — Application logic
- **Purpose:** single Python function, path-routed, implementing all backend behavior.
- **Owned behavior:**
  - Health: return a healthy JSON response (FR-010, AC-010).
  - Create feedback: parse/validate input server-side, generate `feedbackId` and `createdAt`, write to DynamoDB, return confirmation (FR-002–FR-006, BR-001–BR-005, BR-008).
  - List feedback: verify the organizer access key, then return collected records (FR-007–FR-009, BR-006, A-005).
- **Interfaces:** inbound API Gateway proxy events; outbound DynamoDB `PutItem`/`Scan`.
- **Trust boundary:** holds the organizer access key as an environment variable injected by Terraform (never in source or frontend). Performs all authoritative validation.
- **Failure considerations:** validation failures → 400 with a clear error; malformed JSON → 400; unexpected errors → 500 with a generic message (details logged, not returned). No retries needed for the POC.
- **Operational responsibility:** Backend owns handler code; DevOps owns packaging/deploy via Terraform.
- **Choice note:** one function with internal routing is the smallest footprint (single deployment artifact, single log group, single role). Justified by NFR-009.

### DynamoDB — Feedback persistence
- **Purpose:** durable serverless storage of feedback records.
- **Owned data:** `Feedback` table (see `docs/data-model.md`).
- **Interfaces:** `PutItem` (create), `Scan` (list) from Lambda only.
- **Trust boundary:** accessible only via the Lambda execution role (least privilege: item-level write and table read on this table ARN only).
- **Capacity:** `PAY_PER_REQUEST` (on-demand) per NFR-008.
- **Failure considerations:** conditional-write not required (write-once, unique generated IDs). On throttling (unlikely at workshop scale) Lambda surfaces a 500.
- **Satisfies:** FR-004, FR-006, NFR-012, AC-002, AC-008.

### CloudWatch — Observability
- **Purpose:** logs and metrics for health confirmation and failure diagnosis.
- **Owned behavior:** Lambda log group (structured logs for submissions/validation outcomes, without sensitive data); API Gateway access/execution logging; default Lambda/API metrics.
- **Trust boundary:** internal; log content must exclude the organizer key and avoid echoing raw comment PII beyond what is needed to diagnose (BR-007).
- **Satisfies:** NFR-013.

### IAM — Access control
- **Purpose:** least-privilege permissions.
- **Owned behavior:**
  - Lambda execution role: `dynamodb:PutItem`, `dynamodb:GetItem`, `dynamodb:Scan` scoped to the `Feedback` table ARN; `logs:CreateLogStream`/`logs:PutLogEvents` scoped to its log group.
  - CloudFront OAC read access to S3 restricted to the specific distribution ARN.
  - No wildcard resource grants.
- **Satisfies:** NFR-006.

---

## 4. Request / data flow

### Flow A — Attendee loads the form (FR-001, FR-011)
1. Browser requests the CloudFront distribution URL over HTTPS.
2. CloudFront serves `index.html` and static assets from private S3 via OAC.

### Flow B — Attendee submits feedback (FR-002–FR-006)
1. Browser JS sends `POST /feedback` to the API Gateway default URL over HTTPS with a JSON body.
2. API Gateway invokes Lambda (proxy).
3. Lambda validates: workshop identifier non-empty (BR-004), rating is integer 1–5 (BR-001–BR-003), comment optional and ≤ 1000 chars (BR-005).
4. If invalid → 400 with a clear error; nothing persisted (FR-005, AC-003–AC-006).
5. If valid → Lambda generates `feedbackId` (UUID) and `createdAt` (ISO-8601 UTC), writes to DynamoDB, returns 201 confirmation (FR-004, FR-006, AC-001, AC-002, AC-007).

### Flow C — Organizer reviews feedback (FR-007–FR-009)
1. Organizer client sends `GET /feedback` with the organizer access key header.
2. Lambda compares the key against its env-var value.
3. Missing/invalid key → 401/403; nothing returned (FR-008, BR-006, AC-009).
4. Valid key → Lambda `Scan`s the table and returns records with workshop identifier, rating, comment (if any), and timestamp (AC-008).

### Flow D — Health check (FR-010)
1. Client sends `GET /health`.
2. Lambda returns `{"status":"ok"}` with 200 (AC-010).

---

## 5. Trust and security boundaries

- **Public edge:** CloudFront (static) and API Gateway (API) are internet-facing over HTTPS only.
- **Private storage:** frontend S3 bucket is never public; reachable only via CloudFront OAC (AC-012). Application data in DynamoDB is reachable only via the Lambda role.
- **Organizer gate:** enforced inside Lambda using a shared access key (A-005). The key is injected via Terraform-managed Lambda environment variable and is never present in frontend assets or source (NFR-007, AC-013). This is an accepted POC simplification (R-001); it is weaker than identity-based authz but satisfies FR-008/BR-006 within the approved catalog (no Cognito/identity service allowed).
- **Least privilege:** all IAM policies scoped to specific resource ARNs and actions (NFR-006).
- **Input trust:** all validation is server-side and authoritative (BR-008); client-side checks are convenience only.
- **CORS:** API Gateway allows the CloudFront origin for the required methods; not a security control but prevents casual cross-origin misuse.

---

## 6. Observability and operations

- Lambda emits structured logs to CloudWatch for each request: route, outcome (accepted/rejected + rejection reason category), and error stack traces on 5xx. Logs must **not** include the organizer key and should avoid persisting raw comment text at info level beyond diagnostic need (BR-007, NFR-013).
- API Gateway access logging enabled to CloudWatch.
- Default CloudWatch metrics (Lambda invocations/errors/duration, API 4xx/5xx) support the smoke test and diagnosis (NFR-013).
- Health endpoint provides the deployment smoke-test signal (FR-010, AC-010).

---

## 7. Deployment / IaC approach

- All resources provisioned and updated via Terraform (NFR-001, NFR-010): S3 bucket + policy + object uploads, CloudFront distribution + OAC, API Gateway HTTP API + routes + integration + stage, Lambda function + role/policies + log group, DynamoDB table.
- The organizer access key is provided as a Terraform input variable (marked sensitive) and passed to the Lambda environment; it is not committed to source (NFR-007).
- Frontend must be built/available before/after distribution creation; the API base URL (API Gateway default endpoint) is a Terraform output consumed by the frontend configuration. Injection mechanism (build-time config vs. runtime config file) is a downstream implementation detail; the contract is that no secret is embedded (only the non-secret API base URL).
- Teardown is a single `terraform destroy` (NFR-010, R-004).

---

## 8. Cost and lifecycle considerations

- Idle cost ≈ storage of a few small S3 objects + DynamoDB on-demand (no idle charge) + CloudFront (no idle charge) → negligible (NFR-008).
- All compute/storage is consumption-based: Lambda per-invoke, DynamoDB `PAY_PER_REQUEST`, API Gateway per-request.
- Single Lambda, single table, single distribution — minimal component count (NFR-009).
- Fully disposable via Terraform for the short workshop lifecycle (NFR-010, R-004).

---

## 9. Trade-offs and accepted limitations

- **ADR-1 — Browser calls API Gateway directly (not proxied through CloudFront).** Drivers: smallest wiring, keeps S3 private, avoids multi-origin CloudFront config. Alternative (CloudFront path-based behavior to API Gateway) rejected as unnecessary complexity for the POC. Limitation: two public hostnames (CloudFront + execute-api); acceptable, both HTTPS, no custom domain (NFR-004).
- **ADR-2 — Single path-routed Lambda.** Drivers: minimal footprint, one role/log group. Alternative (function-per-route) rejected as more components than needed (NFR-009). Limitation: shared cold-start/blast radius; acceptable at POC scale.
- **ADR-3 — Shared-key organizer gate in Lambda.** Drivers: FR-008/BR-006 require gating; identity services are outside the approved catalog. Alternative (Cognito/IAM auth) prohibited. Limitation: shared-secret authz (R-001), accepted POC risk.
- **ADR-4 — DynamoDB `Scan` for organizer list.** Drivers: single access pattern (list all), tiny dataset, write-once records, no filtering/pagination in scope. Alternative (query with partition design) unnecessary; `Scan` is simplest for the collection-review pattern at workshop volume. Limitation: `Scan` is inefficient at large scale — explicitly out of scope (NFR-014, out-of-scope pagination).
- **ADR-5 — HTTP API over REST API.** Drivers: lower cost, simpler config, sufficient features. Within the approved API Gateway catalog entry.
- **Accepted risks (from requirements):** R-002 unauthenticated/duplicate submissions, R-003 no content moderation, R-004 no retention/backup. All documented and accepted per requirements.

---

## 10. Requirement-coverage matrix

| Requirement | Covered by |
|-------------|-----------|
| FR-001 | S3 + CloudFront static delivery; frontend form; `GET /health` not required for load |
| FR-002 | `POST /feedback` request contract; Lambda parse |
| FR-003 | Lambda server-side validation |
| FR-004 | Lambda write to DynamoDB + 201 confirmation |
| FR-005 | Lambda 400 on invalid, no write |
| FR-006 | Lambda-generated `createdAt` timestamp |
| FR-007 | `GET /feedback` (gated) + Lambda Scan |
| FR-008 | Organizer access-key check in Lambda |
| FR-009 | `GET /feedback` response includes workshop id, rating, comment, timestamp |
| FR-010 | `GET /health` |
| FR-011 | CloudFront default URL over HTTPS; private S3 |
| NFR-001 | Terraform for all infra |
| NFR-002 | Python Lambda + static frontend |
| NFR-003 | Only S3/CloudFront/API GW/Lambda/DynamoDB/CloudWatch/IAM used |
| NFR-004 | Default CloudFront/execute-api URLs; no Route 53/ACM |
| NFR-005 | S3 Block Public Access + OAC-only bucket policy |
| NFR-006 | Resource-scoped IAM policies |
| NFR-007 | Organizer key via Terraform env var; not in source/frontend |
| NFR-008 | On-demand Lambda/DynamoDB; negligible idle |
| NFR-009 | Single Lambda, single table, minimal components |
| NFR-010 | `terraform destroy` teardown |
| NFR-011 | HTTPS on CloudFront and API Gateway |
| NFR-012 | DynamoDB durable persistence + Scan retrieval |
| NFR-013 | CloudWatch logs/metrics + health endpoint |
| NFR-014 | On-demand capacity for workshop-sized traffic |
| BR-001–BR-005, BR-008 | Lambda validation rules (see api-contract) |
| BR-006 | Organizer-only list; attendee flow returns no other feedback |
| BR-007 | Form/data model require no PII; logging avoids sensitive data |
| AC-001–AC-013 | Flows B/C/D + security boundaries above |

---

## 11. Terminal status

Every functional requirement maps to a component/API behavior; every selected component has a requirement or quality-attribute justification; only approved services are used; the API contract and data model agree (see companion docs); trust boundaries and least-privilege needs are specified for DevOps; the solution is the smallest viable serverless topology. No requirements conflicts or blocking ambiguities were found.

ARCH_STATUS: PASS
