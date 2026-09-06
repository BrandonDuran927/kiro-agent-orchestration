# SDLC Workflow Contract

This file is the authoritative process definition that the participant-created `sdlc-orchestrator` agent must read and enforce.

The orchestrator controls lifecycle state, delegates specialist work, validates gates, routes failures to the correct owner, preserves artifacts, and stops for human approval before deployment. It must not perform specialist work itself.

## Authoritative inputs

- `BUSINESS_REQUEST.md` — initial stakeholder intent
- `WORKSHOP_CONSTRAINTS.md` — engineering/platform boundaries
- `SDLC_WORKFLOW.md` — lifecycle and change-management rules
- `change-requests/CR-XXX.md` — later change requests when supplied

## Available specialist agents

- `business-analyst`
- `solution-architect`
- `frontend-developer`
- `backend-developer`
- `qa-engineer`
- `security-reviewer`
- `devops-engineer`

---

# Entry routing

## Initial delivery

If no completed release exists and work is based on `BUSINESS_REQUEST.md`, start at `INTAKE`.

## Change request

If a completed release exists and the user supplies `change-requests/CR-XXX.md`, start at `CHANGE_REQUEST_INTAKE`.

A change request must **never** go directly to either implementation developer. It begins with Business Analyst impact analysis.

---

# Workflow A — Initial delivery

```text
INTAKE
  ↓
REQUIREMENTS
  ↓
DESIGN
  ↓
IMPLEMENTATION
  ↓
VALIDATION
  ↓
DEPLOYMENT_PREPARATION
  ↓
AWAITING_HUMAN_APPROVAL
  ↓
DEPLOYMENT
  ↓
VERIFICATION
  ↓
COMPLETED
```

## INTAKE

Confirm the business request, constraints, and workflow exist, initialize lifecycle state, and invoke `business-analyst`.

## REQUIREMENTS

Owner: `business-analyst`

Inputs: `BUSINESS_REQUEST.md`, `WORKSHOP_CONSTRAINTS.md`

Output: `docs/requirements.md`

Gate:

```text
BA_STATUS: PASS
```

If `BA_STATUS: BLOCKED`, surface only the BA's unresolved stakeholder questions to the human, collect answers, and re-invoke BA until PASS.

Requirements must include actors, functional/non-functional requirements, testable acceptance criteria, assumptions, out-of-scope items, and no unresolved blocker.

## DESIGN

Owner: `solution-architect`

Inputs: `WORKSHOP_CONSTRAINTS.md`, `docs/requirements.md`

Outputs:

- `docs/architecture.md`
- `docs/api-contract.md`
- `docs/data-model.md`

Gate:

```text
ARCH_STATUS: PASS
```

Design must cover requirements, stay inside the approved service catalog, remain serverless/POC-sized, keep frontend storage private, use Python backend + Terraform, and introduce no Route 53/ACM/custom domain.

If the problem is a requirements conflict, route back to BA rather than having Architect invent business behavior.

## IMPLEMENTATION

Owners, run independently and preferably in parallel:

- `frontend-developer`
- `backend-developer`
- `devops-engineer` in **Infrastructure Implementation** mode

### Frontend workstream

Inputs:

- `WORKSHOP_CONSTRAINTS.md`
- `docs/requirements.md`
- `docs/architecture.md`
- `docs/api-contract.md`

Owns: `frontend/`

Output: `docs/frontend-implementation-summary.md`

Gate signal:

```text
FRONTEND_STATUS: PASS
```

### Backend workstream

Inputs:

- `WORKSHOP_CONSTRAINTS.md`
- `docs/requirements.md`
- `docs/architecture.md`
- `docs/api-contract.md`
- `docs/data-model.md`

Owns: `backend/`, backend-focused `tests/`

Output: `docs/backend-implementation-summary.md`

Gate signal:

```text
BACKEND_STATUS: PASS
```

### Infrastructure workstream

Owner: `devops-engineer` in Infrastructure Implementation mode

Inputs: approved requirements/design/contracts.

Owns: `terraform/`

Output: `docs/infrastructure-implementation-summary.md`

Gate signal:

```text
INFRA_STATUS: PASS
```

No deployment is allowed in this mode.

### Implementation gate

Do not enter VALIDATION until all three are PASS:

```text
FRONTEND_STATUS: PASS
BACKEND_STATUS: PASS
INFRA_STATUS: PASS
```

## VALIDATION

Owners, run independently and preferably in parallel:

- `qa-engineer`
- `security-reviewer`

Outputs:

- `docs/qa-report.md`
- `docs/security-report.md`

Gate:

```text
QA_STATUS: PASS
SECURITY_STATUS: PASS
```

### Failure routing

Every blocking QA/Security finding must identify a remediation owner.

The orchestrator must route each finding only to the owner named in the finding:

