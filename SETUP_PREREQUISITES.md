# Participant Setup Prerequisites

This module assumes Kiro IDE is already installed and configured.

Before the SDLC exercise begins, verify the following tools are available:

```bash
aws --version
terraform version
python --version
python -m pytest --version
```

## Required local tooling

- Kiro IDE
- AWS CLI
- Terraform CLI
- Python 3.12+ recommended for local workshop tests
- pytest
- Git

## AWS access

The facilitator should provide temporary workshop credentials or a workshop AWS account/role.

The participant should be able to run:

```bash
aws sts get-caller-identity
```

The role should be scoped to the services allowed by `WORKSHOP_CONSTRAINTS.md` and to workshop resources where practical.

## No custom domain setup

Participants do not need:

- a purchased domain,
- Route 53 configuration,
- ACM certificate setup,
- DNS changes.

Terraform will expose the generated CloudFront distribution URL for frontend access.
