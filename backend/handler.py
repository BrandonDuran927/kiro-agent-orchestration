"""AWS Lambda handler for the Workshop Feedback Portal (POC).

Single, path-routed Python function behind an API Gateway HTTP API (v2 payload),
per docs/architecture.md (ADR-2) and docs/api-contract.md.

Routes:
- ``GET  /health``   — service health (FR-010, AC-010); no auth.
- ``POST /feedback``  — submit feedback (FR-002..FR-006); no auth; server-side
  validation; persists then returns 201.
- ``GET  /feedback``  — list feedback (FR-007..FR-009); gated by the
  ``X-Organizer-Key`` header (401 missing / 403 invalid; A-005, BR-006).

Transport parsing, validation, and persistence are kept as distinct concerns.
Business logic is exercised through injectable dependencies so tests never need
AWS credentials or a network.
"""

from __future__ import annotations

import hmac
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from .config import Config, load_config
from .repository import FeedbackRepository, build_default_repository
from .validation import validate_feedback

logger = logging.getLogger()
if not logger.handlers:
    logging.basicConfig()
logger.setLevel(logging.INFO)

ORGANIZER_HEADER = "x-organizer-key"  # header names are matched case-insensitively

# Error codes (api-contract 1 / 2.x)
CODE_VALIDATION = "VALIDATION_ERROR"
CODE_MALFORMED = "MALFORMED_REQUEST"
CODE_UNAUTHORIZED = "UNAUTHORIZED"
CODE_FORBIDDEN = "FORBIDDEN"
CODE_NOT_FOUND = "NOT_FOUND"
CODE_INTERNAL = "INTERNAL_ERROR"

_JSON_HEADERS = {"Content-Type": "application/json"}


# --------------------------------------------------------------------------- #
# HTTP response helpers
# --------------------------------------------------------------------------- #
def _response(status: int, body: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "statusCode": status,
        "headers": dict(_JSON_HEADERS),
        "body": json.dumps(body),
    }


def _error(
    status: int,
    code: str,
    message: str,
    details: Optional[List[Dict[str, str]]] = None,
) -> Dict[str, Any]:
    err: Dict[str, Any] = {"code": code, "message": message}
    if details:
        err["details"] = details
    return _response(status, {"error": err})


# --------------------------------------------------------------------------- #
# Event parsing (API Gateway HTTP API v2, with REST v1 fallback)
# --------------------------------------------------------------------------- #
def _extract_method_and_path(event: Dict[str, Any]) -> tuple[str, str]:
    """Return (METHOD, path) from an API Gateway event.

    Supports HTTP API (v2) ``requestContext.http`` and falls back to REST (v1)
    ``httpMethod`` / ``path`` so the handler is robust to integration shape.
    """

    ctx = event.get("requestContext") or {}
    http = ctx.get("http") or {}
    method = http.get("method") or event.get("httpMethod") or ""
    path = (
        http.get("path")
        or event.get("rawPath")
        or event.get("path")
        or ""
    )
    return method.upper(), _normalize_path(path)


def _normalize_path(path: str) -> str:
    """Strip a trailing slash (except root) and any stage prefix noise."""

    if not path:
        return "/"
    if len(path) > 1 and path.endswith("/"):
        path = path.rstrip("/")
    return path or "/"


def _get_header(event: Dict[str, Any], name: str) -> Optional[str]:
    headers = event.get("headers") or {}
    target = name.lower()
    for key, value in headers.items():
        if key.lower() == target:
            return value
    return None


def _parse_json_body(event: Dict[str, Any]) -> tuple[Optional[Any], bool]:
    """Parse the request body as JSON.

    Returns ``(parsed, ok)``. ``ok`` is False when the body is not valid JSON.
    An empty/absent body parses to ``None`` with ``ok=True`` so validation can
    report the missing required fields.
    """

    raw = event.get("body")
    if raw is None or raw == "":
        return None, True

    if event.get("isBase64Encoded"):
        import base64

        try:
            raw = base64.b64decode(raw).decode("utf-8")
        except Exception:
            return None, False

    try:
        return json.loads(raw), True
    except (ValueError, TypeError):
        return None, False


# --------------------------------------------------------------------------- #
# Route handlers
# --------------------------------------------------------------------------- #
def handle_health() -> Dict[str, Any]:
    return _response(200, {"status": "ok"})