- frontend behavior → `frontend-developer`
- backend behavior → `backend-developer`
- Terraform/infrastructure → `devops-engineer`
- architecture contract problem → `solution-architect`
- business requirement ambiguity/conflict → `business-analyst`

After any remediation that changes application code or Terraform, rerun **both QA and Security** against the integrated result. The orchestrator may not waive a finding.

## DEPLOYMENT_PREPARATION

Owner: `devops-engineer` in Deployment Preparation mode

Preconditions:

```text
FRONTEND_STATUS: PASS
BACKEND_STATUS: PASS
INFRA_STATUS: PASS
QA_STATUS: PASS
SECURITY_STATUS: PASS
```

Minimum commands:

```bash
terraform fmt -check
terraform init
terraform validate
terraform plan
```

Output: `docs/deployment-plan.md`

Gate:

```text
DEVOPS_STATUS: READY_FOR_APPROVAL
```

The report must summarize add/change/destroy counts, important IAM/security changes, account/region when detectable, validation results, and risks. `terraform apply` is forbidden here.

## AWAITING_HUMAN_APPROVAL

The orchestrator presents the plan summary and stops.

Only this exact participant approval authorizes deployment:

```text
APPROVE DEPLOY
```

## DEPLOYMENT

Owner: `devops-engineer`

After approval only, apply the approved Terraform plan and capture the generated CloudFront and API outputs.

## VERIFICATION

Owner: `devops-engineer`

Smoke-test the actual deployed environment. At minimum verify frontend reachability, health, valid submission, invalid rating rejection, organizer retrieval, and persistence.

Output: `docs/release-report.md`

Required status:

```text
DEVOPS_STATUS: DEPLOYED
```

## COMPLETED

The orchestrator may declare:

```text
SDLC_STATUS: COMPLETED
```

only when every required gate passed, human deployment approval was obtained, deployment succeeded, and live verification passed.

---

# Workflow B — Change request

```text
CHANGE_REQUEST_INTAKE
  ↓
REQUIREMENTS_IMPACT
  ↓
DESIGN_IMPACT
  ↓
IMPLEMENTATION
  ↓
VALIDATION
  ↓
DEPLOYMENT_PREPARATION
  ↓
AWAITING_HUMAN_APPROVAL
  ↓
DEPLOYMENT
  ↓
VERIFICATION
  ↓
COMPLETED
```

## CHANGE_REQUEST_INTAKE

Inputs:

- existing completed release and canonical `docs/`
- `change-requests/CR-XXX.md`

First owner: `business-analyst`.

Never route a CR directly to Frontend or Backend Developer.

## REQUIREMENTS_IMPACT

Owner: `business-analyst`

Inputs: current `docs/requirements.md`, CR file, constraints.

Outputs:

- `docs/change-requests/CR-XXX/requirements-impact.md`
- updated canonical `docs/requirements.md`

Gate: `BA_STATUS: PASS`

The impact artifact must identify changed/new requirements, acceptance criteria, compatibility/legacy assumptions, and out-of-scope impacts.

## DESIGN_IMPACT

Owner: `solution-architect`

Inputs: CR, requirements impact, updated requirements, current architecture/API/data model.

Outputs:

- `docs/change-requests/CR-XXX/architecture-impact.md`
- updated canonical architecture/API/data-model docs where needed

Gate: `ARCH_STATUS: PASS`

The impact must explicitly state which layers are changed or unchanged, including whether AWS topology/IAM/Terraform resource types change.

## IMPLEMENTATION — change request

Invoke only workstreams affected by the approved impact, but require unaffected workstreams to remain compatible with the current contracts.

Typical cross-layer CRs may invoke Frontend and Backend in parallel. Invoke DevOps Infrastructure Implementation mode when Terraform packaging/configuration or infrastructure must change.

Preserve CR implementation evidence under:

```text
docs/change-requests/CR-XXX/
```

Use:

- `frontend-implementation-summary.md` when frontend changed;
- `backend-implementation-summary.md` when backend changed;
- `infrastructure-implementation-summary.md` when Terraform changed.

The canonical application directories represent the current release candidate.

## VALIDATION — change request

Always run both QA and Security after implementation, even if only one application layer changed.

QA must include new acceptance criteria **and regression coverage** for existing behavior.

Write CR-specific reports under:

```text
docs/change-requests/CR-XXX/qa-report.md
docs/change-requests/CR-XXX/security-report.md
```

Gate: both PASS.

Failure routing follows the same remediation-owner rules as the initial workflow.

## DEPLOYMENT PREPARATION / APPROVAL / DEPLOYMENT / VERIFICATION

Repeat the same DevOps and human-approval gates as initial delivery.

Preserve CR-specific:

- `deployment-plan.md`
- `release-report.md`

under `docs/change-requests/CR-XXX/` while canonical docs/application represent the currently deployed system.
