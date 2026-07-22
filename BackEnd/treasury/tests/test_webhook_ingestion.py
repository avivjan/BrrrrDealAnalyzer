"""Integration tests for the webhook ingestion pipeline: category parsing,
real vs. virtual classification, real-time bucket mutation, and rent
payments running through the 5-step waterfall (percentage-based reserve).
"""

from datetime import datetime, timezone
from decimal import Decimal

from treasury.schemas.llc_schemas import LLCConfigurationCreate
from treasury.schemas.property_schemas import PropertyStatusCreate
from treasury.schemas.webhook_schemas import BankWebhookPayload
from treasury.services import (
    llc_service,
    property_service,
    transaction_routing_service,
    webhook_parser_service,
)


def _make_llc(db_session, name="Webhook LLC"):
    return llc_service.create_llc(db_session, LLCConfigurationCreate(llc_name=name))


def _make_property(db_session, llc_id, **overrides):
    return property_service.create_property(
        db_session,
        PropertyStatusCreate(property_name="webhook-prop", llc_id=llc_id, **overrides),
    )


def _webhook(property_id, amount, category, day=5, **overrides):
    defaults = dict(
        property_id=property_id,
        amount=Decimal(amount),
        description=f"{category} payment",
        timestamp=datetime(2026, 7, day, tzinfo=timezone.utc),
        category=category,
    )
    defaults.update(overrides)
    return BankWebhookPayload(**defaults)


# --- Category classification (real vs virtual) ---------------------------------


def test_rent_category_is_classified_as_real_bank_transaction(db_session):
    llc = _make_llc(db_session)
    prop = _make_property(db_session, llc.llc_id)

    parsed = webhook_parser_service.parse_bank_webhook(_webhook(prop.property_id, "1000", "rent"))
    assert parsed.is_real_bank_tx is True
    assert parsed.transaction_type == "Rent"
    assert parsed.sub_bucket_assignment is None


def test_tax_allocation_category_is_classified_as_virtual_platform_action(db_session):
    llc = _make_llc(db_session)
    prop = _make_property(db_session, llc.llc_id)

    parsed = webhook_parser_service.parse_bank_webhook(
        _webhook(prop.property_id, "200", "tax_allocation")
    )
    assert parsed.is_real_bank_tx is False
    assert parsed.sub_bucket_assignment == "Tax"


def test_repair_category_is_classified_as_real_bank_transaction(db_session):
    llc = _make_llc(db_session)
    prop = _make_property(db_session, llc.llc_id)

    parsed = webhook_parser_service.parse_bank_webhook(
        _webhook(prop.property_id, "-450", "repair")
    )
    assert parsed.is_real_bank_tx is True
    assert parsed.transaction_type == "Repair"
    assert parsed.sub_bucket_assignment is None


# --- Real-time bucket mutation via webhook --------------------------------------


def test_webhook_ingestion_mutates_bucket_and_settlement_queue_immediately(db_session):
    llc = _make_llc(db_session)
    prop = _make_property(db_session, llc.llc_id)

    parsed = webhook_parser_service.parse_bank_webhook(
        _webhook(prop.property_id, "175.00", "tax_allocation")
    )
    transaction_routing_service.ingest_webhook_transaction(db_session, parsed)

    refetched = property_service.get_property(db_session, prop.property_id)
    assert refetched.tax_bucket_balance == Decimal("175.00")
    assert refetched.tax_to_settle == Decimal("175.00")


def test_continuous_webhook_ingestion_compounds_settlement_queue(db_session):
    llc = _make_llc(db_session)
    prop = _make_property(db_session, llc.llc_id)

    for amount in ("50.00", "25.00", "10.00"):
        parsed = webhook_parser_service.parse_bank_webhook(
            _webhook(prop.property_id, amount, "reserve_allocation")
        )
        transaction_routing_service.ingest_webhook_transaction(db_session, parsed)

    refetched = property_service.get_property(db_session, prop.property_id)
    assert refetched.reserve_bucket_balance == Decimal("85.00")
    assert refetched.reserve_to_settle == Decimal("85.00")


