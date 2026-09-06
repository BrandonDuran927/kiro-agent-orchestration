"""Environment-based configuration for the Feedback backend.

No secrets or resource identifiers are hardcoded. Terraform injects these
values into the Lambda environment (docs/architecture.md section 7):

- ``FEEDBACK_TABLE_NAME`` — DynamoDB table name (data-model.md).
- ``ORGANIZER_KEY``      — shared organizer access key (api-contract 2.3, A-005).

Configuration is read lazily so unit tests can set/patch the environment
without a deployed stack.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

TABLE_NAME_ENV = "FEEDBACK_TABLE_NAME"
ORGANIZER_KEY_ENV = "ORGANIZER_KEY"


@dataclass(frozen=True)
class Config:
    """Resolved runtime configuration."""

    table_name: str
    organizer_key: str


def load_config() -> Config:
    """Read configuration from the process environment.

    Returns a :class:`Config`. Missing values resolve to empty strings so the
    handler can fail safely (500 for missing table, 401/403 for organizer
    checks) rather than raising at import time.
    """

    return Config(
        table_name=os.environ.get(TABLE_NAME_ENV, ""),
        organizer_key=os.environ.get(ORGANIZER_KEY_ENV, ""),
    )
