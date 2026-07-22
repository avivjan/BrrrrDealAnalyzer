"""Unit-level tests for `transaction_routing_service`: real-time bucket
mutation, manual HITL reassignment, and multi-LLC veil protection.
"""

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from treasury.schemas.llc_schemas import LLCConfigurationCreate
from treasury.schemas.property_schemas import PropertyStatusCreate
from treasury.schemas.transaction_schemas import (
    TransactionLedgerCreate,
    TransactionLedgerUpdate,
)
from treasury.services import llc_service, property_service, transaction_routing_service
from treasury.services.exceptions import ValidationError


def _make_llc(db_session, name="Routing LLC"):
    return llc_service.create_llc(db_session, LLCConfigurationCreate(llc_name=name))


def _make_property(db_session, llc_id, name="prop", **overrides):
    return property_service.create_property(
        db_session,
        PropertyStatusCreate(property_name=name, llc_id=llc_id, **overrides),
    )


def _txn_payload(property_id, amount, sub_bucket, transaction_type="Rent", **overrides):
    defaults = dict(
        property_id=property_id,
        amount=Decimal(amount),
        description="test entry",
        timestamp=datetime(2026, 7, 5, tzinfo=timezone.utc),
        is_real_bank_tx=False,
        sub_bucket_assignment=sub_bucket,
        transaction_type=transaction_type,
    )
    defaults.update(overrides)
    return TransactionLedgerCreate(**defaults)


# --- Real-time bucket mutation -------------------------------------------------


def test_ingestion_immediately_mutates_tax_bucket_and_settlement_queue(db_session):
    llc = _make_llc(db_session)
    prop = _make_property(db_session, llc.llc_id)

    transaction_routing_service.create_transaction_with_effects(
        db_session, _txn_payload(prop.property_id, "300.00", "Tax")
    )

    refetched = property_service.get_property(db_session, prop.property_id)
    assert refetched.tax_bucket_balance == Decimal("300.00")
    assert refetched.tax_to_settle == Decimal("300.00")


def test_ingestion_immediately_mutates_reserve_bucket_and_settlement_queue(db_session):
    llc = _make_llc(db_session)
    prop = _make_property(db_session, llc.llc_id)

    transaction_routing_service.create_transaction_with_effects(
        db_session, _txn_payload(prop.property_id, "150.00", "General Reserve")
    )

    refetched = property_service.get_property(db_session, prop.property_id)
    assert refetched.reserve_bucket_balance == Decimal("150.00")
    assert refetched.reserve_to_settle == Decimal("150.00")


def test_continuous_ingestion_accumulates_settlement_queue_in_real_time(db_session):
    """Multiple ingested transactions must keep compounding the settlement
    queue live — no batching, no monthly lookback step required."""
    llc = _make_llc(db_session)
    prop = _make_property(db_session, llc.llc_id)

    transaction_routing_service.create_transaction_with_effects(
        db_session, _txn_payload(prop.property_id, "100.00", "Tax")
    )
    after_first = property_service.get_property(db_session, prop.property_id)
    assert after_first.tax_to_settle == Decimal("100.00")

    transaction_routing_service.create_transaction_with_effects(
        db_session, _txn_payload(prop.property_id, "50.00", "Tax")
    )
    after_second = property_service.get_property(db_session, prop.property_id)
    assert after_second.tax_to_settle == Decimal("150.00")
    assert after_second.tax_bucket_balance == Decimal("150.00")


def test_unassigned_sub_bucket_never_mutates_any_property_balance(db_session):
    llc = _make_llc(db_session)
    prop = _make_property(db_session, llc.llc_id)

    transaction_routing_service.create_transaction_with_effects(
        db_session,
        _txn_payload(
            prop.property_id, "900.00", None, transaction_type="Rent", is_real_bank_tx=True
        ),
    )

    refetched = property_service.get_property(db_session, prop.property_id)
    assert refetched.tax_bucket_balance == Decimal("0")
    assert refetched.reserve_bucket_balance == Decimal("0")


# --- Manual reassignment (HITL) ------------------------------------------------


