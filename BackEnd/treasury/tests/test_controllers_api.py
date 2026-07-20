"""End-to-end HTTP tests through the real FastAPI controllers."""

from datetime import datetime, timezone


def test_llc_full_crud_via_api(client):
    create_res = client.post(
        "/treasury/llcs",
        json={"llc_name": "API LLC", "checking_redline_buffer": "500.00"},
    )
    assert create_res.status_code == 201
    llc_id = create_res.json()["llc_id"]
    assert create_res.json()["llc_name"] == "API LLC"
    assert float(create_res.json()["checking_redline_buffer"]) == 500.0

    list_res = client.get("/treasury/llcs")
    assert list_res.status_code == 200
    assert any(row["llc_id"] == llc_id for row in list_res.json())

    get_res = client.get(f"/treasury/llcs/{llc_id}")
    assert get_res.status_code == 200

    update_res = client.put(
        f"/treasury/llcs/{llc_id}",
        json={"checking_redline_buffer": "1.23"},
    )
    assert update_res.status_code == 200
    assert float(update_res.json()["checking_redline_buffer"]) == 1.23

    delete_res = client.delete(f"/treasury/llcs/{llc_id}")
    assert delete_res.status_code == 200

    missing_res = client.get(f"/treasury/llcs/{llc_id}")
    assert missing_res.status_code == 404


def test_property_full_crud_via_api(client):
    llc_res = client.post("/treasury/llcs", json={"llc_name": "Prop LLC"})
    llc_id = llc_res.json()["llc_id"]

    create_res = client.post(
        "/treasury/properties",
        json={"property_id": "456-oak-ave", "llc_id": llc_id, "reserve_debt": "5000"},
    )
    assert create_res.status_code == 201
    property_id = create_res.json()["property_id"]

    update_res = client.put(
        f"/treasury/properties/{property_id}",
        json={"reserve_debt": "77.77", "force_tax_ins_accrual": True},
    )
    assert update_res.status_code == 200
    assert float(update_res.json()["reserve_debt"]) == 77.77
    assert update_res.json()["force_tax_ins_accrual"] is True

    list_res = client.get("/treasury/properties", params={"llc_id": llc_id})
    assert list_res.status_code == 200
    assert len(list_res.json()) == 1

    delete_res = client.delete(f"/treasury/properties/{property_id}")
    assert delete_res.status_code == 200


def test_property_create_rejects_unknown_llc_via_api(client):
    res = client.post(
        "/treasury/properties",
        json={"property_id": "ghost", "llc_id": "ghost-llc"},
    )
    assert res.status_code == 400


def test_cash_flow_history_full_crud_via_api(client):
    llc_res = client.post("/treasury/llcs", json={"llc_name": "History LLC"})
    llc_id = llc_res.json()["llc_id"]
    prop_res = client.post(
        "/treasury/properties",
        json={"property_id": "hist-prop", "llc_id": llc_id},
    )
    property_id = prop_res.json()["property_id"]

    create_res = client.post(
        "/treasury/cash-flow-history",
        json={
            "property_id": property_id,
            "month_year": "2026-07",
            "monthly_cash_flow": "321.00",
        },
    )
    assert create_res.status_code == 201
    history_id = create_res.json()["history_id"]

    update_res = client.put(
        f"/treasury/cash-flow-history/{history_id}",
        json={"cumulative_cash_flow": "999.99"},
    )
    assert update_res.status_code == 200
    assert float(update_res.json()["cumulative_cash_flow"]) == 999.99

    list_res = client.get(
        "/treasury/cash-flow-history",
        params={"property_id": property_id},
    )
    assert list_res.status_code == 200
    assert len(list_res.json()) == 1

    delete_res = client.delete(f"/treasury/cash-flow-history/{history_id}")
    assert delete_res.status_code == 200


def test_deleting_llc_via_api_cascades_to_property(client):
    llc_res = client.post("/treasury/llcs", json={"llc_name": "Cascade API LLC"})
    llc_id = llc_res.json()["llc_id"]
    prop_res = client.post(
        "/treasury/properties",
        json={"property_id": "cascade-prop", "llc_id": llc_id},
    )
    property_id = prop_res.json()["property_id"]

    delete_res = client.delete(f"/treasury/llcs/{llc_id}")
    assert delete_res.status_code == 200

    missing_prop = client.get(f"/treasury/properties/{property_id}")
    assert missing_prop.status_code == 404


def test_transaction_full_crud_via_api(client):
    llc_res = client.post("/treasury/llcs", json={"llc_name": "Txn LLC"})
    llc_id = llc_res.json()["llc_id"]
    prop_res = client.post(
        "/treasury/properties",
        json={"property_id": "txn-prop", "llc_id": llc_id},
    )
    property_id = prop_res.json()["property_id"]

    create_res = client.post(
        "/treasury/transactions",
        json={
            "property_id": property_id,
            "amount": "1200.00",
            "description": "Rent payment",
            "timestamp": datetime(2026, 7, 1, tzinfo=timezone.utc).isoformat(),
            "transaction_type": "Rent",
            "sub_bucket_assignment": "Tax",
        },
    )
    assert create_res.status_code == 201
    transaction_id = create_res.json()["transaction_id"]

    update_res = client.put(
        f"/treasury/transactions/{transaction_id}",
        json={"amount": "-50.00", "sub_bucket_assignment": "Insurance"},
    )
    assert update_res.status_code == 200
    assert float(update_res.json()["amount"]) == -50.0

    delete_res = client.delete(f"/treasury/transactions/{transaction_id}")
    assert delete_res.status_code == 200
