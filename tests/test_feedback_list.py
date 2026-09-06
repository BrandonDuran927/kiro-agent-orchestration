"""GET /feedback organizer-gated retrieval tests.

Covers FR-007, FR-008, FR-009, BR-006, A-005, AC-008, AC-009.
"""

from __future__ import annotations

from decimal import Decimal

from backend.handler import handler
from backend_test_helpers import make_http_event, parse_body

VALID_KEY = "s3cr3t-organizer-key"


def _seed(repo, comment="Nice"):
    repo.items.append(
        {
            "feedbackId": "6f9619ff-8b86-4d01-b42d-00cf4fc964ff",
            "workshopId": "aws-serverless-2026-09",
            "rating": 4,
            "comment": comment,
            "createdAt": "2026-09-05T08:34:33Z",
        }
    )


def test_missing_organizer_key_returns_401(repo, config):
    _seed(repo)
    event = make_http_event("GET", "/feedback", headers={})
    resp = handler(event, repo=repo, config=config)
    assert resp["statusCode"] == 401
    body = parse_body(resp)
    assert body["error"]["code"] == "UNAUTHORIZED"
    assert "items" not in body  # AC-009: no data leaked


def test_invalid_organizer_key_returns_403(repo, config):
    _seed(repo)
    event = make_http_event(
        "GET", "/feedback", headers={"X-Organizer-Key": "wrong-key"}
    )
    resp = handler(event, repo=repo, config=config)
    assert resp["statusCode"] == 403
    body = parse_body(resp)
    assert body["error"]["code"] == "FORBIDDEN"
    assert "items" not in body


def test_valid_organizer_key_returns_items(repo, config):
    _seed(repo)
    event = make_http_event(
        "GET", "/feedback", headers={"X-Organizer-Key": VALID_KEY}
    )
    resp = handler(event, repo=repo, config=config)
    assert resp["statusCode"] == 200
    body = parse_body(resp)
    assert body["count"] == 1
    item = body["items"][0]
    assert item["workshopId"] == "aws-serverless-2026-09"
    assert item["rating"] == 4
    assert item["comment"] == "Nice"
    assert item["createdAt"] == "2026-09-05T08:34:33Z"
    assert item["feedbackId"] == "6f9619ff-8b86-4d01-b42d-00cf4fc964ff"


def test_header_name_is_case_insensitive(repo, config):
    _seed(repo)
    event = make_http_event(
        "GET", "/feedback", headers={"x-organizer-key": VALID_KEY}
    )
    resp = handler(event, repo=repo, config=config)
    assert resp["statusCode"] == 200


def test_empty_collection_returns_empty_list(repo, config):
    event = make_http_event(
        "GET", "/feedback", headers={"X-Organizer-Key": VALID_KEY}
    )
    resp = handler(event, repo=repo, config=config)
    assert resp["statusCode"] == 200
    assert parse_body(resp) == {"items": [], "count": 0}


def test_item_without_comment_returned_as_null(repo, config):
    repo.items.append(
        {
            "feedbackId": "a1b2c3d4-0000-4aaa-9bbb-ccccdddd1111",
            "workshopId": "ws",
            "rating": 5,
            "createdAt": "2026-09-05T08:40:10Z",
        }
    )
    event = make_http_event(
        "GET", "/feedback", headers={"X-Organizer-Key": VALID_KEY}
    )
    resp = handler(event, repo=repo, config=config)
    assert parse_body(resp)["items"][0]["comment"] is None


def test_dynamodb_decimal_rating_coerced_to_int(repo, config):
    repo.items.append(
        {
            "feedbackId": "id",
            "workshopId": "ws",
            "rating": Decimal("5"),  # DynamoDB returns numbers as Decimal
            "createdAt": "2026-09-05T08:40:10Z",
        }
    )
    event = make_http_event(
        "GET", "/feedback", headers={"X-Organizer-Key": VALID_KEY}
    )
    resp = handler(event, repo=repo, config=config)
    item = parse_body(resp)["items"][0]
    assert item["rating"] == 5
    assert isinstance(item["rating"], int)


def test_no_server_key_configured_denies_access(repo):
    from backend.config import Config

    cfg = Config(table_name="T", organizer_key="")
    _seed(repo)
    event = make_http_event(
        "GET", "/feedback", headers={"X-Organizer-Key": "anything"}
    )
    resp = handler(event, repo=repo, config=cfg)
    assert resp["statusCode"] == 403


def test_scan_failure_returns_500_generic(repo, config):
    repo.raise_on_scan = True
    event = make_http_event(
        "GET", "/feedback", headers={"X-Organizer-Key": VALID_KEY}
    )
    resp = handler(event, repo=repo, config=config)
    assert resp["statusCode"] == 500
    assert parse_body(resp)["error"]["code"] == "INTERNAL_ERROR"