def test_manual_reassignment_moves_bucket_effect_from_property_a_to_property_b(db_session):
    llc = _make_llc(db_session)
    prop_a = _make_property(db_session, llc.llc_id, name="Property A")
    prop_b = _make_property(db_session, llc.llc_id, name="Property B")

    txn = transaction_routing_service.create_transaction_with_effects(
        db_session, _txn_payload(prop_a.property_id, "500.00", "Tax")
    )

    a_after_create = property_service.get_property(db_session, prop_a.property_id)
    assert a_after_create.tax_bucket_balance == Decimal("500.00")
    assert a_after_create.tax_to_settle == Decimal("500.00")

    updated = transaction_routing_service.apply_manual_override(
        db_session,
        txn.transaction_id,
        TransactionLedgerUpdate(property_id=prop_b.property_id),
    )
    assert updated.property_id == prop_b.property_id

    a_after_move = property_service.get_property(db_session, prop_a.property_id)
    b_after_move = property_service.get_property(db_session, prop_b.property_id)
    assert a_after_move.tax_bucket_balance == Decimal("0")
    assert a_after_move.tax_to_settle == Decimal("0")
    assert b_after_move.tax_bucket_balance == Decimal("500.00")
    assert b_after_move.tax_to_settle == Decimal("500.00")


def test_manual_override_changing_sub_bucket_moves_amount_between_buckets(db_session):
    llc = _make_llc(db_session)
    prop = _make_property(db_session, llc.llc_id)

    txn = transaction_routing_service.create_transaction_with_effects(
        db_session, _txn_payload(prop.property_id, "220.00", "Tax")
    )

    transaction_routing_service.apply_manual_override(
        db_session,
        txn.transaction_id,
        TransactionLedgerUpdate(sub_bucket_assignment="General Reserve"),
    )

    refetched = property_service.get_property(db_session, prop.property_id)
    assert refetched.tax_bucket_balance == Decimal("0")
    assert refetched.tax_to_settle == Decimal("0")
    assert refetched.reserve_bucket_balance == Decimal("220.00")
    assert refetched.reserve_to_settle == Decimal("220.00")


def test_manual_override_changing_amount_recalculates_bucket_delta(db_session):
    llc = _make_llc(db_session)
    prop = _make_property(db_session, llc.llc_id)

    txn = transaction_routing_service.create_transaction_with_effects(
        db_session, _txn_payload(prop.property_id, "100.00", "Tax")
    )

    transaction_routing_service.apply_manual_override(
        db_session,
        txn.transaction_id,
        TransactionLedgerUpdate(amount=Decimal("40.00")),
    )

    refetched = property_service.get_property(db_session, prop.property_id)
    assert refetched.tax_bucket_balance == Decimal("40.00")
    assert refetched.tax_to_settle == Decimal("40.00")


def test_deleting_transaction_unwinds_its_bucket_effect(db_session):
    llc = _make_llc(db_session)
    prop = _make_property(db_session, llc.llc_id)

    txn = transaction_routing_service.create_transaction_with_effects(
        db_session, _txn_payload(prop.property_id, "75.00", "General Reserve")
    )

    transaction_routing_service.delete_transaction_with_effects(db_session, txn.transaction_id)

    refetched = property_service.get_property(db_session, prop.property_id)
    assert refetched.reserve_bucket_balance == Decimal("0")
    assert refetched.reserve_to_settle == Decimal("0")


# --- Multi-LLC veil protection --------------------------------------------------


def test_reassignment_within_same_llc_is_allowed(db_session):
    llc = _make_llc(db_session)
    prop_a = _make_property(db_session, llc.llc_id, name="A")
    prop_b = _make_property(db_session, llc.llc_id, name="B")

    txn = transaction_routing_service.create_transaction_with_effects(
        db_session, _txn_payload(prop_a.property_id, "60.00", "Tax")
    )

    updated = transaction_routing_service.apply_manual_override(
        db_session,
        txn.transaction_id,
        TransactionLedgerUpdate(property_id=prop_b.property_id),
    )
    assert updated.property_id == prop_b.property_id


def test_reassignment_across_llcs_is_blocked_by_veil_protection(db_session):
    llc_1 = _make_llc(db_session, "LLC One")
    llc_2 = _make_llc(db_session, "LLC Two")
    prop_a = _make_property(db_session, llc_1.llc_id, name="A")
    prop_c = _make_property(db_session, llc_2.llc_id, name="C")

    txn = transaction_routing_service.create_transaction_with_effects(
        db_session, _txn_payload(prop_a.property_id, "60.00", "Tax")
    )

    with pytest.raises(ValidationError):
        transaction_routing_service.apply_manual_override(
            db_session,
            txn.transaction_id,
            TransactionLedgerUpdate(property_id=prop_c.property_id),
        )

    # Original property must remain untouched after the rejected reassignment.
    a_after = property_service.get_property(db_session, prop_a.property_id)
    assert a_after.tax_bucket_balance == Decimal("60.00")
