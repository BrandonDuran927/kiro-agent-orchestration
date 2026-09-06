"""Server-authoritative validation for feedback submissions.

All rules mirror docs/api-contract.md (2.2) and docs/data-model.md (section 5),
enforced server-side before any persistence (BR-008, FR-003, FR-005).

Rules:
- ``workshopId``: required string, non-empty after trimming, max 200 chars (BR-004).
- ``rating``: required integer 1-5 inclusive; must be a JSON number with no
  fractional part; reject non-integer, string, bool, null, out-of-range
  (BR-001, BR-002, BR-003).
- ``comment``: optional string, max 1000 chars when present; omitted / null /
  empty string all mean "no comment" (BR-005).

Unknown fields are ignored (not an error) per the contract.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

WORKSHOP_ID_MAX_LEN = 200
COMMENT_MAX_LEN = 1000
RATING_MIN = 1
RATING_MAX = 5


@dataclass(frozen=True)
class FieldIssue:
    """A single field-level validation issue, mirroring the contract shape."""

    field: str
    issue: str

    def to_dict(self) -> Dict[str, str]:
        return {"field": self.field, "issue": self.issue}


@dataclass
class ValidatedFeedback:
    """Normalized, validated submission ready for persistence."""

    workshop_id: str
    rating: int
    comment: Optional[str] = None


@dataclass
class ValidationResult:
    """Outcome of validating a submission body."""

    value: Optional[ValidatedFeedback] = None
    issues: List[FieldIssue] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.issues and self.value is not None


def _is_strict_int(value: Any) -> bool:
    """True only for genuine integers.

    ``bool`` is a subclass of ``int`` in Python but is not an acceptable
    rating, so it is rejected explicitly. Floats such as ``4.0`` arriving from
    JSON are rejected because the contract requires no fractional part; we treat
    only ``int`` (and integral-typed values) as valid.
    """

    if isinstance(value, bool):
        return False
    return isinstance(value, int)


def validate_feedback(body: Any) -> ValidationResult:
    """Validate a parsed JSON body for ``POST /feedback``.

    ``body`` must already be a parsed object (dict). Returns a
    :class:`ValidationResult`; ``issues`` lists every failing field so the
    client receives a complete picture in one response.
    """

    issues: List[FieldIssue] = []

    # An absent/empty body is treated as an empty object so the response
    # reports each missing required field (api-contract: missing workshopId /
    # rating are VALIDATION_ERROR). A present-but-non-object body is rejected.
    if body is None:
        body = {}
    if not isinstance(body, dict):
        issues.append(
            FieldIssue("body", "Request body must be a JSON object.")
        )
        return ValidationResult(issues=issues)

    # --- workshopId ---
    raw_workshop = body.get("workshopId", None)
    workshop_id: str = ""
    if raw_workshop is None:
        issues.append(FieldIssue("workshopId", "workshopId is required."))
    elif not isinstance(raw_workshop, str):
        issues.append(
            FieldIssue("workshopId", "workshopId must be a string.")
        )
    else:
        workshop_id = raw_workshop.strip()
        if not workshop_id:
            issues.append(
                FieldIssue("workshopId", "workshopId must not be empty.")
            )
        elif len(workshop_id) > WORKSHOP_ID_MAX_LEN:
            issues.append(
                FieldIssue(
                    "workshopId",
                    f"workshopId must be at most {WORKSHOP_ID_MAX_LEN} characters.",
                )
            )

    # --- rating ---
    raw_rating = body.get("rating", None)
    rating: Optional[int] = None
    if raw_rating is None:
        issues.append(FieldIssue("rating", "Rating is required."))
    elif not _is_strict_int(raw_rating):
        issues.append(
            FieldIssue(
                "rating", "Rating must be an integer between 1 and 5."
            )
        )
    elif not (RATING_MIN <= raw_rating <= RATING_MAX):
        issues.append(
            FieldIssue(
                "rating", "Rating must be an integer between 1 and 5."
            )
        )
    else:
        rating = int(raw_rating)

    # --- comment (optional) ---
    raw_comment = body.get("comment", None)
    comment: Optional[str] = None
    if raw_comment is not None:
        if not isinstance(raw_comment, str):
            issues.append(FieldIssue("comment", "comment must be a string."))
        else:
            trimmed = raw_comment
            if len(trimmed) > COMMENT_MAX_LEN:
                issues.append(
                    FieldIssue(
                        "comment",
                        f"comment must be at most {COMMENT_MAX_LEN} characters.",
                    )
                )
            # Empty string means "no comment": leave comment as None.
            elif trimmed != "":
                comment = trimmed

    if issues:
        return ValidationResult(issues=issues)

    assert rating is not None  # guaranteed when no issues
    return ValidationResult(
        value=ValidatedFeedback(
            workshop_id=workshop_id,
            rating=rating,
            comment=comment,
        )
    )
