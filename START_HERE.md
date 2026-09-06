# Start Here — Multi-Agent Orchestration with SDLC

In this module you will build **one orchestration agent** and use it to coordinate **seven supplied specialist agents** through a complete SDLC.

You are **not** expected to create the BA, Architect, Frontend Developer, Backend Developer, QA, Security, or DevOps agents. Those are provided.

## Your job

1. Read `CHALLENGE.md`.
2. Read `ORCHESTRATOR_INTEGRATION.md`.
3. Create:
   - `.kiro/agents/sdlc-orchestrator.json`
   - `agent-prompts/sdlc-orchestrator.md`
4. Make your orchestrator use `SDLC_WORKFLOW.md` and `WORKSHOP_CONSTRAINTS.md`.
5. Allow it to delegate to all seven supplied specialists.
6. Select your orchestrator agent.
7. Use the prompt in `LAUNCH_PROMPT.md`.
8. Answer stakeholder questions only when BA asks through the orchestrator.
9. Review and explicitly approve deployment only after DevOps prepares the Terraform plan.
10. Later, process the facilitator-provided change request through the same orchestrator.

## Do not

- manually invoke specialists during the SDLC run;
- give Frontend/Backend implementation instructions directly;
- manually fix QA/Security findings;
- bypass failed gates;
- deploy before the explicit approval point;
- inspect the facilitator reference solution.

## Agent configuration model

The supplied specialist registrations under `.kiro/agents/` use thin JSON configs with external prompt files. Each JSON limits tools, write paths, and shell commands to the agent's role. Your orchestrator should follow the same pattern and use explicit sub-agent allow/trust lists.
