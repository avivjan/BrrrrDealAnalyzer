from datetime import datetime, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError as PydanticValidationError

from treasury.schemas.cash_flow_schemas import (
    PropertyCashFlowHistoryCreate,
    PropertyCashFlowHistoryUpdate,
)
from treasury.schemas.llc_schemas import LLCConfigurationCreate
from treasury.schemas.property_schemas import PropertyStatusCreate
from treasury.schemas.transaction_schemas import (
    TransactionLedgerCreate,
    TransactionLedgerUpdate,
)
from treasury.services import (
    cash_flow_service,
    llc_service,
    property_service,
    transaction_service,
)
from treasury.services.exceptions import NotFoundError, ValidationError


def _make_property(db_session):
    llc = llc_service.create_llc(db_session, LLCConfigurationCreate(llc_name="Test LLC"))
    return property_service.create_property(
        db_session,
        PropertyStatusCreate(property_name="prop-1", llc_id=llc.llc_id),
    )


def test_create_and_get_snapshot(db_session):
    prop = _make_property(db_session)
    snapshot = cash_flow_service.create_snapshot(
        db_session,
        PropertyCashFlowHistoryCreate(
            property_id=prop.property_id,
            month_year="2026-06",
            monthly_cash_flow=Decimal("500.00"),
        ),
    )
    fetched = cash_flow_service.get_snapshot(db_session, snapshot.history_id)
    assert fetched.month_year == "2026-06"
    assert fetched.monthly_cash_flow == Decimal("500.00")


def test_create_snapshot_rejects_unknown_property(db_session):
    with pytest.raises(ValidationError):
        cash_flow_service.create_snapshot(
            db_session,
            PropertyCashFlowHistoryCreate(
                property_id="ghost-property",
                month_year="2026-06",
            ),
        )


def test_create_snapshot_rejects_bad_month_year_format(db_session):
    prop = _make_property(db_session)
    with pytest.raises(PydanticValidationError):
        PropertyCashFlowHistoryCreate(
            property_id=prop.property_id,
            month_year="June-2026",
        )


def test_list_snapshots_filtered_by_property_sorted_by_month(db_session):
    prop = _make_property(db_session)
    for month in ("2026-03", "2026-01", "2026-02"):
        cash_flow_service.create_snapshot(
            db_session,
            PropertyCashFlowHistoryCreate(property_id=prop.property_id, month_year=month),
        )
    rows = cash_flow_service.list_snapshots(db_session, property_id=prop.property_id)
    assert [row.month_year for row in rows] == ["2026-01", "2026-02", "2026-03"]


def test_update_snapshot_overrides_stored_values(db_session):
    prop = _make_property(db_session)
    snapshot = cash_flow_service.create_snapshot(
        db_session,
        PropertyCashFlowHistoryCreate(
            property_id=prop.property_id,
            month_year="2026-06",
            monthly_cash_flow=Decimal("500.00"),
        ),
    )
    updated = cash_flow_service.update_snapshot(
        db_session,
        snapshot.history_id,
        PropertyCashFlowHistoryUpdate(cumulative_cash_flow=Decimal("12345.67")),
    )
    assert updated.cumulative_cash_flow == Decimal("12345.67")
    assert updated.monthly_cash_flow == Decimal("500.00")


def test_delete_snapshot_removes_row(db_session):
    prop = _make_property(db_session)
    snapshot = cash_flow_service.create_snapshot(
        db_session,
        PropertyCashFlowHistoryCreate(property_id=prop.property_id, month_year="2026-06"),
    )
    cash_flow_service.delete_snapshot(db_session, snapshot.history_id)
    with pytest.raises(NotFoundError):
        cash_flow_service.get_snapshot(db_session, snapshot.history_id)


def test_get_missing_snapshot_raises_not_found(db_session):
    with pytest.raises(NotFoundError):
        cash_flow_service.get_snapshot(db_session, "does-not-exist")


def test_create_and_get_transaction(db_session):
    prop = _make_property(db_session)
    txn = transaction_service.create_transaction(
        db_session,
        TransactionLedgerCreate(
            property_id=prop.property_id,
            amount=Decimal("1500.00"),
            description="June rent",
            timestamp=datetime(2026, 6, 1, tzinfo=timezone.utc),
            transaction_type="Rent",
            sub_bucket_assignment="Tax",
        ),
    )
    fetched = transaction_service.get_transaction(db_session, txn.transaction_id)
    assert fetched.amount == Decimal("1500.00")
    assert fetched.sub_bucket_assignment == "Tax"


def test_update_transaction_manual_override(db_session):
    prop = _make_property(db_session)
    txn = transaction_service.create_transaction(
        db_session,
        TransactionLedgerCreate(
            property_id=prop.property_id,
            amount=Decimal("100.00"),
            description="Original",
            timestamp=datetime(2026, 6, 1, tzinfo=timezone.utc),
            transaction_type="Repair",
        ),
    )
    updated = transaction_service.update_transaction(
        db_session,
        txn.transaction_id,
        TransactionLedgerUpdate(
            amount=Decimal("-777.77"),
            description="Manual override",
            sub_bucket_assignment="General Reserve",
        ),
    )
    assert updated.amount == Decimal("-777.77")
    assert updated.description == "Manual override"
    assert updated.sub_bucket_assignment == "General Reserve"
