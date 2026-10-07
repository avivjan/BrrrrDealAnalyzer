"""SHA-256 hash chains over the Member Loan tables.

Each row's hash covers every column except the hash itself (so it includes the
previous row's hash). Values are normalised so a row read back from Postgres
hashes exactly as it did when it was written: money as two-decimal text,
datetimes in UTC ISO format, dates ISO, UUIDs as text, JSON sorted.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Iterable

GENESIS_HASH = "0" * 64


def _hash_ready(value: Any) -> Any:
    if isinstance(value, Decimal):
        return f"{value:.2f}"
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, dict):
        return {str(k): _hash_ready(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_hash_ready(v) for v in value]
    return value


def canonical_json(data: Any) -> str:
    return json.dumps(_hash_ready(data), sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def compute_row_hash(row: Any, hash_column_name: str) -> str:
    content = {
        column.name: getattr(row, column.key)
        for column in row.__table__.columns
        if column.name != hash_column_name
    }
    return hashlib.sha256(canonical_json(content).encode("utf-8")).hexdigest()


def verify_hash_chain(
    rows_in_sequence_order: Iterable[Any], *, hash_column_name: str, previous_hash_column_name: str, table_label: str
) -> list[str]:
    """Plain-language problems found in one chain; an empty list means it is intact."""

    problems: list[str] = []
    expected_previous_hash = GENESIS_HASH
    for position, row in enumerate(rows_in_sequence_order, start=1):
        if getattr(row, previous_hash_column_name) != expected_previous_hash:
            problems.append(f"{table_label} row {position} does not link to the row before it.")
        if compute_row_hash(row, hash_column_name) != getattr(row, hash_column_name):
            problems.append(f"{table_label} row {position} was changed after it was written.")
        expected_previous_hash = getattr(row, hash_column_name)
    return problems
