# Orchestrator Integration Assignment

In the previous module, you already created a general orchestrator. In this module, **adapt that existing orchestrator into an SDLC orchestrator**.

Seven specialist agents are supplied:

- Business Analyst
- Solution Architect
- Frontend Developer
- Backend Developer
- QA Engineer
- Security Reviewer
- DevOps Engineer

Your existing orchestrator becomes the eighth agent in this multi-agent system.

## Files your orchestrator must use

Treat these repository files as the source of truth:

- `SDLC_WORKFLOW.md` — authoritative lifecycle and gate rules
- `WORKSHOP_CONSTRAINTS.md` — fixed engineering boundaries
- `BUSINESS_REQUEST.md` — initial business request

Do not copy the workflow into the chat prompt. The orchestrator should read it from the repository.

## Update your orchestrator JSON registration

Keep your existing orchestrator prompt/behavior, but make sure its JSON registration has the equivalent of the following structure:

```json
{
  "name": "sdlc-orchestrator",
  "description": "Coordinates specialist agents through the defined SDLC without performing specialist work itself.",
  "prompt": "file://./agent-prompts/sdlc-orchestrator.md",
  "tools": ["read", "subagent"],
  "allowedTools": ["read"],
  "toolsSettings": {
    "subagent": {
      "availableAgents": [
        "business-analyst",
        "solution-architect",
        "frontend-developer",
        "backend-developer",
        "qa-engineer",
        "security-reviewer",
        "devops-engineer"
      ],
      "trustedAgents": [
        "business-analyst",
        "solution-architect",
        "frontend-developer",
        "backend-developer",
        "qa-engineer",
        "security-reviewer",
        "devops-engineer"
      ]
    }
  },
  "resources": [
    "file://./SDLC_WORKFLOW.md",
    "file://./WORKSHOP_CONSTRAINTS.md",
    "file://./BUSINESS_REQUEST.md"
  ]
}
```

You may preserve additional safe capabilities from your previous orchestrator, but the orchestrator must not gain application-code or deployment ownership.

## Required orchestrator behavior

Adapt your orchestrator prompt so it can:

1. distinguish initial delivery from a change request;
2. track and report current SDLC state;
3. invoke only agents allowed by the current state;
4. pass the correct approved artifacts to each specialist;
5. run Frontend + Backend + DevOps infrastructure implementation in parallel where supported;
6. run QA + Security validation in parallel where supported;
7. validate terminal status signals before transitioning;
8. route validation findings using `REMEDIATION_OWNER`;
9. rerun validation after remediation;
10. preserve CR-specific audit artifacts;
11. ask the human only for BA stakeholder blockers or deployment approval;
12. never allow Terraform apply until the participant explicitly says `APPROVE DEPLOY`;
13. require live smoke verification before `SDLC_STATUS: COMPLETED`.

## Minimum expected routing

```text
BA PASS
→ Architect

Architect PASS
→ Frontend Developer + Backend Developer + DevOps (Terraform implementation)

Frontend PASS + Backend PASS + Infra PASS
→ QA + Security

QA/Security FAIL
→ route finding to REMEDIATION_OWNER
→ rerun QA + Security

QA PASS + Security PASS
→ DevOps terraform plan
→ Human approval
→ DevOps terraform apply + smoke tests
```

## Change request routing

```text
CR-XXX
→ Business Analyst impact analysis
→ Solution Architect impact analysis
→ affected implementation workstreams
→ QA + Security regression validation
→ DevOps plan
→ Human approval
→ redeploy + verify
```

A change request must never go directly to Frontend Developer, Backend Developer, or DevOps implementation.

## What you should change

Normally you will update your existing:

```text
.kiro/agents/<your-orchestrator>.json
agent-prompts/<your-orchestrator>.md
```

You do not have to rename it to `sdlc-orchestrator` as long as it satisfies the required behavior and can invoke all supplied specialists.
