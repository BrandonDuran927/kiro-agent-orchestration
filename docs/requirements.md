# Workshop Feedback Portal — Requirements Baseline (POC)

Status: Approved for Design
Owner: Business Analyst
Source of truth: `BUSINESS_REQUEST.md`, `WORKSHOP_CONSTRAINTS.md`
Scope level: Proof of Concept (POC)

This document defines **what** the Workshop Feedback Portal must do and the qualities it must exhibit. It intentionally does **not** define API contracts, data schemas, data models, IAM policies, or cloud architecture. Those decisions belong to the Solution Architect and downstream specialists.

---

## 1. Business objective

The Learning & Development (L&D) team runs internal technical workshops and needs a lightweight web application that lets:

- workshop **attendees** submit feedback after a workshop, and
- workshop **organizers** review the collected feedback.

The application is a proof of concept. It must be inexpensive to operate, cheap to run at idle, easy to deploy to AWS, and simple to tear down after the workshop. Success means an attendee can submit valid feedback and an organizer can see that feedback reflected in the review view.

---

## 2. Actors / stakeholders

| Actor | Type | Description |
|-------|------|-------------|
| Attendee | Primary user | A workshop participant who submits feedback after attending. Unauthenticated for this POC. |
| Organizer | Primary user | A member of the L&D team who reviews submitted feedback. Access is gated by a shared, low-friction mechanism for the POC (see assumptions). |
| L&D team | Stakeholder | Owns the business need and the collected feedback. |
| Workshop facilitator | Stakeholder | Sets/approves workshop constraints and the POC boundaries. |
| Operator / deployer | Supporting | Person who deploys and later tears down the POC (a downstream SDLC role). |

---

## 3. Scope summary

**In scope**

- A public web page where an attendee submits feedback for a workshop.
- Capture and durable persistence of each submitted feedback record.
- Server-side validation of submitted feedback before it is stored.
- A review capability that lets an organizer see the list of submitted feedback.
- A basic service health/availability signal suitable for a smoke test.

**Out of scope** — see Section 9.

The business team intentionally left the feedback fields, workflow, API design, data model, and architecture unspecified. This document derives reasonable POC-appropriate **feedback fields, workflow, and behavior** as requirements/assumptions, and leaves API/data/architecture to Design.

---

## 4. Functional requirements

### Feedback submission (Attendee)

- **FR-001** — The system shall present attendees with a feedback submission form accessible from a web browser without requiring an attendee login/account.
- **FR-002** — The system shall allow an attendee to submit feedback consisting of at least: a workshop identifier/name, a numeric overall rating, and an optional free-text comment (see BR-001–BR-005 for field rules).
- **FR-003** — The system shall validate submitted feedback on the server side before persisting it, and shall reject submissions that violate the business/validation rules in Section 6.
- **FR-004** — On a successful submission, the system shall durably persist the feedback record and return a clear success confirmation to the attendee.
- **FR-005** — On a rejected submission, the system shall not persist the record and shall return a clear, human-readable error indicating that the submission was invalid.
- **FR-006** — The system shall record the submission timestamp for each accepted feedback record.

### Feedback review (Organizer)

- **FR-007** — The system shall allow an organizer to retrieve the collected feedback records for review.
- **FR-008** — The system shall restrict the organizer review capability so it is not available to ordinary attendees through the normal attendee submission flow (see BR-006 and assumptions on organizer access).
- **FR-009** — The system shall present retrieved feedback in a form that shows, for each record, at least the workshop identifier, the rating, the comment (if any), and the submission timestamp.

### Service health

- **FR-010** — The system shall expose a basic health/availability indicator that confirms the backend is reachable and functioning, suitable for a deployment smoke test.

### Frontend delivery

- **FR-011** — The system shall serve the attendee-facing frontend as a static web application over HTTPS via the generated content-delivery URL, without requiring a custom domain.

---

## 5. Non-functional requirements