# --- Rent → waterfall (percentage-based, NOT 100% of rent) ----------------------


def test_rent_webhook_allocates_only_configured_reserve_percentage(db_session):
    """The bug the operator hit: a $1500 rent webhook dumped the whole
    amount into reserves. With a 10% reserve setting it must only sweep $150.
    """
    llc = _make_llc(db_session)
    prop = _make_property(
        db_session,
        llc.llc_id,
        base_rent_target=Decimal("1500.00"),
        precentage_of_rent_to_reserve=Decimal("10.00"),
        target_tax_allocation=Decimal("0"),
    )
    assert prop.target_reserve_allocation == Decimal("150.00")

    parsed = webhook_parser_service.parse_bank_webhook(
        _webhook(prop.property_id, "1500.00", "rent", day=1)
    )
    result = transaction_routing_service.ingest_webhook_transaction(db_session, parsed)
    assert result["waterfall"] is not None
    assert Decimal(result["waterfall"]["reserve_filled"]) == Decimal("150.00")
    assert Decimal(result["waterfall"]["clean_cash_flow"]) == Decimal("1350.00")

    refetched = property_service.get_property(db_session, prop.property_id)
    assert refetched.reserve_bucket_balance == Decimal("150.00")
    assert refetched.reserve_to_settle == Decimal("150.00")


def test_rent_webhook_also_accrues_monthly_tax_and_queues_settlement(db_session):
    llc = _make_llc(db_session)
    prop = _make_property(
        db_session,
        llc.llc_id,
        base_rent_target=Decimal("1500.00"),
        precentage_of_rent_to_reserve=Decimal("10.00"),
        target_tax_allocation=Decimal("200.00"),
    )

    parsed = webhook_parser_service.parse_bank_webhook(
        _webhook(prop.property_id, "1500.00", "rent", day=1)
    )
    transaction_routing_service.ingest_webhook_transaction(db_session, parsed)

    refetched = property_service.get_property(db_session, prop.property_id)
    assert refetched.tax_bucket_balance == Decimal("200.00")
    assert refetched.tax_to_settle == Decimal("200.00")
    assert refetched.reserve_bucket_balance == Decimal("150.00")


def test_partial_rent_installments_finish_remaining_tax_and_reserve(db_session):
    llc = _make_llc(db_session)
    prop = _make_property(
        db_session,
        llc.llc_id,
        base_rent_target=Decimal("1500.00"),
        precentage_of_rent_to_reserve=Decimal("10.00"),  # $150
        target_tax_allocation=Decimal("200.00"),
    )

    # First installment: enough to cover tax fully + part of reserve.
    parsed_1 = webhook_parser_service.parse_bank_webhook(
        _webhook(prop.property_id, "250.00", "rent", day=1)
    )
    transaction_routing_service.ingest_webhook_transaction(db_session, parsed_1)
    after_1 = property_service.get_property(db_session, prop.property_id)
    assert after_1.tax_bucket_balance == Decimal("200.00")
    assert after_1.reserve_bucket_balance == Decimal("50.00")

    # Second installment finishes the remaining $100 reserve; no double tax.
    parsed_2 = webhook_parser_service.parse_bank_webhook(
        _webhook(prop.property_id, "300.00", "rent", day=10)
    )
    transaction_routing_service.ingest_webhook_transaction(db_session, parsed_2)
    after_2 = property_service.get_property(db_session, prop.property_id)
    assert after_2.tax_bucket_balance == Decimal("200.00")  # unchanged
    assert after_2.reserve_bucket_balance == Decimal("150.00")


def test_rent_with_zero_percentage_does_not_touch_reserve(db_session):
    llc = _make_llc(db_session)
    prop = _make_property(
        db_session,
        llc.llc_id,
        base_rent_target=Decimal("1500.00"),
        precentage_of_rent_to_reserve=Decimal("0"),
    )

    parsed = webhook_parser_service.parse_bank_webhook(
        _webhook(prop.property_id, "1500.00", "rent", day=1)
    )
    result = transaction_routing_service.ingest_webhook_transaction(db_session, parsed)
    assert Decimal(result["waterfall"]["reserve_filled"]) == Decimal("0.00")
    assert Decimal(result["waterfall"]["clean_cash_flow"]) == Decimal("1500.00")

    refetched = property_service.get_property(db_session, prop.property_id)
    assert refetched.reserve_bucket_balance == Decimal("0")


