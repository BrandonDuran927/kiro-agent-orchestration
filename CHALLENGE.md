# Challenge — Workshop Feedback Portal

Your team has received the business request in `BUSINESS_REQUEST.md`.

Your goal is to build an **SDLC Orchestrator Agent** that can take that request from requirements elicitation through a verified AWS deployment using the supplied specialists and the process in `SDLC_WORKFLOW.md`.

Seven specialist agents are already supplied. You create only the orchestrator.

## Success means

- BA turns the business brief into testable requirements;
- Architect derives a compliant POC architecture from requirements + constraints;
- Frontend and Backend Developers implement their layers independently, preferably in parallel;
- DevOps implements Terraform from the approved architecture;
- QA and Security independently validate the integrated result;
- failures are automatically routed to the correct remediation owner;
- DevOps prepares a Terraform plan;
- the workflow stops for explicit human deployment approval;
- DevOps deploys and smoke-tests the real AWS environment;
- the orchestrator reports `SDLC_STATUS: COMPLETED` only after live verification.

Later, you will receive a change request. Your same orchestrator must re-enter the SDLC through BA impact analysis rather than sending the change directly to a developer.
