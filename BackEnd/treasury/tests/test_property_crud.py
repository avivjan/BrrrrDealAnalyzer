from decimal import Decimal

import pytest

from treasury.schemas.llc_schemas import LLCConfigurationCreate
from treasury.schemas.property_schemas import PropertyStatusCreate, PropertyStatusUpdate
from treasury.services import llc_service, property_service
from treasury.services.exceptions import NotFoundError, ValidationError


def _make_llc(db_session, name="Test LLC"):
    return llc_service.create_llc(db_session, LLCConfigurationCreate(llc_name=name))


def test_create_and_get_property(db_session):
    llc = _make_llc(db_session)
    prop = property_service.create_property(
        db_session,
        PropertyStatusCreate(property_name="123 Main St", llc_id=llc.llc_id),
    )
    fetched = property_service.get_property(db_session, prop.property_id)
    assert len(fetched.property_id) == 32  # uuid4.hex
    assert fetched.property_name == "123 Main St"
    assert fetched.llc_id == llc.llc_id


def test_create_property_rejects_unknown_llc(db_session):
    with pytest.raises(ValidationError):
        property_service.create_property(
            db_session,
            PropertyStatusCreate(property_name="ghost", llc_id="ghost-llc"),
        )


def test_list_properties_filtered_by_llc(db_session):
    llc_a = _make_llc(db_session, "LLC A")
    llc_b = _make_llc(db_session, "LLC B")
    property_service.create_property(
        db_session, PropertyStatusCreate(property_name="a1", llc_id=llc_a.llc_id)
    )
    property_service.create_property(
        db_session, PropertyStatusCreate(property_name="b1", llc_id=llc_b.llc_id)
    )
    a_props = property_service.list_properties(db_session, llc_id=llc_a.llc_id)
    assert len(a_props) == 1
    assert a_props[0].property_name == "a1"


def test_update_property_overrides_any_field(db_session):
    llc = _make_llc(db_session)
    prop = property_service.create_property(
        db_session,
        PropertyStatusCreate(property_name="p1", llc_id=llc.llc_id),
    )
    updated = property_service.update_property(
        db_session,
        prop.property_id,
        PropertyStatusUpdate(reserve_debt=Decimal("42.42"), chase_reserves=True),
    )
    assert updated.reserve_debt == Decimal("42.42")
    assert updated.chase_reserves is True


def test_update_property_can_reparent_to_another_llc(db_session):
    llc_a = _make_llc(db_session, "LLC A")
    llc_b = _make_llc(db_session, "LLC B")
    prop = property_service.create_property(
        db_session,
        PropertyStatusCreate(property_name="p1", llc_id=llc_a.llc_id),
    )
    updated = property_service.update_property(
        db_session,
        prop.property_id,
        PropertyStatusUpdate(llc_id=llc_b.llc_id),
    )
    assert updated.llc_id == llc_b.llc_id


def test_update_property_reparent_rejects_unknown_llc(db_session):
    llc = _make_llc(db_session)
    prop = property_service.create_property(
        db_session,
        PropertyStatusCreate(property_name="p1", llc_id=llc.llc_id),
    )
    with pytest.raises(ValidationError):
        property_service.update_property(
            db_session,
            prop.property_id,
            PropertyStatusUpdate(llc_id="ghost-llc"),
        )


def test_delete_property_removes_row(db_session):
    llc = _make_llc(db_session)
    prop = property_service.create_property(
        db_session,
        PropertyStatusCreate(property_name="p1", llc_id=llc.llc_id),
    )
    property_service.delete_property(db_session, prop.property_id)
    with pytest.raises(NotFoundError):
        property_service.get_property(db_session, prop.property_id)


def test_get_missing_property_raises_not_found(db_session):
    with pytest.raises(NotFoundError):
        property_service.get_property(db_session, "does-not-exist")


def test_create_property_stores_target_metrics(db_session):
    llc = _make_llc(db_session)
    prop = property_service.create_property(
        db_session,
        PropertyStatusCreate(
            property_name="Target Test",
            llc_id=llc.llc_id,
            base_rent_target=Decimal("350.00"),
            target_tax_allocation=Decimal("125.50"),
            precentage_of_rent_to_reserve=Decimal("10.00"),
        ),
    )
    fetched = property_service.get_property(db_session, prop.property_id)
    assert fetched.base_rent_target == Decimal("350.00")
    assert fetched.target_tax_allocation == Decimal("125.50")
    assert fetched.precentage_of_rent_to_reserve == Decimal("10.00")
    # Derived: 350 * 10% = 35.00
    assert fetched.target_reserve_allocation == Decimal("35.00")


def test_partial_update_overrides_target_tax_allocation_only(db_session):
    llc = _make_llc(db_session)
    prop = property_service.create_property(
        db_session,
        PropertyStatusCreate(
            property_name="p1",
            llc_id=llc.llc_id,
            base_rent_target=Decimal("2000.00"),
            target_tax_allocation=Decimal("100.00"),
            precentage_of_rent_to_reserve=Decimal("20.00"),
        ),
    )
    updated = property_service.update_property(
        db_session,
        prop.property_id,
        PropertyStatusUpdate(target_tax_allocation=Decimal("175.25")),
    )
    assert updated.target_tax_allocation == Decimal("175.25")
    # Percentage untouched → derived dollar target stays 2000 * 20% = 400
    assert updated.precentage_of_rent_to_reserve == Decimal("20.00")
    assert updated.target_reserve_allocation == Decimal("400.00")


def test_editing_percentage_updates_derived_dollar_target(db_session):
    llc = _make_llc(db_session)
    prop = property_service.create_property(
        db_session,
        PropertyStatusCreate(
            property_name="pct-prop",
            llc_id=llc.llc_id,
            base_rent_target=Decimal("1500.00"),
            precentage_of_rent_to_reserve=Decimal("0"),
        ),
    )
    assert prop.target_reserve_allocation == Decimal("0.00")

    updated = property_service.update_property(
        db_session,
        prop.property_id,
        PropertyStatusUpdate(precentage_of_rent_to_reserve=Decimal("10.00")),
    )
    assert updated.precentage_of_rent_to_reserve == Decimal("10.00")
    assert updated.target_reserve_allocation == Decimal("150.00")

    # Changing rent recalculates the dollar target without touching the %.
    updated = property_service.update_property(
        db_session,
        prop.property_id,
        PropertyStatusUpdate(base_rent_target=Decimal("2000.00")),
    )
    assert updated.precentage_of_rent_to_reserve == Decimal("10.00")
    assert updated.target_reserve_allocation == Decimal("200.00")
