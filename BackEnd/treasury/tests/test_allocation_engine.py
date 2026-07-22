"""Unit + integration tests for the 5-step waterfall priority engine."""

from decimal import Decimal

from treasury.schemas.llc_schemas import LLCConfigurationCreate
from treasury.schemas.property_schemas import PropertyStatusCreate, PropertyStatusUpdate
from treasury.services import allocation_engine, llc_service, property_service, settlement_service
from treasury.services.allocation_engine import WaterfallInput


def test_step0_retains_pi_shortfall_in_checking_before_any_allocation():
    result = allocation_engine.run_waterfall(
        WaterfallInput(
            rent_received=Decimal("1000.00"),
            pi_amount=Decimal("800.00"),
            checking_balance=Decimal("200.00"),  # shortfall = 600
            target_tax_allocation=Decimal("100.00"),
            target_reserve_allocation=Decimal("100.00"),
        )
    )
    assert result.pi_shortfall == Decimal("600.00")
    assert result.pi_retained_in_checking == Decimal("600.00")
    # Remaining after Step 0: 400 → tax 100 + reserve 100 + cash flow 200
    assert result.tax_balance_delta == Decimal("100.00")
    assert result.reserve_filled == Decimal("100.00")
    assert result.clean_cash_flow == Decimal("200.00")


def test_step1_clears_reserve_debt_and_queues_settlement():
    result = allocation_engine.run_waterfall(
        WaterfallInput(
            rent_received=Decimal("500.00"),
            reserve_debt=Decimal("300.00"),
            reserve_bucket_balance=Decimal("0"),
            target_tax_allocation=Decimal("0"),
            target_reserve_allocation=Decimal("0"),
        )
    )
    assert result.reserve_debt_cleared == Decimal("300.00")
    assert result.new_reserve_debt == Decimal("0.00")
    assert result.reserve_balance_delta == Decimal("300.00")
    assert result.reserve_to_settle_delta == Decimal("300.00")
    assert result.clean_cash_flow == Decimal("200.00")


def test_full_recovery_rent_waterfall_order_steps_0_through_4():
    """Rent recovery after a miss: P&I first, then debt, tax, reserve, cash flow."""
    result = allocation_engine.run_waterfall(
        WaterfallInput(
            rent_received=Decimal("2000.00"),
            pi_amount=Decimal("900.00"),
            checking_balance=Decimal("100.00"),  # shortfall 800
            reserve_debt=Decimal("900.00"),
            reserve_bucket_balance=Decimal("-900.00"),
            reserve_bucket_cap=Decimal("5000.00"),
            target_tax_allocation=Decimal("200.00"),
            target_reserve_allocation=Decimal("150.00"),
        )
    )
    assert [s.step for s in result.steps] == [0, 1, 2, 3, 4]
    assert result.pi_retained_in_checking == Decimal("800.00")
    assert result.reserve_debt_cleared == Decimal("900.00")
    assert result.new_reserve_debt == Decimal("0.00")
    assert result.tax_balance_delta == Decimal("200.00")
    assert result.tax_to_settle_delta == Decimal("200.00")
    # available after 0: 1200; after 1: 300; after 2: 100 → reserve fills $100 of $150 need
    assert result.reserve_filled == Decimal("100.00")
    assert result.clean_cash_flow == Decimal("0.00")


def test_partial_cap_fill_deposits_to_cap_and_pauses_only_surplus():
    """Reserve needs $150, but only $50 room under the cap → deposit $50, pause $100."""
    result = allocation_engine.run_waterfall(
        WaterfallInput(
            rent_received=Decimal("1000.00"),
            reserve_bucket_balance=Decimal("950.00"),
            reserve_bucket_cap=Decimal("1000.00"),  # $50 room
            target_tax_allocation=Decimal("0"),
            target_reserve_allocation=Decimal("150.00"),
        )
    )
    assert result.reserve_filled == Decimal("50.00")
    assert result.pending_overflow == Decimal("100.00")
    # Paused overflow is frozen (not passed to clean cash flow).
    assert result.clean_cash_flow == Decimal("850.00")  # 1000 - 50 - 100


