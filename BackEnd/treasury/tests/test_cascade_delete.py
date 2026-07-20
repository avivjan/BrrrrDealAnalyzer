from decimal import Decimal

import pytest

from treasury.repositories import cash_flow_repository, property_repository
from treasury.schemas.cash_flow_schemas import PropertyCashFlowHistoryCreate
from treasury.schemas.llc_schemas import LLCConfigurationCreate
from treasury.schemas.property_schemas import PropertyStatusCreate
from treasury.services import cash_flow_service, llc_service, property_service


def _seed_llc_with_property_and_history(db_session, llc_name="Seed LLC"):
    llc = llc_service.create_llc(db_session, LLCConfigurationCreate(llc_name=llc_name))
    prop = property_service.create_property(
        db_session,
        PropertyStatusCreate(property_id=f"{llc.llc_id}-prop", llc_id=llc.llc_id),
    )
    snapshot = cash_flow_service.create_snapshot(
        db_session,
        PropertyCashFlowHistoryCreate(
            property_id=prop.property_id,
            month_year="2026-06",
            monthly_cash_flow=Decimal("500.00"),
        ),
    )
    return llc, prop, snapshot


def test_deleting_llc_cascades_to_property_and_history(db_session):
    llc, prop, snapshot = _seed_llc_with_property_and_history(db_session)
    llc_service.delete_llc(db_session, llc.llc_id)
    with pytest.raises(Exception):
        property_service.get_property(db_session, prop.property_id)
    with pytest.raises(Exception):
        cash_flow_service.get_snapshot(db_session, snapshot.history_id)
    assert property_repository.list_all(db_session) == []
    assert cash_flow_repository.list_all(db_session) == []


def test_deleting_llc_with_multiple_properties_removes_every_descendant(db_session):
    llc = llc_service.create_llc(
        db_session, LLCConfigurationCreate(llc_name="Multi-Property LLC")
    )
    props = [
        property_service.create_property(
            db_session,
            PropertyStatusCreate(property_id=f"p{i}", llc_id=llc.llc_id),
        )
        for i in range(3)
    ]
    for prop in props:
        cash_flow_service.create_snapshot(
            db_session,
            PropertyCashFlowHistoryCreate(property_id=prop.property_id, month_year="2026-01"),
        )
    assert len(property_repository.list_all(db_session, llc_id=llc.llc_id)) == 3
    assert len(cash_flow_repository.list_all(db_session)) == 3
    llc_service.delete_llc(db_session, llc.llc_id)
    assert property_repository.list_all(db_session) == []
    assert cash_flow_repository.list_all(db_session) == []


def test_deleting_llc_does_not_touch_unrelated_llcs(db_session):
    llc_a, prop_a, snapshot_a = _seed_llc_with_property_and_history(db_session, "LLC A")
    llc_b, prop_b, snapshot_b = _seed_llc_with_property_and_history(db_session, "LLC B")
    llc_service.delete_llc(db_session, llc_a.llc_id)
    fetched_llc_b = llc_service.get_llc(db_session, llc_b.llc_id)
    fetched_prop_b = property_service.get_property(db_session, prop_b.property_id)
    fetched_snapshot_b = cash_flow_service.get_snapshot(db_session, snapshot_b.history_id)
    assert fetched_llc_b.llc_id == llc_b.llc_id
    assert fetched_prop_b.property_id == prop_b.property_id
    assert fetched_snapshot_b.history_id == snapshot_b.history_id


def test_deleting_property_cascades_to_history_but_protects_parent_llc(db_session):
    llc, prop, snapshot = _seed_llc_with_property_and_history(db_session)
    property_service.delete_property(db_session, prop.property_id)
    with pytest.raises(Exception):
        cash_flow_service.get_snapshot(db_session, snapshot.history_id)
    fetched_llc = llc_service.get_llc(db_session, llc.llc_id)
    assert fetched_llc.llc_id == llc.llc_id
