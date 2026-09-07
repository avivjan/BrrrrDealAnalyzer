"""The MCP server (mcp_server.py): every endpoint is a tool, tools do what the
endpoints do, and the Streamable HTTP transport answers at the mounted path.

Runs on the same throwaway PostgreSQL as the rest of the suite (conftest.py).
"""

from __future__ import annotations

import asyncio
import base64
import json
import pathlib
import uuid

import pytest

import mcp_server
from main import app

GOLDEN_OPENAPI = pathlib.Path(__file__).parent / "_regression_snapshots" / "openapi.json"


def _call(name: str, **arguments):
    """Call a tool and return its content blocks."""
    return asyncio.run(mcp_server.call_tool(name, arguments))


def _call_json(name: str, **arguments):
    blocks = _call(name, **arguments)
    assert len(blocks) == 1 and blocks[0].type == "text"
    return json.loads(blocks[0].text)


class TestToolList:
    def test_every_endpoint_is_a_tool_with_a_description(self):
        app.openapi_schema = None
        operations = sum(len(ops) for ops in app.openapi()["paths"].values())
        tools = mcp_server.tools()
        assert len(tools) == operations
        undocumented = [n for n in tools if n not in mcp_server.DESCRIPTIONS]
        assert undocumented == [], f"add these to mcp_server.DESCRIPTIONS: {undocumented}"
        stale = [n for n in mcp_server.DESCRIPTIONS if n not in tools]
        assert stale == [], f"DESCRIPTIONS entries without an endpoint: {stale}"

    def test_schemas_are_self_contained(self):
        for spec in mcp_server.tools().values():
            dumped = json.dumps(spec["tool"].inputSchema)
            assert "#/components/" not in dumped, spec["tool"].name
            assert ("#/$defs/" not in dumped) or ("$defs" in spec["tool"].inputSchema)

    def test_openapi_contract_is_untouched(self):
        app.openapi_schema = None
        assert app.openapi() == json.loads(GOLDEN_OPENAPI.read_text())

    def test_path_follows_the_secret(self, monkeypatch):
        monkeypatch.delenv("MCP_PATH_SECRET", raising=False)
        assert mcp_server.mcp_path() == "/mcp"
        monkeypatch.setenv("MCP_PATH_SECRET", "s3cret")
        assert mcp_server.mcp_path() == "/mcp/s3cret"


class TestToolsDoWhatTheEndpointsDo:
    def test_analyze_brrr_matches_the_endpoint(self, client, brrrr_payload):
        via_tool = _call_json("analyze_brrr", body=brrrr_payload)
        via_http = client.post("/analyze/brrr", json=brrrr_payload).json()
        assert via_tool == via_http

    def test_active_deal_lifecycle(self, client, brrrr_payload):
        created = _call_json("add_active_deal", body=brrrr_payload)
        assert created["address"] == brrrr_payload["address"]

        listed = _call_json("get_active_deals")
        assert [d["id"] for d in listed] == [created["id"]]

        copy = _call_json("duplicate_deal", deal_id=created["id"], deal_type="BRRRR")
        assert copy["id"] != created["id"]
        assert len(_call_json("get_active_deals")) == 2

        for deal_id in (created["id"], copy["id"]):
            assert _call_json("delete_deal", deal_id=deal_id, deal_type="BRRRR") == {
                "message": "Deal deleted"
            }
        assert _call_json("get_active_deals") == []

    def test_pdf_report_comes_back_as_a_blob(self, client, brrrr_payload):
        blocks = _call("report_brrr_pdf", address="1 Shared Form St", body=brrrr_payload)
        assert [b.type for b in blocks] == ["text", "resource"]
        resource = blocks[1].resource
        assert resource.mimeType == "application/pdf"
        assert base64.b64decode(resource.blob).startswith(b"%PDF")

    def test_http_errors_become_tool_errors(self, client):
        with pytest.raises(RuntimeError, match="HTTP 404"):
            _call("delete_deal", deal_id=str(uuid.uuid4()), deal_type="BRRRR")

    def test_missing_path_param_is_rejected(self, client):
        with pytest.raises(ValueError, match="deal_id"):
            _call("delete_deal", deal_type="BRRRR")


class TestStreamableHttp:
    HEADERS = {"Accept": "application/json, text/event-stream"}

    def _rpc(self, client, method, params=None, id=1):
        body = {"jsonrpc": "2.0", "id": id, "method": method, "params": params or {}}
        response = client.post("/mcp", json=body, headers=self.HEADERS)
        assert response.status_code == 200, response.text
        return response.json()

    def test_initialize_and_list_tools(self, client):
        init = self._rpc(client, "initialize", {
            "protocolVersion": "2025-06-18",
            "capabilities": {},
            "clientInfo": {"name": "pytest", "version": "0"},
        })
        assert init["result"]["serverInfo"]["name"] == "brrrr-deal-analyzer"
        assert "THOUSANDS" in init["result"]["instructions"]

        # Stateless: no session id needed between requests.
        listed = self._rpc(client, "tools/list", id=2)
        names = {tool["name"] for tool in listed["result"]["tools"]}
        assert names == set(mcp_server.tools())

    def test_call_tool_over_http(self, client):
        result = self._rpc(client, "tools/call", {"name": "helloworld", "arguments": {}})
        assert json.loads(result["result"]["content"][0]["text"]) == {"message": "Hello, World!"}
        assert not result["result"].get("isError")

    def test_tool_error_over_http_is_flagged_not_raised(self, client):
        result = self._rpc(client, "tools/call", {
            "name": "delete_deal",
            "arguments": {"deal_id": str(uuid.uuid4()), "deal_type": "BRRRR"},
        })
        assert result["result"]["isError"] is True
        assert "HTTP 404" in result["result"]["content"][0]["text"]

    def test_other_paths_are_not_mcp(self, client):
        assert client.post("/mcp/wrong", json={}, headers=self.HEADERS).status_code == 404
