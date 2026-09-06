# Frontend Implementation Summary — Workshop Feedback Portal (POC)

Status: Implementation
Owner: Frontend Developer
Scope: `frontend/` only
Sources of truth: `WORKSHOP_CONSTRAINTS.md`, `docs/requirements.md`, `docs/architecture.md`, `docs/api-contract.md`

Preconditions confirmed before implementation: `BA_STATUS: PASS` (requirements) and `ARCH_STATUS: PASS` (architecture, API contract, data model). No requirements/contract conflicts were found.

---

## 1. Approved scope implemented

A framework-less static browser application (semantic HTML5 + plain CSS + browser JavaScript with the Fetch API — no React/Vue/Angular/build pipeline, per `WORKSHOP_CONSTRAINTS.md` and NFR-002). Two capabilities in a single page:

1. **Attendee feedback submission** (FR-001, FR-002) — form with workshop identifier, 1–5 rating, and optional comment; submitted to `POST /feedback`.
2. **Organizer review** (FR-007, FR-009) — enter an organizer key, call `GET /feedback` with the `X-Organizer-Key` header, and list the collected records.

No behavior outside the approved requirements/contract was added (no editing/deleting, no analytics, no filtering/sorting/pagination, no PII fields — all explicitly out of scope in requirements §9).

## 2. Files created

| File | Responsibility |
|------|----------------|
| `frontend/index.html` | Semantic markup for both views (tabbed), accessible form controls, status/live regions. |
| `frontend/styles.css` | Mobile-first responsive layout; restrained internal-tool visual style; visible focus; ~44px touch targets; color-independent status messaging; honors `prefers-reduced-motion`. |
| `frontend/api.js` | API access layer isolated from the DOM. Implements `submitFeedback()` and `listFeedback()` against the exact contract shapes; tolerant JSON parsing; error normalization. |
| `frontend/app.js` | DOM/event wiring, tab switching, client-side convenience validation mirroring server rules, UI state management (IDLE/LOADING/SUCCESS/ERROR/EMPTY), safe rendering of untrusted data. |
| `frontend/config.js` | Non-secret runtime config carrying the API base URL (a Terraform output placeholder `__API_BASE_URL__`). |
| `frontend/README.md` | Frontend usage, config-injection contract, and secrets policy. |

## 3. API endpoints consumed (per `docs/api-contract.md`)

### `POST /feedback` — submit (auth: none)
- Request: `Content-Type: application/json`; body `{ workshopId, rating, comment? }`.
  - `workshopId`: trimmed string, ≤ 200 chars.
  - `rating`: JSON integer 1–5 (from radio selection — always an integer).
  - `comment`: included only when non-empty; omitted otherwise (matches "omitted = no comment").
- Responses handled:
  - `201` → read `message` (fallback "Feedback submitted successfully."), show success, reset form.
  - `400 VALIDATION_ERROR` → show `message`; map `details[].field` (`workshopId` / `rating` / `comment`) to the matching field error.
  - `400 MALFORMED_REQUEST` / `415` → show returned `message`.
  - `500 INTERNAL_ERROR` → show generic server-error message.
  - Network failure / non-JSON body → generic recoverable error (error bodies are not assumed to be JSON).

### `GET /feedback` — review (auth: `X-Organizer-Key`)
- Request: `X-Organizer-Key: <key>` header; no body; no query params.
- Responses handled:
  - `200` → render `items[]` (each `feedbackId`, `workshopId`, `rating`, `comment`|null, `createdAt`) and `count`; render EMPTY state when `count`/`items` is 0.
  - `401 UNAUTHORIZED` → "Organizer key is required." (or server `message`).
  - `403 FORBIDDEN` → "The organizer key is not valid." (or server `message`).
  - `500 INTERNAL_ERROR` → generic server-error message.

Field names/types are used exactly as specified and are shared with `docs/data-model.md`. Unknown response fields are ignored (additive-compatible).

`GET /health` is a backend/DevOps smoke-test endpoint and is intentionally not wired into the attendee UI.

## 4. UX states implemented

| State | Submission view | Review view |
|-------|-----------------|-------------|
| IDLE | Empty form, comment counter at `0 / 1000`. | Key field, no results. |
| LOADING | Button disabled + spinner, label "Submitting…"; prevents duplicate submits. | Button disabled + spinner, label "Loading…". |
| SUCCESS | Green status region with server message; form reset. | Results list rendered with count summary. |
| ERROR | Red status region + inline field errors (client or server-mapped). | Red status region (401/403/500/network). |
| EMPTY | — | "No feedback has been submitted yet." when count is 0. |

Status regions use `role="status"`/`aria-live="polite"`; field errors use `role="alert"`. No `alert()`/`confirm()` dialogs are used (per UI quality standard).