def test_chase_reserves_adds_uncollected_past_targets():
    result = allocation_engine.run_waterfall(
        WaterfallInput(
            rent_received=Decimal("500.00"),
            target_tax_allocation=Decimal("0"),
            target_reserve_allocation=Decimal("100.00"),
            chase_reserves=True,
            uncollected_reserve_targets=Decimal("200.00"),
            reserve_bucket_cap=Decimal("0"),  # uncapped
        )
    )
    # Need = 100 + 200 = 300
    assert result.reserve_filled == Decimal("300.00")
    assert result.clean_cash_flow == Decimal("200.00")


def test_apply_waterfall_persists_bucket_and_settlement_mutations(db_session):
    llc = llc_service.create_llc(db_session, LLCConfigurationCreate(llc_name="WF LLC"))
    prop = property_service.create_property(
        db_session,
        PropertyStatusCreate(
            property_name="wf-prop",
            llc_id=llc.llc_id,
            base_rent_target=Decimal("1500.00"),
            precentage_of_rent_to_reserve=Decimal("10.00"),
            target_tax_allocation=Decimal("200.00"),
            reserve_debt=Decimal("300.00"),
            reserve_bucket_balance=Decimal("0"),
        ),
    )

    result = settlement_service.apply_waterfall_to_property(
        db_session,
        prop.property_id,
        Decimal("1000.00"),
        checking_balance=Decimal("500.00"),
        pi_amount=Decimal("400.00"),  # shortfall = 0 (checking covers it)
    )
    assert result.pi_retained_in_checking == Decimal("0.00")
    assert result.reserve_debt_cleared == Decimal("300.00")
    assert result.tax_balance_delta == Decimal("200.00")
    assert result.reserve_filled == Decimal("150.00")

    refetched = property_service.get_property(db_session, prop.property_id)
    assert refetched.reserve_debt == Decimal("0.00")
    assert refetched.tax_bucket_balance == Decimal("200.00")
    assert refetched.tax_to_settle == Decimal("200.00")
    # debt restore 300 + reserve fill 150
    assert refetched.reserve_bucket_balance == Decimal("450.00")
    assert refetched.reserve_to_settle == Decimal("450.00")


def test_overflow_decision_break_cap_and_cross_allocate(db_session):
    llc = llc_service.create_llc(db_session, LLCConfigurationCreate(llc_name="Cap LLC"))
    source = property_service.create_property(
        db_session,
        PropertyStatusCreate(
            property_name="source",
            llc_id=llc.llc_id,
            reserve_bucket_balance=Decimal("1000.00"),
            reserve_bucket_cap=Decimal("1000.00"),
        ),
    )
    sibling = property_service.create_property(
        db_session,
        PropertyStatusCreate(property_name="sibling", llc_id=llc.llc_id),
    )

    spill = settlement_service.resolve_overflow_decision(
        db_session, source.property_id, Decimal("100.00"), "A"
    )
    assert spill["choice"] == "A"

    cross = settlement_service.resolve_overflow_decision(
        db_session,
        source.property_id,
        Decimal("75.00"),
        "B",
        target_property_id=sibling.property_id,
    )
    assert cross["applied_to"] == sibling.property_id
    sibling = property_service.get_property(db_session, sibling.property_id)
    assert sibling.reserve_bucket_balance == Decimal("75.00")

    brk = settlement_service.resolve_overflow_decision(
        db_session, source.property_id, Decimal("50.00"), "C"
    )
    assert brk["choice"] == "C"
    source = property_service.get_property(db_session, source.property_id)
    assert source.reserve_bucket_balance == Decimal("1050.00")  # broke the cap


def test_percentage_edit_updates_derived_target_used_by_waterfall(db_session):
    llc = llc_service.create_llc(db_session, LLCConfigurationCreate(llc_name="Pct LLC"))
    prop = property_service.create_property(
        db_session,
        PropertyStatusCreate(
            property_name="pct-prop",
            llc_id=llc.llc_id,
            base_rent_target=Decimal("2000.00"),
            precentage_of_rent_to_reserve=Decimal("5.00"),
        ),
    )
    assert prop.target_reserve_allocation == Decimal("100.00")

    property_service.update_property(
        db_session,
        prop.property_id,
        PropertyStatusUpdate(precentage_of_rent_to_reserve=Decimal("12.50")),
    )
    prop = property_service.get_property(db_session, prop.property_id)
    assert prop.target_reserve_allocation == Decimal("250.00")

    result = settlement_service.apply_waterfall_to_property(
        db_session, prop.property_id, Decimal("2000.00")
    )
    assert result.reserve_filled == Decimal("250.00")
