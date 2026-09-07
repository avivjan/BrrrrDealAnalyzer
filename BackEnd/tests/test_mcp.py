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

import jsonschema
import pytest
from fastapi import FastAPI

import mcp_server
from main import app

GOLDEN_OPENAPI = pathlib.Path(__file__).parent / "_regression_snapshots" / "openapi.json"


from tests.mcp_helpers import call as _call, call_json as _call_json  # noqa: E402


class TestToolList:
    def test_every_endpoint_is_a_tool_with_a_description(self):
        app.openapi_schema = None
        operations = sum(
            len(ops) for path, ops in app.openapi()["paths"].items() if not path.startswith(mcp_server.EXCLUDED_PREFIXES)
        )
        tools = mcp_server.tools()
        assert len(tools) == operations
        assert not any(spec["path"].startswith(mcp_server.EXCLUDED_PREFIXES) for spec in tools.values())
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


class TestEveryToolSchema:
    """One check per tool, so a regression names the tool."""

    @pytest.mark.parametrize("name", sorted(mcp_server.tools()))
    def test_schema_is_valid_and_complete(self, name):
        spec = mcp_server.tools()[name]
        tool = spec["tool"]
        jsonschema.Draft202012Validator.check_schema(tool.inputSchema)

        properties = set(tool.inputSchema["properties"])
        expected = set(spec["path_params"] + spec["query_params"] + spec["form_fields"] + spec["file_fields"])
        if spec["json_body"]:
            expected.add(mcp_server.BODY_ARG)
        assert properties == expected

        required = set(tool.inputSchema.get("required", []))
        assert set(spec["path_params"]) <= required, "path params must be required"

        assert tool.description and tool.description == tool.description.strip()
        assert len(tool.description) <= 400
        assert not name.endswith("_route")

    def test_body_is_required_exactly_when_openapi_says_so(self):
        app.openapi_schema = None
        paths = app.openapi()["paths"]
        for name, spec in mcp_server.tools().items():
            if not spec["json_body"]:
                continue
            op = paths[spec["path"]][spec["method"].lower()]
            required = mcp_server.BODY_ARG in spec["tool"].inputSchema.get("required", [])
            assert required == bool(op["requestBody"].get("required")), name

    def test_tools_list_payload_stays_within_budget(self):
        payload = json.dumps([spec["tool"].model_dump(exclude_none=True) for spec in mcp_server.tools().values()])
        assert len(payload) < 200_000, f"tools/list is {len(payload)} bytes"


class TestTransportEdges:
    HEADERS = {"Accept": "application/json, text/event-stream"}

    def test_get_without_event_stream_accept_is_rejected(self, client):
        assert client.get("/mcp", headers={"Accept": "application/json"}).status_code == 406

    def test_wrong_accept_header_is_a_client_error(self, client):
        body = {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}
        assert client.post("/mcp", json=body, headers={"Accept": "text/plain"}).status_code == 406

    def test_unknown_tool_is_flagged_not_raised(self, client):
        body = {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                "params": {"name": "no_such_tool", "arguments": {}}}
        result = client.post("/mcp", json=body, headers=self.HEADERS).json()["result"]
        assert result["isError"] is True
        assert "Unknown tool" in result["content"][0]["text"]

    def test_pdf_over_http_is_an_embedded_resource(self, client, flip_payload):
        body = {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                "params": {"name": "report_flip_pdf", "arguments": {"address": "2 Shared Form Ave", "body": flip_payload}}}
        result = client.post("/mcp", json=body, headers=self.HEADERS).json()["result"]
        assert not result.get("isError")
        assert [c["type"] for c in result["content"]] == ["text", "resource"]
        resource = result["content"][1]["resource"]
        assert resource["mimeType"] == "application/pdf"
        assert base64.b64decode(resource["blob"]).startswith(b"%PDF")


class TestSecretMount:
    def test_mount_registers_only_the_secret_path(self, monkeypatch):
        monkeypatch.setenv("MCP_PATH_SECRET", "s3cret")
        saved = (mcp_server._app, mcp_server._tools)
        try:
            scratch = FastAPI()
            assert mcp_server.mount(scratch) == "/mcp/s3cret"
            assert [r.path for r in scratch.routes if r.path.startswith("/mcp")] == ["/mcp/s3cret"]
        finally:
            mcp_server._app, mcp_server._tools = saved


class TestConcurrency:
    def test_parallel_calls_do_not_cross_talk(self, client, brrrr_payload):
        low_rent = {**brrrr_payload, "rent": 1000}

        async def run():
            calls = [mcp_server.call_tool("analyze_brrr", {"body": p}) for p in [brrrr_payload, low_rent] * 5]
            return await asyncio.gather(*calls)

        results = [json.loads(blocks[0].text)["cash_flow"] for blocks in asyncio.run(run())]
        assert results[0::2] == [results[0]] * 5
        assert results[1::2] == [results[1]] * 5
        assert results[1] < results[0]