## 5. Validation & accessibility behavior

Validation (client-side is **convenience only**; server is authoritative — BR-008):
- `workshopId` required, non-empty after trim, ≤ 200 chars (BR-004).
- `rating` required, integer 1–5 via radio group (BR-001–BR-003) — a fractional or out-of-range value is not representable in the UI.
- `comment` optional, ≤ 1000 chars enforced client-side and via `maxlength` (BR-005).
- Duplicate submission prevented by disabling the submit button while a request is pending.
- User-entered data is preserved on recoverable errors; the form resets only after a confirmed `201`.

Accessibility (WCAG 2.2 AA principles):
- Semantic landmarks (`header`/`nav`/`main`/`footer`), single `h1`, logical heading order.
- Explicit `<label>`/`<legend>` for every control; radios grouped in a `<fieldset>` with a `radiogroup`.
- Inputs associated with hints and errors via `aria-describedby`; invalid fields get `aria-invalid="true"`.
- Skip link, visible focus rings, keyboard-operable tabs and controls, ~44px touch targets.
- Status/errors are perceivable without relying on color alone (text + icons-free semantics + live regions).
- `prefers-reduced-motion` disables the spinner animation.

## 6. Safe-rendering & privacy decisions

- All API/user-provided values (`workshopId`, `rating`, `comment`, `createdAt`) are rendered exclusively via `textContent`/`createElement`. No `innerHTML`, `outerHTML`, `insertAdjacentHTML`, or string-built markup is used anywhere — untrusted content cannot execute (XSS-safe).
- No PII is collected or displayed; the form requests only workshop id, rating, and optional comment (BR-007, A-004).
- **No secrets in assets or source** (NFR-007, AC-013): the only configured value is the public API base URL. The organizer key is entered at runtime, held in memory only for the request, sent solely as the `X-Organizer-Key` header, and never persisted or logged.
- The attendee submission flow never calls `GET /feedback`, so attendees never receive other attendees' feedback (BR-006, AC-009).
- All calls go to the HTTPS API Gateway URL (NFR-011); served from the CloudFront HTTPS URL with no custom domain (FR-011, NFR-004).

## 7. Requirement / acceptance-criteria mapping

| AC / Req | Where satisfied |
|----------|-----------------|
| AC-001 (submit id+rating+comment → success) | `POST /feedback` happy path + success state. |
| AC-002 (stored fields) | Fields sent exactly; server generates id/timestamp (not frontend concern). |
| AC-003 (no rating → rejected) | Client blocks; server `400` mapped to `rating` error. |
| AC-004 (rating 0/6 → rejected) | Only 1–5 selectable; server `400` mapped if bypassed. |
| AC-005 (empty workshop id → rejected) | Client blocks; server `400` mapped to `workshopId`. |
| AC-006 (comment > max → rejected) | Client `maxlength`+check; server `400` mapped to `comment`. |
| AC-007 (no comment → accepted) | `comment` omitted when empty; happy path. |
| AC-008 (organizer sees records) | `GET /feedback` renders id/rating/comment/timestamp. |
| AC-009 (attendee flow hides others' feedback) | Submission flow never calls `GET /feedback`. |
| AC-011 (form loads over HTTPS, no custom domain) | Static assets via CloudFront URL. |
| AC-013 (no secrets in assets/source) | Only public API base URL configured; key entered at runtime. |
| FR-001–FR-009, FR-011 | See sections 1–6. |
| NFR-002, NFR-004, NFR-007, NFR-011 | Framework-less static app; no custom domain; no secrets; HTTPS. |

## 8. Self-review performed

- All frontend-relevant acceptance criteria are represented (table above).
- Request/response handling matches the approved contract field names, types, and status codes; error bodies are not assumed to be JSON.
- No unapproved feature added; no PII collected/exposed.
- Accessibility basics present (labels, roles, live regions, focus, keyboard).
- Responsive from ~320px upward; cards/lists wrap rather than overflow.
- Untrusted content rendered only via `textContent`.
- Loading/error/success/empty states are intentional and disable duplicate submits.
- Output is deployable as static assets consistent with the architecture (S3 + CloudFront), with the API base URL injected via `config.js`.

## 9. Known limitations (within approved POC scope)

- Ordering of review results follows the server's natural order (no client sort — sorting is out of scope).
- Organizer key is entered per session in the browser; this is the accepted shared-secret POC mechanism (A-005, R-001), not identity-based auth.
- Client-side validation is convenience only; the server is authoritative (BR-008) and its messages take precedence when returned.
- `config.js` requires the deploy-time API base URL substitution (owned by DevOps); until substituted, the app surfaces a clear "API base URL is not configured" error rather than calling a placeholder URL.

FRONTEND_STATUS: PASS
