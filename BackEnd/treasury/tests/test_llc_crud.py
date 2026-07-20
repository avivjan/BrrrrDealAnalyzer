from decimal import Decimal

import pytest

from treasury.schemas.llc_schemas import LLCConfigurationCreate, LLCConfigurationUpdate
from treasury.services import llc_service
from treasury.services.exceptions import NotFoundError


def test_create_and_get_llc(db_session):
    llc = llc_service.create_llc(
        db_session,
        LLCConfigurationCreate(llc_name="Big Whales AY LLC", checking_redline_buffer=Decimal("2500.00")),
    )
    fetched = llc_service.get_llc(db_session, llc.llc_id)
    assert fetched.llc_name == "Big Whales AY LLC"
    assert fetched.checking_redline_buffer == Decimal("2500.00")


def test_create_llc_with_user_supplied_id(db_session):
    llc = llc_service.create_llc(
        db_session,
        LLCConfigurationCreate(llc_id="custom-llc-1", llc_name="Custom LLC"),
    )
    assert llc.llc_id == "custom-llc-1"


def test_list_llcs_returns_all_rows(db_session):
    llc_service.create_llc(db_session, LLCConfigurationCreate(llc_name="Alpha LLC"))
    llc_service.create_llc(db_session, LLCConfigurationCreate(llc_name="Beta LLC"))
    names = {row.llc_name for row in llc_service.list_llcs(db_session)}
    assert names == {"Alpha LLC", "Beta LLC"}


def test_update_llc_partial_fields(db_session):
    llc = llc_service.create_llc(
        db_session,
        LLCConfigurationCreate(llc_name="Gamma LLC", checking_redline_buffer=Decimal("1000")),
    )
    updated = llc_service.update_llc(
        db_session,
        llc.llc_id,
        LLCConfigurationUpdate(checking_redline_buffer=Decimal("9999.99")),
    )
    assert updated.checking_redline_buffer == Decimal("9999.99")
    assert updated.llc_name == "Gamma LLC"


def test_delete_llc_removes_row(db_session):
    llc = llc_service.create_llc(db_session, LLCConfigurationCreate(llc_name="Delta LLC"))
    llc_service.delete_llc(db_session, llc.llc_id)
    with pytest.raises(NotFoundError):
        llc_service.get_llc(db_session, llc.llc_id)


def test_get_missing_llc_raises_not_found(db_session):
    with pytest.raises(NotFoundError):
        llc_service.get_llc(db_session, "does-not-exist")


def test_update_missing_llc_raises_not_found(db_session):
    with pytest.raises(NotFoundError):
        llc_service.update_llc(db_session, "does-not-exist", LLCConfigurationUpdate(llc_name="X"))


def test_delete_missing_llc_raises_not_found(db_session):
    with pytest.raises(NotFoundError):
        llc_service.delete_llc(db_session, "does-not-exist")