- **NFR-001 (Platform)** — The solution shall run entirely on AWS and be provisioned/updated via Terraform. *(Fixed constraint.)*
- **NFR-002 (Runtime)** — Backend logic shall be implemented in Python on a serverless runtime; the frontend shall be static HTML/CSS/JavaScript with no frontend framework. *(Fixed constraint.)*
- **NFR-003 (Approved services only)** — The solution shall use only services in the approved catalog (S3, CloudFront, API Gateway, Lambda, DynamoDB, CloudWatch, IAM) and shall not introduce Route 53, ACM, EC2/ECS/EKS, load balancers, VPCs, or NAT Gateways. *(Fixed constraint.)*
- **NFR-004 (No custom domain)** — The frontend shall be reachable via the generated CloudFront distribution URL; no custom DNS/domain/certificate configuration is required. *(Fixed constraint.)*
- **NFR-005 (Frontend storage privacy)** — Frontend object storage shall not be directly publicly accessible; content shall be delivered only through the content-delivery layer. *(Fixed constraint.)*
- **NFR-006 (Least privilege)** — All access permissions granted to compute and users shall follow least-privilege principles. *(Fixed constraint.)*
- **NFR-007 (No embedded secrets)** — No AWS credentials, secrets, or account credentials shall be embedded in source code or in frontend assets. *(Fixed constraint.)*
- **NFR-008 (Cost / idle)** — The solution shall use consumption-based/on-demand capacity and incur negligible cost while idle. *(Fixed constraint.)*
- **NFR-009 (Minimal footprint)** — The solution shall use the fewest components needed to satisfy these requirements and shall not add capacity or features for hypothetical future scale. *(Fixed constraint.)*
- **NFR-010 (Deploy/teardown simplicity)** — The solution shall be deployable and fully removable through Terraform to support a short workshop lifecycle.
- **NFR-011 (Transport security)** — All client-server communication shall occur over HTTPS.
- **NFR-012 (Durability of feedback)** — Accepted feedback records shall persist across backend invocations and be retrievable by an organizer for the duration of the POC.
- **NFR-013 (Observability)** — The system shall emit backend logs/metrics sufficient to confirm health and diagnose failed submissions during the POC.
- **NFR-014 (POC availability)** — The system is expected to serve low, workshop-sized concurrent traffic; no formal uptime SLA is required for the POC.

---

## 6. Business and validation rules

- **BR-001 (Rating scale)** — The overall rating shall be an integer on a 1–5 scale (1 = worst, 5 = best). *(Assumption — see A-002.)*
- **BR-002 (Rating required)** — A rating is required for a submission to be accepted.
- **BR-003 (Rating range enforcement)** — A submission with a rating outside the 1–5 integer range shall be rejected.
- **BR-004 (Workshop identifier required)** — A non-empty workshop identifier/name is required for a submission to be accepted.
- **BR-005 (Comment optional and bounded)** — The free-text comment is optional; when provided it shall be bounded to a reasonable maximum length (e.g., 1,000 characters) and rejected if exceeded. *(Assumption — see A-003.)*
- **BR-006 (Review visibility)** — Feedback review is an organizer capability; the attendee submission experience shall not expose other attendees' feedback back to attendees.
- **BR-007 (No sensitive personal data)** — Attendees are not required to provide personally identifying information; the form shall not request sensitive personal data. *(Assumption — see A-004.)*
- **BR-008 (Server-authoritative validation)** — All validation rules are enforced server-side; any client-side validation is a convenience only and is not authoritative.

---

## 7. Acceptance criteria

**Submission — happy path**

- **AC-001** —
  Given the attendee feedback form is loaded,
  When the attendee submits a workshop identifier, a rating of 4, and a comment,
  Then the system persists the feedback and returns a success confirmation.

- **AC-002** —
  Given a feedback record was successfully submitted,
  When the record is stored,
  Then it includes the workshop identifier, the rating, the comment (if provided), and a submission timestamp.

**Submission — validation / boundary**

- **AC-003** —
  Given the attendee feedback form,
  When the attendee submits with no rating,
  Then the system rejects the submission and returns a clear validation error, and no record is persisted.

- **AC-004** —
  Given the attendee feedback form,
  When the attendee submits a rating of 0 or 6 (outside 1–5),
  Then the system rejects the submission and returns a clear validation error, and no record is persisted.

- **AC-005** —
  Given the attendee feedback form,
  When the attendee submits with an empty workshop identifier,
  Then the system rejects the submission and returns a clear validation error, and no record is persisted.

- **AC-006** —
  Given the attendee feedback form,
  When the attendee submits a comment longer than the allowed maximum,
  Then the system rejects the submission and returns a clear validation error, and no record is persisted.

- **AC-007** —
  Given a valid rating within range and a valid workshop identifier and no comment,
  When the attendee submits,
  Then the system accepts and persists the record (comment is optional).

**Review — organizer**

- **AC-008** —
  Given one or more feedback records have been submitted,
  When an organizer accesses the review capability,
  Then the system returns the collected feedback records showing workshop identifier, rating, comment (if any), and submission timestamp.

- **AC-009** —
  Given the normal attendee submission experience,
  When an attendee uses it,
  Then it does not display other attendees' submitted feedback to the attendee.

**Health / delivery**

- **AC-010** —
  Given the deployed backend,
  When the health indicator is queried,
  Then it returns a healthy response confirming the backend is reachable.

- **AC-011** —
  Given the deployed frontend,
  When the attendee opens the generated distribution URL over HTTPS,
  Then the feedback form loads without requiring a custom domain.

**Non-functional / constraints (verifiable)**

- **AC-012** —
  Given the deployed frontend storage,
  When accessed directly (not through the delivery layer),
  Then the object storage is not directly publicly readable.

- **AC-013** —
  Given the delivered frontend assets and source,
  When inspected,
  Then no AWS credentials or secrets are present in the assets or source.

---

## 8. Assumptions and dependencies

