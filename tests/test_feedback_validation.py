"""POST /feedback validation & boundary rejection tests.

Covers FR-003, FR-005, BR-001..BR-005, BR-008, AC-003..AC-006.
Every 400 must persist nothing and return the contract error shape.
"""

from __future__ import annotations

import pytest

from backend.handler import handler
from backend_test_helpers import make_http_event, parse_body


def _assert_validation_error(resp, field: str):
    assert resp["statusCode"] == 400
    body = parse_body(resp)
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert "message" in body["error"]
    fields = {d["field"] for d in body["error"]["details"]}
    assert field in fields


def test_missing_rating_rejected(repo, config):
    # AC-003
    event = make_http_event("POST", "/feedback", body={"workshopId": "ws"})
    resp = handler(event, repo=repo, config=config)
    _assert_validation_error(resp, "rating")
    assert repo.items == []


def test_null_rating_rejected(repo, config):
    event = make_http_event(
        "POST", "/feedback", body={"workshopId": "ws", "rating": None}
    )
    resp = handler(event, repo=repo, config=config)
    _assert_validation_error(resp, "rating")
    assert repo.items == []


@pytest.mark.parametrize("rating", [0, 6, -1, 100])
def test_out_of_range_rating_rejected(repo, config, rating):
    # AC-004
    event = make_http_event(
        "POST", "/feedback", body={"workshopId": "ws", "rating": rating}
    )
    resp = handler(event, repo=repo, config=config)
    _assert_validation_error(resp, "rating")
    assert repo.items == []


@pytest.mark.parametrize("rating", [3.5, 4.0, "4", True, False, [4], {"v": 4}])
def test_non_integer_rating_rejected(repo, config, rating):
    # BR-001/BR-002: reject fractional, string, bool, and structured ratings.
    event = make_http_event(
        "POST", "/feedback", body={"workshopId": "ws", "rating": rating}
    )
    resp = handler(event, repo=repo, config=config)
    _assert_validation_error(resp, "rating")
    assert repo.items == []


def test_missing_workshop_id_rejected(repo, config):
    # AC-005 (missing)
    event = make_http_event("POST", "/feedback", body={"rating": 4})
    resp = handler(event, repo=repo, config=config)
    _assert_validation_error(resp, "workshopId")
    assert repo.items == []


@pytest.mark.parametrize("workshop_id", ["", "   ", "\t\n"])
def test_empty_or_whitespace_workshop_id_rejected(repo, config, workshop_id):
    # AC-005 (empty / whitespace-only)
    event = make_http_event(
        "POST", "/feedback", body={"workshopId": workshop_id, "rating": 4}
    )
    resp = handler(event, repo=repo, config=config)
    _assert_validation_error(resp, "workshopId")
    assert repo.items == []


def test_non_string_workshop_id_rejected(repo, config):
    event = make_http_event(
        "POST", "/feedback", body={"workshopId": 123, "rating": 4}
    )
    resp = handler(event, repo=repo, config=config)
    _assert_validation_error(resp, "workshopId")
    assert repo.items == []


def test_workshop_id_over_max_length_rejected(repo, config):
    event = make_http_event(
        "POST", "/feedback", body={"workshopId": "x" * 201, "rating": 4}
    )
    resp = handler(event, repo=repo, config=config)
    _assert_validation_error(resp, "workshopId")
    assert repo.items == []


def test_comment_over_max_length_rejected(repo, config):
    # AC-006
    event = make_http_event(
        "POST",
        "/feedback",
        body={"workshopId": "ws", "rating": 4, "comment": "x" * 1001},
    )
    resp = handler(event, repo=repo, config=config)
    _assert_validation_error(resp, "comment")
    assert repo.items == []


def test_multiple_errors_reported_together(repo, config):
    event = make_http_event(
        "POST", "/feedback", body={"workshopId": "", "rating": 9}
    )
    resp = handler(event, repo=repo, config=config)
    assert resp["statusCode"] == 400
    fields = {d["field"] for d in parse_body(resp)["error"]["details"]}
    assert {"workshopId", "rating"} <= fields
    assert repo.items == []


def test_malformed_json_body_rejected(repo, config):
    event = make_http_event("POST", "/feedback", raw_body="{not valid json")
    resp = handler(event, repo=repo, config=config)
    assert resp["statusCode"] == 400
    assert parse_body(resp)["error"]["code"] == "MALFORMED_REQUEST"
    assert repo.items == []


def test_empty_body_reports_required_fields(repo, config):
    event = make_http_event("POST", "/feedback")  # no body at all
    resp = handler(event, repo=repo, config=config)
    assert resp["statusCode"] == 400
    fields = {d["field"] for d in parse_body(resp)["error"]["details"]}
    assert {"workshopId", "rating"} <= fields
    assert repo.items == []


def test_persistence_failure_returns_500_generic(repo, config):
    repo.raise_on_put = True
    event = make_http_event(
        "POST", "/feedback", body={"workshopId": "ws", "rating": 4}
    )
    resp = handler(event, repo=repo, config=config)
    assert resp["statusCode"] == 500
    body = parse_body(resp)
    assert body["error"]["code"] == "INTERNAL_ERROR"
    # No stack trace / internals leaked.
    assert "Traceback" not in body["error"]["message"]
