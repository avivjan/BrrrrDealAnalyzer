"""Every feature area of the site, exercised through its MCP tools.

Each test drives the same code path the website does, via mcp_server.call_tool,
on the throwaway PostgreSQL (conftest.py). Integrations that need credentials
(Google Sheets/GCS, Mercury, SMTP) are either asserted on their deterministic
"not configured" branch or have their BL function monkeypatched at the router,
so nothing external is ever contacted.
"""

from __future__ import annotations

import base64
import importlib

import pytest

import db as app_db
from DAL.crud.reps import list_prospects
from ReqRes.common.reps_schemas import RepsUploadBatchRes, RepsUploadedFile
from tests.mcp_helpers import call, call_json

# `routers/__init__.py` rebinds `routers.reps` / `routers.email` to the APIRouter objects,
# so `import routers.reps` would hand back the router; ask for the modules explicitly.
reps_router = importlib.import_module("routers.reps")
email_router = importlib.import_module("routers.email")


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


@pytest.fixture
def no_integrations(monkeypatch):
    """Guarantee the Google / Mercury integrations take their 'not configured' branch."""
    for key in list(__import__("os").environ):
        if key.startswith(("REPS_", "MERCURY_API_TOKEN", "GOOGLE_APPLICATION_CREDENTIALS")):
            monkeypatch.delenv(key, raising=False)


class TestFlip:
    def test_analyze_flip_matches_the_endpoint(self, client, flip_payload):
        assert call_json("analyze_flip", body=flip_payload) == client.post("/analyze/flip", json=flip_payload).json()

    def test_flip_deal_lifecycle(self, client, flip_payload):
        created = call_json("add_active_deal", body=flip_payload)
        assert created["deal_type"] == "FLIP"

        edited = call_json("update_deal", deal_id=created["id"],
                           body={**flip_payload, "address": "3 Updated Way", "salePrice": 400})
        assert edited["address"] == "3 Updated Way"
        assert edited["net_profit"] > created["net_profit"], "a higher sale price must re-analyse"

        assert call_json("delete_deal", deal_id=created["id"], deal_type="FLIP") == {"message": "Deal deleted"}
        assert call_json("get_active_deals") == []

    def test_endpoint_validation_errors_surface_with_status_422(self, client, flip_payload):
        with pytest.raises(RuntimeError, match="HTTP 422"):
            call("analyze_flip", body={**flip_payload, "purchasePrice": "not a number"})


class TestBoughtFlow:
    def test_move_to_bought_then_tick_a_checklist_item(self, client, brrrr_payload):
        deal = call_json("add_active_deal", body={**brrrr_payload, "stage": 3})
        bought = call_json("move_to_bought", deal_id=deal["id"], deal_type="BRRRR")
        assert bought["boughtStage"] == "purchase"
        assert bought["sourceDealId"] == deal["id"]
        assert [d["id"] for d in call_json("get_bought_deals")] == [bought["id"]]
        assert len(call_json("get_active_deals")) == 1, "the active deal is kept"

        template = next(t for t in call_json("list_pipeline_templates") if t["dealType"] == "BRRRR")
        first_substage = template["stages"][0]["subStages"][0]["id"]
        ticked = call_json("update_bought_deal", deal_id=bought["id"],
                           body={**bought, "completedSubstages": {first_substage: True}})
        assert ticked["completedSubstages"] == {first_substage: True}

        stats = call_json("pipeline_template_stats", deal_type="BRRRR")
        purchase = next(s for s in stats["stages"] if s["stageId"] == "purchase")
        assert purchase["dealCount"] == 1

        assert call_json("delete_bought_deal", deal_id=bought["id"], deal_type="BRRRR") == {"message": "Bought deal deleted"}
        assert call_json("get_bought_deals") == []

    def test_add_bought_deal_directly(self, client, flip_payload):
        bought = call_json("add_bought_deal", body={**flip_payload, "boughtStage": "purchase"})
        assert bought["deal_type"] == "FLIP" and bought["boughtStage"] == "purchase"
        call_json("delete_bought_deal", deal_id=bought["id"], deal_type="FLIP")

    def test_wrong_deal_type_is_a_404(self, client, brrrr_payload):
        deal = call_json("add_active_deal", body=brrrr_payload)
        with pytest.raises(RuntimeError, match="HTTP 404"):
            call("move_to_bought", deal_id=deal["id"], deal_type="FLIP")


