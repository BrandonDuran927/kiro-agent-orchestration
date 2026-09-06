# Agent JSON Configuration Guide

The supplied specialist agents use a thin JSON registration plus a detailed external Markdown prompt.

## Pattern

```text
.kiro/agents/<agent>.json
        │
        ├── reusable role description
        ├── prompt file reference
        ├── available tools
        ├── auto-approved tools
        ├── scoped permissions
        └── project resources
                │
                ▼
agent-prompts/<agent>.md
        └── expert role, process, standards, boundaries, inputs, outputs, status contract
```

## Design principle

The agents are **general experts**, not one-off personas for this application.

Challenge-specific behavior comes from:

- `WORKSHOP_CONSTRAINTS.md`;
- approved requirements and architecture;
- task instructions supplied by the orchestrator.

For example, the Backend Developer is a reusable senior backend engineer. In this challenge the approved architecture selects Python + Lambda + DynamoDB, so the same expert follows those constraints without making that stack part of its permanent identity.

## Important JSON fields

- `prompt` — points to the detailed Markdown prompt using `file://`.
- `tools` — capabilities the agent may use.
- `allowedTools` — safe tools that can run without a confirmation prompt.
- `permissions.rules` — role-specific filesystem and shell boundaries.
- `resources` — static project context available to the agent.
- `toolsSettings.subagent` — used by the orchestrator to restrict which agents it can delegate to and which are trusted.

## Capability boundaries

Permissions reinforce role ownership:

- Frontend Developer writes frontend files and its implementation summary only.
- Backend Developer writes backend/backend-focused tests and may run approved Python test/compile commands.
- Business Analyst writes requirements/change-impact artifacts only.
- Solution Architect writes architecture/API/data-model artifacts only.
- QA writes QA-owned tests/reports but not production code.
- Security writes security reports but not implementation.
- DevOps writes Terraform/release artifacts and runs approved Terraform/AWS verification commands.
- Orchestrator delegates and manages lifecycle state but does not implement specialist work.

The Markdown prompt defines **how an expert should work**. JSON permissions define **what the agent is technically allowed to do**. Both layers matter.

## Reuse on another project

To reuse an agent:

1. keep its general role prompt;
2. replace or add project-specific constraints/resources;
3. adjust filesystem/shell permissions to the new repository layout;
4. let approved Architecture choose the technology stack;
5. avoid rewriting the agent identity around a single project name.
