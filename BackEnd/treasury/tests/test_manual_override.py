"""Human-in-the-loop guarantee: every numeric balance, buffer, cap, debt
counter, and boolean control flag must be directly overridable, and the
override must land in the database exactly as supplied — no silent
recomputation or clamping.
"""

from decimal import Decimal

from treasury.schemas.cash_flow_schemas import (
    PropertyCashFlowHistoryCreate,
    PropertyCashFlowHistoryUpdate,
)
from treasury.schemas.llc_schemas import LLCConfigurationCreate, LLCConfigurationUpdate
from treasury.schemas.property_schemas import PropertyStatusCreate, PropertyStatusUpdate
from treasury.services import cash_flow_service, llc_service, property_service


def test_manual_override_of_llc_redline_buffer_persists_exactly(db_session):
    llc = llc_service.create_llc(
        db_session,
        LLCConfigurationCreate(llc_name="Override LLC", checking_redline_buffer=Decimal("100.00")),
    )
    llc_service.update_llc(
        db_session,
        llc.llc_id,
        LLCConfigurationUpdate(checking_redline_buffer=Decimal("0.01")),
    )
    refetched = llc_service.get_llc(db_session, llc.llc_id)
    assert refetched.checking_redline_buffer == Decimal("0.01")


def test_manual_override_of_every_property_field_bypasses_automated_math(db_session):
    llc = llc_service.create_llc(db_session, LLCConfigurationCreate(llc_name="Override LLC"))
    prop = property_service.create_property(
        db_session,
        PropertyStatusCreate(property_name="override-prop", llc_id=llc.llc_id),
    )
    property_service.update_property(
        db_session,
        prop.property_id,
        PropertyStatusUpdate(
            tax_bucket_balance=Decimal("-500.00"),
            tax_to_settle=Decimal("1234.56"),
            reserve_bucket_balance=Decimal("999999.99"),
            reserve_to_settle=Decimal("1.00"),
            reserve_bucket_cap=Decimal("10.00"),
            reserve_debt=Decimal("123456.78"),
            base_rent_target=Decimal("2500.00"),
            target_tax_allocation=Decimal("300.00"),
            precentage_of_rent_to_reserve=Decimal("10.00"),
            chase_reserves=True,
        ),
    )
    refetched = property_service.get_property(db_session, prop.property_id)
    assert refetched.tax_bucket_balance == Decimal("-500.00")
    assert refetched.tax_to_settle == Decimal("1234.56")
    assert refetched.reserve_bucket_balance == Decimal("999999.99")
    assert refetched.reserve_to_settle == Decimal("1.00")
    assert refetched.reserve_bucket_cap == Decimal("10.00")
    assert refetched.reserve_debt == Decimal("123456.78")
    assert refetched.target_tax_allocation == Decimal("300.00")
    assert refetched.precentage_of_rent_to_reserve == Decimal("10.00")
    assert refetched.target_reserve_allocation == Decimal("250.00")  # derived
    assert refetched.chase_reserves is True


def test_manual_override_toggles_chase_reserves_independently(db_session):
    llc = llc_service.create_llc(db_session, LLCConfigurationCreate(llc_name="Flag LLC"))
    prop = property_service.create_property(
        db_session,
        PropertyStatusCreate(property_name="flag-prop", llc_id=llc.llc_id),
    )
    property_service.update_property(
        db_session,
        prop.property_id,
        PropertyStatusUpdate(chase_reserves=True),
    )
    refetched = property_service.get_property(db_session, prop.property_id)
    assert refetched.chase_reserves is True


def test_manual_override_of_cash_flow_history_snapshot(db_session):
    llc = llc_service.create_llc(db_session, LLCConfigurationCreate(llc_name="History LLC"))
    prop = property_service.create_property(
        db_session,
        PropertyStatusCreate(property_name="hist-prop", llc_id=llc.llc_id),
    )
    snapshot = cash_flow_service.create_snapshot(
        db_session,
        PropertyCashFlowHistoryCreate(
            property_id=prop.property_id,
            month_year="2026-06",
            monthly_cash_flow=Decimal("500.00"),
        ),
    )
    cash_flow_service.update_snapshot(
        db_session,
        snapshot.history_id,
        PropertyCashFlowHistoryUpdate(cumulative_cash_flow=Decimal("-999.99")),
    )
    refetched = cash_flow_service.get_snapshot(db_session, snapshot.history_id)
    assert refetched.cumulative_cash_flow == Decimal("-999.99")
