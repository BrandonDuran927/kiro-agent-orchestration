"""POST /feedback happy-path & persistence tests.

Covers FR-002, FR-004, FR-006, AC-001, AC-002, AC-007.
"""

from __future__ import annotations

import re

from backend.handler import handler
from backend_test_helpers import make_http_event, parse_body

UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
)
ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


def test_submit_valid_feedback_returns_201_and_persists(repo, config, fixed_now):
    event = make_http_event(
        "POST",
        "/feedback",
        body={
            "workshopId": "aws-serverless-2026-09",
            "rating": 4,
            "comment": "Great pacing, more hands-on labs please.",
        },
    )
    resp = handler(event, repo=repo, config=config, now=fixed_now)

    assert resp["statusCode"] == 201
    body = parse_body(resp)
    assert body["workshopId"] == "aws-serverless-2026-09"
    assert body["rating"] == 4
    assert body["comment"] == "Great pacing, more hands-on labs please."
    assert body["message"] == "Feedback submitted successfully."
    assert UUID_RE.match(body["feedbackId"])
    assert body["createdAt"] == "2026-09-05T08:34:33Z"
    assert ISO_RE.match(body["createdAt"])

    # AC-002: record persisted with all fields.
    assert len(repo.items) == 1
    stored = repo.items[0]
    assert stored["feedbackId"] == body["feedbackId"]
    assert stored["workshopId"] == "aws-serverless-2026-09"
    assert stored["rating"] == 4
    assert stored["comment"] == "Great pacing, more hands-on labs please."
    assert stored["createdAt"] == "2026-09-05T08:34:33Z"


def test_submit_without_comment_persists_and_returns_null_comment(repo, config):
    # AC-007: comment optional. Store omits comment; API returns null.
    event = make_http_event(
        "POST", "/feedback", body={"workshopId": "ws-1", "rating": 5}
    )
    resp = handler(event, repo=repo, config=config)

    assert resp["statusCode"] == 201
    body = parse_body(resp)
    assert body["comment"] is None
    assert len(repo.items) == 1
    assert "comment" not in repo.items[0]  # attribute omitted in store


def test_empty_string_comment_treated_as_no_comment(repo, config):
    event = make_http_event(
        "POST", "/feedback", body={"workshopId": "ws-1", "rating": 3, "comment": ""}
    )
    resp = handler(event, repo=repo, config=config)
    assert resp["statusCode"] == 201
    assert parse_body(resp)["comment"] is None
    assert "comment" not in repo.items[0]


def test_boundary_ratings_1_and_5_accepted(repo, config):
    for rating in (1, 5):
        event = make_http_event(
            "POST", "/feedback", body={"workshopId": "ws", "rating": rating}
        )
        resp = handler(event, repo=repo, config=config)
        assert resp["statusCode"] == 201
        assert parse_body(resp)["rating"] == rating
    assert len(repo.items) == 2


def test_unknown_fields_are_ignored(repo, config):
    event = make_http_event(
        "POST",
        "/feedback",
        body={"workshopId": "ws", "rating": 4, "extra": "ignored", "admin": True},
    )
    resp = handler(event, repo=repo, config=config)
    assert resp["statusCode"] == 201
    stored = repo.items[0]
    assert "extra" not in stored and "admin" not in stored


def test_workshop_id_is_trimmed(repo, config):
    event = make_http_event(
        "POST", "/feedback", body={"workshopId": "  ws-trim  ", "rating": 2}
    )
    resp = handler(event, repo=repo, config=config)
    assert resp["statusCode"] == 201
    assert parse_body(resp)["workshopId"] == "ws-trim"


def test_comment_at_max_length_accepted(repo, config):
    comment = "x" * 1000
    event = make_http_event(
        "POST", "/feedback", body={"workshopId": "ws", "rating": 3, "comment": comment}
    )
    resp = handler(event, repo=repo, config=config)
    assert resp["statusCode"] == 201
    assert parse_body(resp)["comment"] == comment
