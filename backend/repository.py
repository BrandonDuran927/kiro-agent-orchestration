"""Persistence access for feedback records (DynamoDB).

Implements the two approved access patterns from docs/data-model.md:

- AP-1: ``PutItem`` one write-once record keyed by generated ``feedbackId``.
- AP-2: ``Scan`` to list all records for organizer review.

Required IAM actions (implemented by DevOps, documented here, NFR-006):
``dynamodb:PutItem`` and ``dynamodb:Scan`` on the Feedback table ARN.
(GetItem is reserved/unused for the POC — AP-3.)

``boto3`` is imported lazily so unit tests can substitute an in-memory
repository without the dependency or any AWS credentials/network.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Protocol


class FeedbackRepository(Protocol):
    """Persistence port used by the handler; enables test doubles."""

    def put(self, item: Dict[str, Any]) -> None:
        """Persist one feedback item (write-once)."""

    def scan_all(self) -> List[Dict[str, Any]]:
        """Return all feedback items."""


class DynamoDBFeedbackRepository:
    """DynamoDB-backed repository using boto3 resource API.

    The boto3 client is created lazily and cached, following the safe
    SDK-reuse pattern for Lambda warm starts.
    """

    def __init__(self, table_name: str, table: Optional[Any] = None) -> None:
        if not table_name and table is None:
            raise ValueError("table_name is required")
        self._table_name = table_name
        self._table = table

    def _get_table(self) -> Any:
        if self._table is None:
            import boto3  # lazy import: provided by the Lambda runtime

            self._table = boto3.resource("dynamodb").Table(self._table_name)
        return self._table

    def put(self, item: Dict[str, Any]) -> None:
        self._get_table().put_item(Item=item)

    def scan_all(self) -> List[Dict[str, Any]]:
        """Scan the whole table, following pagination via LastEvaluatedKey.

        ADR-4 (architecture): Scan is acceptable at workshop scale. Paginating
        keeps correctness if the dataset exceeds a single 1 MB page.
        """

        table = self._get_table()
        items: List[Dict[str, Any]] = []
        response = table.scan()
        items.extend(response.get("Items", []))
        while "LastEvaluatedKey" in response:
            response = table.scan(
                ExclusiveStartKey=response["LastEvaluatedKey"]
            )
            items.extend(response.get("Items", []))
        return items


def build_default_repository(table_name: str) -> FeedbackRepository:
    """Factory for the production DynamoDB repository."""

    return DynamoDBFeedbackRepository(table_name=table_name)