class TestPipelineTemplates:
    def test_list_and_update_round_trip(self, client):
        templates = call_json("list_pipeline_templates")
        assert {t["dealType"] for t in templates} == {"BRRRR", "FLIP"}
        flip = next(t for t in templates if t["dealType"] == "FLIP")

        extra = {"id": "stage_extra", "name": "Extra", "subStages": [{"id": "x", "label": "X"}]}
        updated = call_json("update_pipeline_template", deal_type="FLIP", body={"stages": flip["stages"] + [extra]})
        assert updated["stages"][-1]["id"] == "stage_extra"

        restored = call_json("update_pipeline_template", deal_type="FLIP", body={"stages": flip["stages"]})
        assert restored["stages"] == flip["stages"]

    def test_invalid_deal_type_is_a_400(self, client):
        with pytest.raises(RuntimeError, match="HTTP 400"):
            call("pipeline_template_stats", deal_type="FOO")


class TestLiquidity:
    def test_transactions_crud(self, client):
        created = call_json("create_liquidity_transaction",
                            body={"effective_date": "2026-10-01", "description": "Rent in", "amount_k": 2.5})
        assert created["amount_k"] == 2.5
        assert [t["id"] for t in call_json("list_liquidity_transactions")] == [created["id"]]

        updated = call_json("update_liquidity_transaction", txn_id=created["id"], body={"amount_k": 3})
        assert updated["amount_k"] == 3.0 and updated["description"] == "Rent in"

        assert call_json("delete_liquidity_transaction", txn_id=created["id"]) == {"message": "Transaction deleted"}
        assert call_json("list_liquidity_transactions") == []

    def test_recurring_rules_crud_and_validation(self, client):
        rule = call_json("create_liquidity_recurring", body={
            "description": "Mortgage", "amount_k": -1.2, "start_date": "2026-10-01",
            "frequency": "monthly", "occurrences": 6,
        })
        assert rule["frequency"] == "monthly" and rule["occurrences"] == 6
        assert [r["id"] for r in call_json("list_liquidity_recurring")] == [rule["id"]]

        assert call_json("update_liquidity_recurring", rule_id=rule["id"], body={"interval": 2})["interval"] == 2

        with pytest.raises(RuntimeError, match="HTTP 422"):
            call("create_liquidity_recurring", body={"description": "Zero", "amount_k": 0,
                                                     "start_date": "2026-10-01", "frequency": "weekly"})

        assert call_json("delete_liquidity_recurring", rule_id=rule["id"]) == {"message": "Recurring rule deleted"}

    def test_settings_update_and_read(self, client):
        updated = call_json("update_liquidity_settings",
                            body={"opening_balance_k": 50, "opening_balance_date": "2026-09-01", "reserve_k": 10})
        assert (updated["opening_balance_k"], updated["reserve_k"]) == (50.0, 10.0)
        assert call_json("get_liquidity_settings")["opening_balance_date"] == "2026-09-01"

    def test_mercury_unconfigured_is_a_503(self, client, no_integrations):
        with pytest.raises(RuntimeError, match="HTTP 503"):
            call("get_mercury_balance")


class TestReps:
    def test_people_crud(self, client):
        person = call_json("reps_create_person", body={"name": "Sam Lender", "role": "lender"})
        assert [p["id"] for p in call_json("reps_list_people")] == [person["id"]]
        assert call_json("reps_update_person", person_id=person["id"], body={"role": "broker"})["role"] == "broker"
        with pytest.raises(RuntimeError, match="HTTP 400"):
            call("reps_create_person", body={"name": "Sam Lender"})
        assert call_json("reps_delete_person", person_id=person["id"]) == {"message": "Person deleted"}
        assert call_json("reps_list_people") == []

    def test_prospects_and_categories(self, client):
        prospect = call_json("reps_create_prospect", body={"name": "9 Prospect Rd"})
        assert prospect["source"] == "prospect"
        assert {"name": "9 Prospect Rd", "source": "prospect"} in [
            {"name": p["name"], "source": p["source"]} for p in call_json("reps_properties")]
        # The API never exposes prospect ids (RepsPropertyOption is name + source), so read it from the DB.
        with app_db.SessionLocal() as session:
            prospect_id = str(list_prospects(session)[0].id)
        assert call_json("reps_delete_prospect", prospect_id=prospect_id) == {"message": "Prospect deleted"}
        with pytest.raises(RuntimeError, match="HTTP 404"):
            call("reps_delete_prospect", prospect_id=prospect_id)

        assert call_json("reps_list_activity_categories"), "categories are seeded"
        category = call_json("reps_create_activity_category", body={"name": "Zoom calls"})
        assert call_json("reps_delete_activity_category", cat_id=category["id"]) == {"message": "Activity category deleted"}

    def test_unconfigured_sheets_are_reported_not_crashed(self, client, no_integrations):
        assert call_json("reps_config_status")["configured"] is False
        with pytest.raises(RuntimeError, match="HTTP 503"):
            call("reps_entries", user="Aviv2026")

    def test_input_validation(self, client):
        with pytest.raises(RuntimeError, match="HTTP 400"):
            call("reps_entries", user="nobody")
        with pytest.raises(RuntimeError, match="HTTP 422"):
            call("reps_log", body={"user": "Aviv2026", "description": "too short",
                                   "start_time": "2026-09-07T09:00:00", "end_time": "2026-09-07T10:00:00"})