# --- HTTP-level webhook + nightly sync routes -----------------------------------


def test_bank_transaction_webhook_route_ingests_and_mutates_buckets(client):
    llc_res = client.post("/treasury/llcs", json={"llc_name": "Webhook Route LLC"})
    llc_id = llc_res.json()["llc_id"]
    prop_res = client.post(
        "/treasury/properties",
        json={"property_name": "route-prop", "llc_id": llc_id},
    )
    property_id = prop_res.json()["property_id"]

    res = client.post(
        "/treasury/webhooks/bank-transactions",
        json={
            "property_id": property_id,
            "amount": "260.00",
            "description": "Tax accrual sync",
            "timestamp": datetime(2026, 7, 1, tzinfo=timezone.utc).isoformat(),
            "category": "tax_allocation",
        },
    )
    assert res.status_code == 201
    body = res.json()
    assert body["transaction"]["is_real_bank_tx"] is False
    assert body["transaction"]["sub_bucket_assignment"] == "Tax"
    assert body["overflow_transaction"] is None

    prop_after = client.get(
        "/treasury/properties/item", params={"property_id": property_id}
    ).json()
    assert float(prop_after["tax_bucket_balance"]) == 260.0
    assert float(prop_after["tax_to_settle"]) == 260.0


def test_bank_transaction_webhook_route_rejects_unknown_category(client):
    llc_res = client.post("/treasury/llcs", json={"llc_name": "Bad Category LLC"})
    llc_id = llc_res.json()["llc_id"]
    prop_res = client.post(
        "/treasury/properties",
        json={"property_name": "route-prop-2", "llc_id": llc_id},
    )
    property_id = prop_res.json()["property_id"]

    res = client.post(
        "/treasury/webhooks/bank-transactions",
        json={
            "property_id": property_id,
            "amount": "100.00",
            "description": "bogus",
            "timestamp": datetime(2026, 7, 1, tzinfo=timezone.utc).isoformat(),
            "category": "crypto_yield",
        },
    )
    assert res.status_code == 400


def test_nightly_sync_route_runs_waterfall_on_rent_batch(client):
    llc_res = client.post("/treasury/llcs", json={"llc_name": "Nightly Sync LLC"})
    llc_id = llc_res.json()["llc_id"]
    prop_res = client.post(
        "/treasury/properties",
        json={
            "property_name": "nightly-prop",
            "llc_id": llc_id,
            "base_rent_target": "1000.00",
            "precentage_of_rent_to_reserve": "10.00",
            "target_tax_allocation": "100.00",
        },
    )
    property_id = prop_res.json()["property_id"]

    res = client.post(
        "/treasury/webhooks/nightly-sync",
        json=[
            {
                "property_id": property_id,
                "amount": "600.00",
                "description": "Rent installment 1",
                "timestamp": datetime(2026, 7, 2, tzinfo=timezone.utc).isoformat(),
                "category": "rent",
            },
            {
                "property_id": property_id,
                "amount": "400.00",
                "description": "Rent installment 2",
                "timestamp": datetime(2026, 7, 15, tzinfo=timezone.utc).isoformat(),
                "category": "rent",
            },
        ],
    )
    assert res.status_code == 201
    results = res.json()
    assert results[0]["waterfall"] is not None
    assert results[1]["waterfall"] is not None

    prop_after = client.get(
        "/treasury/properties/item", params={"property_id": property_id}
    ).json()
    # Tax target $100 + reserve target $100 allocated across the two payments.
    assert float(prop_after["tax_bucket_balance"]) == 100.0
    assert float(prop_after["reserve_bucket_balance"]) == 100.0
