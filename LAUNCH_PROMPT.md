# Launch Prompt

After creating and selecting your `sdlc-orchestrator` agent, send it this prompt:

```text
Take BUSINESS_REQUEST.md through the complete SDLC defined in SDLC_WORKFLOW.md.

Follow WORKSHOP_CONSTRAINTS.md and use the supplied specialist agents for their assigned responsibilities. Run independent work in parallel where the workflow allows it.

You are responsible for orchestration only. Do not perform specialist work yourself.

Ask me only when:
1. the Business Analyst requires stakeholder clarification, or
2. DevOps has completed terraform plan and deployment requires my explicit approval.

Do not deploy until I say exactly: APPROVE DEPLOY

Begin from the correct workflow entry state.
```

For a facilitator-provided change request later, tell the same orchestrator:

```text
Process change-requests/CR-001.md through the change-request workflow in SDLC_WORKFLOW.md. Preserve the CR audit artifacts and do not deploy until I say exactly: APPROVE DEPLOY
```
