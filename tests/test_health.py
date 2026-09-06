"""Health endpoint tests — FR-010 / AC-010."""

from __future__ import annotations

from backend.handler import handler
from backend_test_helpers import make_http_event, parse_body


def test_health_returns_200_ok(repo, config):
    event = make_http_event("GET", "/health")
    resp = handler(event, repo=repo, config=config)

    assert resp["statusCode"] == 200
    assert resp["headers"]["Content-Type"] == "application/json"
    assert parse_body(resp) == {"status": "ok"}


def test_health_requires_no_auth(repo, config):
    # No X-Organizer-Key header present; health must still return 200.
    event = make_http_event("GET", "/health", headers={})
    resp = handler(event, repo=repo, config=config)
    assert resp["statusCode"] == 200


def test_health_trailing_slash_normalized(repo, config):
    event = make_http_event("GET", "/health/")
    resp = handler(event, repo=repo, config=config)
    assert resp["statusCode"] == 200
