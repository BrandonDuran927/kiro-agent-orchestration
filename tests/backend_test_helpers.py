"""Test helpers: API Gateway event builders and response parsing.

Kept in a dedicated module (not ``tests.conftest``) to avoid collision with an
unrelated ``tests`` package that may exist on ``sys.path`` (e.g. site-packages).
Imported by test modules via ``from backend_test_helpers import ...`` after the
project root is placed on ``sys.path`` by ``conftest.py``.
"""

from __future__ import annotations

import json
from typing import Any, Dict, Optional


def make_http_event(
    method: str,
    path: str,
    body: Optional[Any] = None,
    headers: Optional[Dict[str, str]] = None,
    raw_body: Optional[str] = None,
) -> Dict[str, Any]:
    """Build an API Gateway HTTP API (v2) proxy event."""

    event: Dict[str, Any] = {
        "version": "2.0",
        "routeKey": f"{method} {path}",
        "rawPath": path,
        "headers": headers or {},
        "requestContext": {"http": {"method": method, "path": path}},
        "isBase64Encoded": False,
    }
    if raw_body is not None:
        event["body"] = raw_body
    elif body is not None:
        event["body"] = json.dumps(body)
    return event


def parse_body(response: Dict[str, Any]) -> Dict[str, Any]:
    return json.loads(response["body"])
