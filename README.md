# Workshop Feedback Portal

A serverless proof-of-concept web app where workshop attendees submit feedback and organizers review it — built end to end by a team of **specialized AI agents orchestrated through an industry-standard SDLC** using the Kiro CLI.

This repository is the artifact of an agent-orchestration workshop by **AI Playgrounds**. The point isn't just the app — it's *how* it was built: a single business request driven through requirements, design, parallel implementation, parallel validation, human-approved deployment, and live verification, with an orchestrator that coordinates specialists but never does their work itself.

---

## What it does

- **Attendees** submit feedback: a workshop identifier, an overall rating (1–5), and an optional comment. No login, no personal data.
- **Organizers** enter a shared access key to review all submitted feedback.
- All validation is **server-authoritative**; the frontend validation is convenience only.

## Architecture

Everything is serverless and provisioned with Terraform, inside a deliberately small AWS service catalog.

```
Browser
  │
  ├──────────────► CloudFront (HTTPS) ──► S3 (private, OAC)      static frontend
  │                                        HTML / CSS / vanilla JS
  │
  └── fetch API ─► API Gateway (HTTP API) ──► AWS Lambda (Python) ──► DynamoDB
                     GET  /health                path-routed handler     (on-demand,
                     POST /feedback              server-side validation    PK: feedbackId)
                     GET  /feedback              X-Organizer-Key gated
                                                        │
                                                        └──► CloudWatch Logs
```

**AWS services used:** S3, CloudFront, API Gateway, Lambda, DynamoDB, CloudWatch, IAM.
No Route 53 / ACM / custom domain — the default CloudFront URL is sufficient for a POC. Frontend storage is private (served only via CloudFront Origin Access Control). IAM is least-privilege.

## API

| Method | Path        | Auth               | Purpose                    |
|--------|-------------|--------------------|----------------------------|
| GET    | `/health`   | none               | Health / smoke check       |
| POST   | `/feedback` | none               | Submit one feedback record |
| GET    | `/feedback` | `X-Organizer-Key`  | List feedback for review   |

`POST /feedback` body:

```json
{
  "workshopId": "aws-serverless-2026-09",
  "rating": 4,
  "comment": "Great pacing, more hands-on labs please."
}
```

- `workshopId` — required, non-empty, ≤ 200 chars
- `rating` — required, integer 1–5 (non-integers / out-of-range rejected with `400`)
- `comment` — optional, ≤ 1000 chars

See [`docs/api-contract.md`](docs/api-contract.md) for full request/response and error shapes.

---

## How it was built: agent orchestration over an SDLC

A single business request ([`BUSINESS_REQUEST.md`](BUSINESS_REQUEST.md)) was taken through the lifecycle defined in [`SDLC_WORKFLOW.md`](SDLC_WORKFLOW.md), within the boundaries in [`WORKSHOP_CONSTRAINTS.md`](WORKSHOP_CONSTRAINTS.md).

Eight agents, each with a narrow role:

| Agent | Responsibility | Key output |
|-------|----------------|------------|
| **Orchestrator** | Coordinates the SDLC, enforces gates, routes findings — never does specialist work | lifecycle control |
| Business Analyst | Requirements & acceptance criteria | `docs/requirements.md` |
| Solution Architect | Architecture, API contract, data model | `docs/architecture.md`, `docs/api-contract.md`, `docs/data-model.md` |
| Frontend Developer | Static frontend | `frontend/` |
| Backend Developer | Python Lambda + tests | `backend/`, `tests/` |
| DevOps Engineer | Terraform, deploy, verify | `terraform/` |
| QA Engineer | Requirements-traceable validation | `docs/qa-report.md` |
| Security Reviewer | Risk-based security review | `docs/security-report.md` |

The flow (each arrow is a hard quality gate):

```
Requirements → Design → Implementation (Frontend ∥ Backend ∥ Infra)
             → Validation (QA ∥ Security) → Deployment Prep
             → Human Approval ("APPROVE DEPLOY") → Deploy → Live Verification → Completed
```

Highlights of the run:
- Frontend, Backend, and Infrastructure were implemented **in parallel**; QA and Security validated **in parallel**.
- The Security Reviewer caught a **deploy-breaking bug** (a Lambda env-var name mismatch) *before* deployment; it was routed to the DevOps agent, fixed, and **both QA and Security were re-run**.
- Deployment was gated on an **explicit human approval phrase** — nothing was applied to AWS without it.
- The release was confirmed with **live smoke tests** (health, valid submission, invalid-rating rejection, organizer auth, persistence) before being marked complete.

The agent definitions and prompts live in [`.kiro/agents/`](.kiro/agents/) and [`agent-prompts/`](agent-prompts/). Full lifecycle artifacts are in [`docs/`](docs/).

---

## Repository layout

```
.
├── .kiro/agents/         Agent registrations (orchestrator + 7 specialists)
├── agent-prompts/        System prompts for each agent
├── backend/              Python Lambda handler, validation, repository
├── tests/                Backend test suite (pytest)
├── frontend/             Static HTML / CSS / vanilla JS
├── terraform/            Infrastructure as code
├── docs/                 SDLC artifacts (requirements → release report)
├── BUSINESS_REQUEST.md   The originating business request
├── SDLC_WORKFLOW.md      The lifecycle the orchestrator enforces
└── WORKSHOP_CONSTRAINTS.md  Engineering/platform boundaries
```

---

## Running it yourself

### Prerequisites
- An AWS account and credentials (default profile or environment variables)
- [Terraform](https://developer.hashicorp.com/terraform/downloads)
- Python 3.12+ (for backend tests)

### Backend tests
```bash
pip install -r backend/requirements.txt pytest
python -m pytest
```

### Deploy
```bash
cd terraform
terraform init
terraform plan
terraform apply
```

Terraform outputs the CloudFront URL and API base URL. The organizer key is a sensitive output:

```bash
terraform output -raw organizer_key
```

### Tear down (avoid ongoing AWS charges)
```bash
cd terraform
terraform destroy
```

---

## Security & cost notes

- **No secrets in source.** The organizer key is a Terraform-managed value passed to the Lambda as an environment variable and surfaced only as a sensitive output. Do not commit `*.tfvars` or Terraform state — the root `.gitignore` excludes them.
- **Least-privilege IAM**, private S3 (CloudFront OAC only), HTTPS enforced, scoped CORS.
- Designed for **negligible idle cost** (on-demand DynamoDB, serverless compute). Run `terraform destroy` when you're done.

---

## Acknowledgements

Built during an agent-orchestration workshop by **AI Playgrounds**, using the **Kiro CLI**. Thanks to the facilitators for a genuinely hands-on session.
