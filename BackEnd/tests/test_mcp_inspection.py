"""MCP tools of the property inspections (tasks/todo/PropertyInspection.md)."""

from __future__ import annotations

import mcp_server
from tests.inspection_helpers import create_bought_deal
from tests.mcp_helpers import call_json

INSPECTION_TOOL_NAMES = {
    "list_inspections",
    "get_inspection",
    "create_inspection",
    "update_inspection_start_info",
    "update_inspection_item",
    "complete_inspection",
    "delete_inspection_photo",
    "delete_inspection",
    "get_inspection_deal_link",
    "link_inspection_to_deal",
    "unlink_inspection_from_deal",
    "list_bought_deal_inspections",
    "create_inspection_for_bought_deal",
}


def test_every_inspection_route_is_a_tool_except_the_binary_photo_routes():
    tools = mcp_server.tools()
    assert INSPECTION_TOOL_NAMES <= set(tools)
    assert not {"upload_inspection_photo", "get_inspection_photo_thumbnail", "get_inspection_photo_full_image"} & set(tools)


def test_inspection_tool_annotations():
    tools = mcp_server.tools()
    assert tools["get_inspection"]["tool"].annotations.readOnlyHint is True
    assert tools["list_inspections"]["tool"].annotations.readOnlyHint is True
    assert tools["delete_inspection"]["tool"].annotations.destructiveHint is True
    assert tools["unlink_inspection_from_deal"]["tool"].annotations.destructiveHint is True
    assert tools["update_inspection_item"]["tool"].annotations.destructiveHint is False


def test_create_update_get_list_link_and_unlink_through_tools(client, brrrr_payload):
    created = call_json("create_inspection", body={"property_address": "77 Gulf Blvd, Clearwater, FL", "inspector_name": "Claude"})
    inspection_id = created["id"]

    updated = call_json(
        "update_inspection_item",
        inspection_id=inspection_id,
        item_key="sewer",
        body={"item_status": "repair", "item_field_values": {"sewer_type": "septic", "septic_last_pump_date": "2023-05-01"}},
    )
    assert updated["item_field_values"] == {"sewer_type": "septic", "septic_last_pump_date": "2023-05-01"}

    inspection = call_json("get_inspection", inspection_id=inspection_id)
    assert inspection["summary"]["items_marked_repair"][0]["item_key"] == "sewer"
    assert "sewer" not in inspection["summary"]["critical_item_keys_not_checked"]

    assert [row["id"] for row in call_json("list_inspections")] == [inspection_id]

    deal = create_bought_deal(client, brrrr_payload)
    linked = call_json("link_inspection_to_deal", inspection_id=inspection_id, body={"bought_deal_id": deal["id"], "deal_type": "BRRRR"})
    assert linked["linked_deal"]["bought_deal_id"] == deal["id"]
    assert call_json("get_inspection", inspection_id=inspection_id)["linked"] is True

    assert call_json("unlink_inspection_from_deal", inspection_id=inspection_id) == {"linked_deal": None}
    assert call_json("get_inspection", inspection_id=inspection_id)["linked"] is False
