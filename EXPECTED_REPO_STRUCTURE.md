# Expected Repository Shape

Exact implementation filenames may vary, but a successful submission should contain the participant-created orchestrator, seven supplied specialists, auditable SDLC artifacts, application code, tests, and Terraform.

After the initial release:

```text
feedback-portal/
├── BUSINESS_REQUEST.md
├── WORKSHOP_CONSTRAINTS.md
├── SDLC_WORKFLOW.md
├── .kiro/
│   └── agents/
│       ├── sdlc-orchestrator.json          # participant-created
│       ├── business-analyst.json
│       ├── solution-architect.json
│       ├── frontend-developer.json
│       ├── backend-developer.json
│       ├── qa-engineer.json
│       ├── security-reviewer.json
│       └── devops-engineer.json
├── agent-prompts/
│   ├── sdlc-orchestrator.md                # participant-created
│   ├── business-analyst.md
│   ├── solution-architect.md
│   ├── frontend-developer.md
│   ├── backend-developer.md
│   ├── qa-engineer.md
│   ├── security-reviewer.md
│   └── devops-engineer.md
├── docs/
│   ├── requirements.md
│   ├── architecture.md
│   ├── api-contract.md
│   ├── data-model.md
│   ├── frontend-implementation-summary.md
│   ├── backend-implementation-summary.md
│   ├── infrastructure-implementation-summary.md
│   ├── qa-report.md
│   ├── security-report.md
│   ├── deployment-plan.md
│   └── release-report.md
├── frontend/
├── backend/
├── tests/
└── terraform/
```

After a change request such as `CR-001`, preserve its audit trail:

```text
├── change-requests/
│   └── CR-001.md
└── docs/
    └── change-requests/
        └── CR-001/
            ├── requirements-impact.md
            ├── architecture-impact.md
            ├── frontend-implementation-summary.md      # if frontend changed
            ├── backend-implementation-summary.md       # if backend changed
            ├── infrastructure-implementation-summary.md # if Terraform changed
            ├── qa-report.md
            ├── security-report.md
            ├── deployment-plan.md
            └── release-report.md
```

Canonical files under `docs/` and the application directories represent the **current deployed system**. CR folders explain how each change moved through the lifecycle.