def handle_create_feedback(
    event: Dict[str, Any], repo: FeedbackRepository, now: Callable[[], datetime]
) -> Dict[str, Any]:
    body, ok = _parse_json_body(event)
    if not ok:
        return _error(
            400, CODE_MALFORMED, "Request body must be valid JSON."
        )

    result = validate_feedback(body)
    if not result.ok:
        return _error(
            400,
            CODE_VALIDATION,
            "One or more fields are invalid.",
            details=[i.to_dict() for i in result.issues],
        )

    feedback = result.value
    assert feedback is not None
    feedback_id = str(uuid.uuid4())
    created_at = _iso_utc(now())

    item: Dict[str, Any] = {
        "feedbackId": feedback_id,
        "workshopId": feedback.workshop_id,
        "rating": feedback.rating,
        "createdAt": created_at,
    }
    # Omit comment attribute entirely when absent (data-model.md section 2).
    if feedback.comment is not None:
        item["comment"] = feedback.comment

    try:
        repo.put(item)
    except Exception:  # pragma: no cover - defensive; exercised via injected repo
        logger.exception("Failed to persist feedback record")
        return _error(
            500, CODE_INTERNAL, "An unexpected error occurred."
        )

    logger.info(
        "feedback.created feedbackId=%s workshopId=%s rating=%s hasComment=%s",
        feedback_id,
        feedback.workshop_id,
        feedback.rating,
        feedback.comment is not None,
    )

    return _response(
        201,
        {
            "feedbackId": feedback_id,
            "workshopId": feedback.workshop_id,
            "rating": feedback.rating,
            "comment": feedback.comment,  # null when no comment
            "createdAt": created_at,
            "message": "Feedback submitted successfully.",
        },
    )


def handle_list_feedback(
    event: Dict[str, Any], repo: FeedbackRepository, config: Config
) -> Dict[str, Any]:
    provided = _get_header(event, ORGANIZER_HEADER)

    if provided is None:
        return _error(
            401, CODE_UNAUTHORIZED, "Organizer key is required."
        )

    if not _keys_match(provided, config.organizer_key):
        return _error(403, CODE_FORBIDDEN, "Organizer key is invalid.")

    try:
        items = repo.scan_all()
    except Exception:  # pragma: no cover - defensive
        logger.exception("Failed to scan feedback records")
        return _error(
            500, CODE_INTERNAL, "An unexpected error occurred."
        )

    normalized = [_to_api_item(i) for i in items]
    return _response(200, {"items": normalized, "count": len(normalized)})


# --------------------------------------------------------------------------- #
# Utilities
# --------------------------------------------------------------------------- #
def _iso_utc(dt: datetime) -> str:
    """Format a datetime as ISO-8601 UTC with a trailing ``Z`` (seconds)."""

    dt = dt.astimezone(timezone.utc).replace(microsecond=0)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _keys_match(provided: str, expected: str) -> bool:
    """Constant-time comparison of organizer keys.

    Returns False if the server has no key configured, so a misconfiguration
    cannot accidentally allow access.
    """

    if not expected:
        return False
    return hmac.compare_digest(provided, expected)


def _to_api_item(item: Dict[str, Any]) -> Dict[str, Any]:
    """Project a stored item onto the API list shape (AC-008).

    ``rating`` may arrive from DynamoDB as ``Decimal``; coerce to int.
    ``comment`` is ``null`` when absent.
    """

    rating = item.get("rating")
    try:
        rating = int(rating) if rating is not None else None
    except (TypeError, ValueError):
        rating = None

    return {
        "feedbackId": item.get("feedbackId"),
        "workshopId": item.get("workshopId"),
        "rating": rating,
        "comment": item.get("comment") if item.get("comment") not in ("", None) else None,
        "createdAt": item.get("createdAt"),
    }


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #
def handler(
    event: Dict[str, Any],
    context: Any = None,
    *,
    repo: Optional[FeedbackRepository] = None,
    config: Optional[Config] = None,
    now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
) -> Dict[str, Any]:
    """Lambda entry point. Optional keyword args support dependency injection
    in tests; production invocations supply only ``event`` and ``context``.
    """

    try:
        cfg = config or load_config()
        method, path = _extract_method_and_path(event or {})

        if method == "GET" and path == "/health":
            return handle_health()

        if method == "POST" and path == "/feedback":
            repository = repo or build_default_repository(cfg.table_name)
            return handle_create_feedback(event, repository, now)

        if method == "GET" and path == "/feedback":
            repository = repo or build_default_repository(cfg.table_name)
            return handle_list_feedback(event, repository, cfg)

        return _error(
            404, CODE_NOT_FOUND, f"No route for {method} {path}."
        )
    except Exception:  # pragma: no cover - top-level safety net
        logger.exception("Unhandled error in handler")
        return _error(500, CODE_INTERNAL, "An unexpected error occurred.")


# AWS Lambda default handler alias (module.lambda_handler)
lambda_handler = handler