- **A-001 (Unauthenticated attendees)** — For the POC, attendees submit feedback without individual accounts or login. Rationale: minimizes scope and cost for an internal workshop; acceptable POC risk.
- **A-002 (Rating scale)** — A 1–5 integer scale is assumed as a standard, low-ambiguity feedback rating. Adjustable if stakeholders prefer a different scale.
- **A-003 (Comment length)** — A 1,000-character maximum comment length is assumed as a reasonable bound; the exact value is not business-critical and may be tuned in design.
- **A-004 (Minimal PII)** — Feedback is assumed to be effectively anonymous; no name, email, or other PII is required. An optional non-identifying name field may be added later only if stakeholders request it.
- **A-005 (Organizer access mechanism)** — For the POC, organizer review is protected by a simple, low-friction access mechanism (e.g., a shared secret/key held by organizers) rather than a full identity system. The specific mechanism is an implementation/design detail, but the *need to gate organizer access* is a requirement (FR-008, BR-006). This is an accepted POC security simplification.
- **A-006 (Single workshop context acceptable)** — The system may serve one or multiple workshops; the workshop identifier field distinguishes records. No workshop-management/admin CRUD is required for the POC.
- **A-007 (Traffic profile)** — Concurrent usage is workshop-sized (tens, not thousands), consistent with on-demand serverless capacity.
- **Dependency D-001** — An AWS account and Terraform tooling are available to the deploying role (covered by workshop prerequisites).
- **Dependency D-002** — Downstream Design will define the API contract, data model, and architecture consistent with these requirements and the approved service catalog.

---

## 9. Explicit out of scope

The following are explicitly **not** in scope for this POC:

- Attendee authentication, user accounts, or profile management.
- A production-grade identity/authorization system for organizers (SSO, IAM Identity Center federation, role hierarchies).
- Editing, updating, or deleting feedback after submission (submissions are write-once for the POC).
- Feedback analytics, aggregation dashboards, charts, scoring, or reporting beyond a simple review list.
- Data export (CSV/PDF), email/Slack notifications, or scheduled digests.
- Search, filtering, sorting, or pagination beyond what is needed to display the collected feedback.
- Internationalization/localization and multi-language support.
- Custom domain, DNS, or TLS certificate management (Route 53/ACM explicitly excluded).
- Multi-region, high-availability, disaster-recovery, or formal uptime SLA guarantees.
- Long-term data retention, archival, backup/restore policies, or compliance/audit programs.
- Moderation of comment content and abuse/spam prevention beyond basic input validation.
- Rate limiting/DDoS protection beyond platform defaults (accepted POC risk).
- Any AWS service outside the approved catalog.
- Load/performance/scale engineering for future growth.

---

## 10. Requirement-to-acceptance-criteria traceability

| Requirement | Acceptance criteria |
|-------------|---------------------|
| FR-001 | AC-011 |
| FR-002 | AC-001, AC-002, AC-007 |
| FR-003 | AC-003, AC-004, AC-005, AC-006 |
| FR-004 | AC-001, AC-002 |
| FR-005 | AC-003, AC-004, AC-005, AC-006 |
| FR-006 | AC-002 |
| FR-007 | AC-008 |
| FR-008 | AC-008, AC-009 |
| FR-009 | AC-008 |
| FR-010 | AC-010 |
| FR-011 | AC-011 |
| NFR-005 | AC-012 |
| NFR-007 | AC-013 |
| NFR-011 | AC-010, AC-011 |
| NFR-012 | AC-002, AC-008 |
| BR-001/BR-002/BR-003 | AC-003, AC-004 |
| BR-004 | AC-005 |
| BR-005 | AC-006, AC-007 |
| BR-006 | AC-009 |
| BR-008 | AC-003, AC-004, AC-005, AC-006 |

*Note: NFR-001–NFR-004, NFR-006, NFR-008–NFR-010, NFR-013–NFR-014 are fixed platform/quality constraints verified during Design, Security review, and Deployment gates rather than by attendee-facing acceptance tests.*

---

## 11. Risks / unresolved considerations (non-blocking)

- **R-001 (Organizer access simplification)** — Using a shared secret/key for organizer review (A-005) is weaker than real identity-based authorization. Accepted as a POC risk; if stakeholders later require accountable organizer identity, raise a change request.
- **R-002 (Unauthenticated submissions)** — Open submission (A-001) allows anonymous or duplicate/spam submissions with no rate limiting. Accepted as a POC risk for an internal, short-lived workshop.
- **R-003 (No content moderation)** — Free-text comments are not moderated beyond length/validation; inappropriate content is possible. Accepted as a POC risk.
- **R-004 (Data retention)** — No retention/backup policy; feedback exists only for the POC lifetime and is removed at teardown. Accepted as a POC risk.

None of these block Design. They are documented accepted POC risks per the workshop security/cost constraints.

---

## 12. Terminal status

All business objectives map to at least one requirement; every functional requirement has at least one testable acceptance criterion; no requirement depends on an unresolved stakeholder decision; and technical design decisions (API, data model, architecture, IAM) have been deliberately left to Design.

BA_STATUS: PASS
