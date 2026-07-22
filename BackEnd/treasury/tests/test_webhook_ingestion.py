"""Integration tests for the webhook ingestion pipeline: category parsing,
real vs. virtual classification, real-time bucket mutation, and the
cumulative rent milestone / overflow engine.
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


# --- Cumulative rent milestone engine -------------------------------------------


def test_partial_rent_payments_aggregate_before_overflow_triggers(db_session):
    llc = _make_llc(db_session)
    prop = _make_property(db_session, llc.llc_id, base_rent_target=Decimal("1500.00"))

    # First partial payment: well under target, no overflow.
    parsed_1 = webhook_parser_service.parse_bank_webhook(
        _webhook(prop.property_id, "800.00", "rent", day=1)
    )
    result_1 = transaction_routing_service.ingest_webhook_transaction(db_session, parsed_1)
    assert result_1["overflow_transaction"] is None

    prop_after_1 = property_service.get_property(db_session, prop.property_id)
    assert prop_after_1.reserve_bucket_balance == Decimal("0")

    # Second partial payment: brings cumulative to exactly the target —
    # reaching it exactly is not "exceeding" it, so still no overflow.
    parsed_2 = webhook_parser_service.parse_bank_webhook(
        _webhook(prop.property_id, "700.00", "rent", day=10)
    )
    result_2 = transaction_routing_service.ingest_webhook_transaction(db_session, parsed_2)
    assert result_2["overflow_transaction"] is None

    prop_after_2 = property_service.get_property(db_session, prop.property_id)
    assert prop_after_2.reserve_bucket_balance == Decimal("0")

    # Third payment: cumulative rent already met the target, so this
    # entire payment is overflow and gets swept into the reserve bucket.
    parsed_3 = webhook_parser_service.parse_bank_webhook(
        _webhook(prop.property_id, "200.00", "rent", day=20)
    )
    result_3 = transaction_routing_service.ingest_webhook_transaction(db_session, parsed_3)
    overflow = result_3["overflow_transaction"]
    assert overflow is not None
    assert overflow.amount == Decimal("200.00")
    assert overflow.sub_bucket_assignment == "General Reserve"
    assert overflow.is_real_bank_tx is False

    prop_after_3 = property_service.get_property(db_session, prop.property_id)
    assert prop_after_3.reserve_bucket_balance == Decimal("200.00")
    assert prop_after_3.reserve_to_settle == Decimal("200.00")


def test_single_payment_crossing_target_only_overflows_the_excess(db_session):
    llc = _make_llc(db_session)
    prop = _make_property(db_session, llc.llc_id, base_rent_target=Decimal("1000.00"))

    parsed = webhook_parser_service.parse_bank_webhook(
        _webhook(prop.property_id, "1300.00", "rent", day=3)
    )
    result = transaction_routing_service.ingest_webhook_transaction(db_session, parsed)

    overflow = result["overflow_transaction"]
    assert overflow is not None
    assert overflow.amount == Decimal("300.00")

    refetched = property_service.get_property(db_session, prop.property_id)
    assert refetched.reserve_bucket_balance == Decimal("300.00")


def test_rent_milestone_window_resets_for_a_new_month(db_session):
    llc = _make_llc(db_session)
    prop = _make_property(db_session, llc.llc_id, base_rent_target=Decimal("1000.00"))

    july_full = webhook_parser_service.parse_bank_webhook(
        _webhook(prop.property_id, "1000.00", "rent", day=1)
    )
    transaction_routing_service.ingest_webhook_transaction(db_session, july_full)

    # New calendar month — cumulative rent resets, so a fresh partial
    # payment must NOT immediately overflow just because July hit target.
    august_partial = BankWebhookPayload(
        property_id=prop.property_id,
        amount=Decimal("400.00"),
        description="August partial rent",
        timestamp=datetime(2026, 8, 2, tzinfo=timezone.utc),
        category="rent",
    )
    parsed_august = webhook_parser_service.parse_bank_webhook(august_partial)
    result_august = transaction_routing_service.ingest_webhook_transaction(
        db_session, parsed_august
    )
    assert result_august["overflow_transaction"] is None


def test_property_without_base_rent_target_never_overflows(db_session):
    llc = _make_llc(db_session)
    prop = _make_property(db_session, llc.llc_id)  # base_rent_target defaults to 0

    parsed = webhook_parser_service.parse_bank_webhook(
        _webhook(prop.property_id, "5000.00", "rent", day=1)
    )
    result = transaction_routing_service.ingest_webhook_transaction(db_session, parsed)
    assert result["overflow_transaction"] is None


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


def test_nightly_sync_route_ingests_a_batch_and_triggers_overflow(client):
    llc_res = client.post("/treasury/llcs", json={"llc_name": "Nightly Sync LLC"})
    llc_id = llc_res.json()["llc_id"]
    prop_res = client.post(
        "/treasury/properties",
        json={
            "property_name": "nightly-prop",
            "llc_id": llc_id,
            "base_rent_target": "1000.00",
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
                "amount": "700.00",
                "description": "Rent installment 2",
                "timestamp": datetime(2026, 7, 15, tzinfo=timezone.utc).isoformat(),
                "category": "rent",
            },
        ],
    )
    assert res.status_code == 201
    results = res.json()
    assert results[0]["overflow_transaction"] is None
    assert results[1]["overflow_transaction"] is not None
    assert float(results[1]["overflow_transaction"]["amount"]) == 300.0

    prop_after = client.get(
        "/treasury/properties/item", params={"property_id": property_id}
    ).json()
    assert float(prop_after["reserve_bucket_balance"]) == 300.0