class TestMultipart:
    def test_upload_batch_passes_file_bytes_through(self, client, monkeypatch):
        captured = {}

        def fake_upload_batch(*, user, property_name, activity_category, log_timestamp, items):
            captured.update(user=user, property_name=property_name, items=items)
            return RepsUploadBatchRes(folder_path="logs/x", files=[
                RepsUploadedFile(name=n, url=f"gs://bucket/{n}", content_type=ct, size_bytes=len(b)) for n, ct, b in items])

        monkeypatch.setattr(reps_router, "upload_batch_bl", fake_upload_batch)
        result = call_json("reps_upload_batch", user="Aviv2026", property_name="1 Main St", files=[
            {"filename": "a.jpg", "content_type": "image/jpeg", "content_base64": _b64(b"\xff\xd8jpeg")},
            {"filename": "b.txt", "content_base64": _b64(b"hello")},
        ])
        assert captured["user"] == "Aviv2026" and captured["property_name"] == "1 Main St"
        assert captured["items"] == [("a.jpg", "image/jpeg", b"\xff\xd8jpeg"),
                                     ("b.txt", "application/octet-stream", b"hello")]
        assert [f["size_bytes"] for f in result["files"]] == [6, 5]

    def test_single_upload(self, client, monkeypatch):
        captured = {}

        def fake_upload_single(*, user, file_bytes, filename, content_type):
            captured.update(user=user, file_bytes=file_bytes, filename=filename)
            return "gs://bucket/c.png"

        monkeypatch.setattr(reps_router, "upload_single_bl", fake_upload_single)
        result = call_json("reps_upload", user="Yarden2026",
                           file={"filename": "c.png", "content_type": "image/png", "content_base64": _b64(b"\x89PNG")})
        assert result == {"url": "gs://bucket/c.png", "filename": "c.png"}
        assert captured == {"user": "Yarden2026", "file_bytes": b"\x89PNG", "filename": "c.png"}


class TestSendOffer:
    def test_forwards_the_offer_without_mail(self, client, monkeypatch):
        captured = {}

        def fake_send(payload):
            captured["payload"] = payload
            return True, "Offer sent"

        monkeypatch.setattr(email_router, "send_offer_email", fake_send)
        result = call_json("send_offer", body={
            "agent_name": "Ann Agent", "agent_email": "ann@example.com", "property_address": "5 Offer Ln",
            "purchase_price": 250000, "inspection_period_days": 10,
        })
        assert result == {"message": "Offer sent", "success": True}
        assert captured["payload"].property_address == "5 Offer Ln"
        assert float(captured["payload"].purchase_price) == 250000


class TestCompactDealTools:
    """The tools a chat should reach for first: small, searchable, then detail on demand."""

    def test_list_search_portfolio_and_detail(self, client, brrrr_payload, flip_payload):
        brrr = call_json("add_active_deal", body={**brrrr_payload, "stage": 3, "notes": "duplex by the beach"})
        flip = call_json("add_active_deal", body=flip_payload)
        bought = call_json("move_to_bought", deal_id=brrr["id"], deal_type="BRRRR")

        rows = call_json("list_deals")
        assert {r["id"] for r in rows} == {brrr["id"], flip["id"], bought["id"]}
        assert all("breakdowns" not in r for r in rows)
        assert [r["id"] for r in call_json("list_deals", board="bought")] == [bought["id"]]
        assert [r["id"] for r in call_json("search_deals", q="duplex beach")] == sorted(
            [brrr["id"], bought["id"]], key=lambda i: [r["id"] for r in call_json("search_deals", q="duplex beach")].index(i))

        summary = call_json("portfolio_summary")
        assert (summary["active_count"], summary["bought_count"]) == (2, 1)
        assert summary["top_bought_by_equity"][0]["id"] == bought["id"]

        detail = call_json("get_deal", deal_id=bought["id"])
        assert detail["board"] == "bought" and "breakdowns" in detail["deal"]
        with pytest.raises(RuntimeError, match="HTTP 404"):
            call("get_deal", deal_id=str(__import__("uuid").uuid4()))
