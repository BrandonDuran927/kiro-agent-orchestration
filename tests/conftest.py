"""Shared pytest fixtures for backend tests.

Provides an in-memory fake repository and config/time fixtures so tests are
fast, deterministic, isolated, and never require AWS credentials, boto3, or a
network (per the backend testing standard).

``conftest.py`` is auto-loaded by pytest, so its fixtures are available to all
test modules without import. It also ensures both the project root (for the
``backend`` package) and this ``tests`` directory (for ``backend_test_helpers``)
are importable.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List

import pytest

_TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_TESTS_DIR)
for _p in (_ROOT, _TESTS_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from backend.config import Config  # noqa: E402


class FakeRepository:
    """In-memory FeedbackRepository test double."""

    def __init__(self) -> None:
        self.items: List[Dict[str, Any]] = []
        self.raise_on_put = False
        self.raise_on_scan = False

    def put(self, item: Dict[str, Any]) -> None:
        if self.raise_on_put:
            raise RuntimeError("simulated put failure")
        self.items.append(dict(item))

    def scan_all(self) -> List[Dict[str, Any]]:
        if self.raise_on_scan:
            raise RuntimeError("simulated scan failure")
        return [dict(i) for i in self.items]


@pytest.fixture
def repo() -> FakeRepository:
    return FakeRepository()


@pytest.fixture
def config() -> Config:
    return Config(table_name="TestFeedback", organizer_key="s3cr3t-organizer-key")


@pytest.fixture
def fixed_now():
    def _now() -> datetime:
        return datetime(2026, 9, 5, 8, 34, 33, tzinfo=timezone.utc)

    return _now
