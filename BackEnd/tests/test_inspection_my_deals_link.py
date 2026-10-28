"""Linking inspections to My Deals deals as well as Bought Deals (tasks/todo/InspectionLinkToMyDeals.md)."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

import db as app_db
from migrations.steps.inspection_link_to_active_deals import add_inspection_links_to_active_deals
from tests.inspection_helpers import (  # noqa: F401 -- fixtures
    PUBLIC_WRITE_HEADERS,
    create_public_inspection,
    enforced_login,
    find_keys_anywhere,
    update_item,
)
from tests.mcp_helpers import call_json


def create_active_deal(client, payload: dict) -> dict:
    response = client.post("/active-deals", json=payload, headers=PUBLIC_WRITE_HEADERS)
    assert response.status_code == 200, response.text
    return response.json()


def link(client, inspection_id: str, deal: dict, deal_type: str, deal_board: str = "my_deals"):
    return client.put(
        f"/inspections/{inspection_id}/deal-link",
        json={"deal_id": deal["id"], "deal_type": deal_type, "deal_board": deal_board},
        headers=PUBLIC_WRITE_HEADERS,
    )


class TestLinkToMyDeals:
    @pytest.mark.parametrize("deal_type", ["BRRRR", "FLIP"])
    def test_link_and_unlink_a_my_deals_deal(self, client, brrrr_payload, flip_payload, deal_type):
        deal = create_active_deal(client, brrrr_payload if deal_type == "BRRRR" else flip_payload)
        inspection_id = create_public_inspection(client)["id"]
        response = link(client, inspection_id, deal, deal_type)
        assert response.status_code == 200, response.text
        assert response.json()["linked_deal"] == {"deal_id": deal["id"], "deal_type": deal_type, "deal_board": "my_deals", "property_address": deal["address"]}
        assert [row["id"] for row in client.get(f"/active-deals/{deal['id']}/inspections?deal_type={deal_type}").json()] == [inspection_id]
        assert client.get("/inspections").json()[0]["linked_deal"]["deal_board"] == "my_deals"
        assert client.delete(f"/inspections/{inspection_id}/deal-link", headers=PUBLIC_WRITE_HEADERS).json() == {"linked_deal": None}
        assert client.get(f"/active-deals/{deal['id']}/inspections?deal_type={deal_type}").json() == []

    def test_relinking_moves_the_link_between_boards(self, client, brrrr_payload):
        active_deal = create_active_deal(client, brrrr_payload)
        bought_deal = client.post("/bought-deals", json={**brrrr_payload, "deal_type": "BRRRR"}, headers=PUBLIC_WRITE_HEADERS).json()
        inspection_id = create_public_inspection(client)["id"]
        link(client, inspection_id, active_deal, "BRRRR")
        assert link(client, inspection_id, bought_deal, "BRRRR", "bought").json()["linked_deal"]["deal_board"] == "bought"
        assert client.get(f"/active-deals/{active_deal['id']}/inspections?deal_type=BRRRR").json() == []

    def test_deal_board_defaults_to_bought(self, client, brrrr_payload):
        bought_deal = client.post("/bought-deals", json={**brrrr_payload, "deal_type": "BRRRR"}, headers=PUBLIC_WRITE_HEADERS).json()
        inspection_id = create_public_inspection(client)["id"]
        response = client.put(f"/inspections/{inspection_id}/deal-link", json={"deal_id": bought_deal["id"], "deal_type": "BRRRR"}, headers=PUBLIC_WRITE_HEADERS)
        assert response.json()["linked_deal"]["deal_board"] == "bought"

    def test_unknown_board_or_missing_deal_is_refused(self, client, brrrr_payload):
        deal = create_active_deal(client, brrrr_payload)
        inspection_id = create_public_inspection(client)["id"]
        assert link(client, inspection_id, deal, "BRRRR", "somewhere").status_code == 422
        assert link(client, inspection_id, {"id": str(uuid.uuid4())}, "BRRRR").status_code == 404
        assert link(client, inspection_id, deal, "FLIP").status_code == 404  # a BRRRR deal is not a FLIP deal

    def test_new_inspection_from_a_my_deals_deal_is_linked_with_its_address(self, client, flip_payload):
        deal = create_active_deal(client, flip_payload)
        response = client.post(f"/active-deals/{deal['id']}/inspections?deal_type=FLIP", json={}, headers=PUBLIC_WRITE_HEADERS)
        assert response.status_code == 201, response.text
        assert response.json()["property_address"] == deal["address"]
        assert response.json()["linked"] is True

    def test_public_responses_carry_no_my_deals_data(self, client, brrrr_payload):
        deal = create_active_deal(client, brrrr_payload)
        inspection = client.post(f"/active-deals/{deal['id']}/inspections?deal_type=BRRRR", json={}, headers=PUBLIC_WRITE_HEADERS).json()
        public_body = client.get(f"/public/inspections/{inspection['id']}").json()
        assert public_body["linked"] is True
        assert find_keys_anywhere(public_body, ("deal", "brrrr", "flip", "board")) == []
        assert deal["id"] not in str(public_body)

    def test_deleting_the_my_deals_deal_clears_the_link(self, client, brrrr_payload):
        deal = create_active_deal(client, brrrr_payload)
        inspection = client.post(f"/active-deals/{deal['id']}/inspections?deal_type=BRRRR", json={}, headers=PUBLIC_WRITE_HEADERS).json()
        assert client.delete(f"/active-deals/{deal['id']}?deal_type=BRRRR", headers=PUBLIC_WRITE_HEADERS).status_code == 200
        assert client.get(f"/public/inspections/{inspection['id']}").json()["linked"] is False


class TestMoveToBought:
    @pytest.mark.parametrize("deal_type", ["BRRRR", "FLIP"])
    def test_inspections_follow_the_deal_to_bought(self, client, brrrr_payload, flip_payload, deal_type):
        deal = create_active_deal(client, brrrr_payload if deal_type == "BRRRR" else flip_payload)
        inspection = client.post(f"/active-deals/{deal['id']}/inspections?deal_type={deal_type}", json={}, headers=PUBLIC_WRITE_HEADERS).json()
        bought_deal = client.post(f"/bought-deals/from-active/{deal['id']}?deal_type={deal_type}", headers=PUBLIC_WRITE_HEADERS).json()
        assert [row["id"] for row in client.get(f"/bought-deals/{bought_deal['id']}/inspections?deal_type={deal_type}").json()] == [inspection["id"]]
        assert client.get(f"/active-deals/{deal['id']}/inspections?deal_type={deal_type}").json() == []
        link_details = client.get(f"/inspections/{inspection['id']}/deal-link").json()["linked_deal"]
        assert (link_details["deal_board"], link_details["deal_id"]) == ("bought", bought_deal["id"])


class TestAccess:
    def test_my_deals_inspection_routes_need_a_session(self, client, enforced_login):  # noqa: F811
        deal_id = str(uuid.uuid4())
        assert client.get(f"/active-deals/{deal_id}/inspections?deal_type=BRRRR").status_code == 401
        assert client.post(f"/active-deals/{deal_id}/inspections?deal_type=BRRRR", json={}, headers=PUBLIC_WRITE_HEADERS).status_code == 401
        inspection_id = create_public_inspection(client)["id"]
        body = {"deal_id": deal_id, "deal_type": "BRRRR", "deal_board": "my_deals"}
        assert client.put(f"/inspections/{inspection_id}/deal-link", json=body, headers=PUBLIC_WRITE_HEADERS).status_code == 401


class TestDatabase:
    def test_an_inspection_cannot_hold_two_deal_links(self, client, brrrr_payload):
        active_deal = create_active_deal(client, brrrr_payload)
        bought_deal = client.post("/bought-deals", json={**brrrr_payload, "deal_type": "BRRRR"}, headers=PUBLIC_WRITE_HEADERS).json()
        inspection_id = create_public_inspection(client)["id"]
        with pytest.raises(IntegrityError):
            with app_db.engine.begin() as connection:
                connection.execute(
                    text("UPDATE property_inspections SET linked_active_brrrr_deal_id = :active, linked_bought_brrrr_deal_id = :bought WHERE id = :id"),
                    {"active": active_deal["id"], "bought": bought_deal["id"], "id": inspection_id},
                )

    def test_the_migration_step_is_idempotent(self):
        from sqlalchemy import inspect as sa_inspect

        add_inspection_links_to_active_deals(app_db.engine, sa_inspect(app_db.engine))
        add_inspection_links_to_active_deals(app_db.engine, sa_inspect(app_db.engine))
        columns = {column["name"] for column in sa_inspect(app_db.engine).get_columns("property_inspections")}
        assert {"linked_active_brrrr_deal_id", "linked_active_flip_deal_id"} <= columns


class TestMcp:
    def test_link_to_my_deals_through_the_tool(self, client, brrrr_payload):
        deal = create_active_deal(client, brrrr_payload)
        created = call_json("create_inspection", body={"property_address": "3 Pine St, Tampa, FL"})
        linked = call_json("link_inspection_to_deal", inspection_id=created["id"], body={"deal_id": deal["id"], "deal_type": "BRRRR", "deal_board": "my_deals"})
        assert linked["linked_deal"]["deal_board"] == "my_deals"
        rows = call_json("list_active_deal_inspections", deal_id=deal["id"], deal_type="BRRRR")
        assert [row["id"] for row in rows] == [created["id"]]
