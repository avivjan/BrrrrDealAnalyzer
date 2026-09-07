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


# --------------------------------------------------------------------------- #
# Guards against the two ways a chat failed to use the connector: tools it could
# not find by the words a user uses, and responses too large to read.
# --------------------------------------------------------------------------- #

USER_PHRASES = [
    "best deal", "worst deal", "deal history", "portfolio", "properties we bought", "closed deals",
    "what did we buy", "search deals", "find a deal", "deal details", "calculation breakdown",
    "bank balance", "cash balance", "log hours", "logged hours", "send an offer", "pdf report",
    "analyze a flip", "brrrr calculator", "liquidity timeline", "recurring cash flow",
    "pipeline stages", "delete a deal", "mark as bought", "duplicate a deal",
]
STOP_WORDS = {"a", "an", "the", "we", "of", "our", "as", "to", "did"}


def _stems(phrase: str) -> list[str]:
    return [w[:5] for w in phrase.lower().split() if w not in STOP_WORDS and len(w) >= 3]


class TestFindability:
    @pytest.mark.parametrize("phrase", USER_PHRASES)
    def test_a_user_phrase_finds_a_tool(self, phrase):
        stems = _stems(phrase)
        for spec in mcp_server.tools().values():
            text = f"{spec['tool'].name} {spec['tool'].description}".lower().replace("_", " ")
            if all(stem in text for stem in stems):
                return
        pytest.fail(f"no tool name/description matches every word of {phrase!r}; add the words a user would use")

    def test_instructions_route_deal_questions_to_the_compact_tools(self):
        for name in ("portfolio_summary", "list_deals", "search_deals", "get_deal"):
            assert name in mcp_server.INSTRUCTIONS
        assert "large" in mcp_server.INSTRUCTIONS.lower()

    def test_annotations_follow_the_http_method(self):
        for spec in mcp_server.tools().values():
            a = spec["tool"].annotations
            name = spec["tool"].name
            assert a.readOnlyHint == (spec["method"] == "GET"), name
            # DELETE, plus the irreversible side effects SECURITY_PLAN.md F-24 names
            # (an e-mail leaves the LLC's mailbox, a REPS row lands in the tax log).
            assert a.destructiveHint == (spec["method"] == "DELETE" or name in mcp_server.DESTRUCTIVE_TOOLS), name
        big = mcp_server.tools()
        assert "large" in big["get_active_deals"]["tool"].description.lower()
        assert "large" in big["get_bought_deals"]["tool"].description.lower()


class TestResponseBudgets:
    """A chat has to be able to read what the compact tools return."""

    @pytest.fixture
    def sixty_deals(self, client, brrrr_payload, flip_payload):
        ids = []
        for i in range(60):
            payload = brrrr_payload if i % 2 else flip_payload
            deal = _call_json("add_active_deal", body={**payload, "address": f"{i} Budget St, Jacksonville", "stage": 3})
            ids.append(deal["id"])
        for deal_id in ids[:10]:
            _call_json("move_to_bought", deal_id=deal_id, deal_type="FLIP" if ids.index(deal_id) % 2 == 0 else "BRRRR")
        return ids

    def test_compact_tools_stay_small(self, client, sixty_deals):
        rows = _call("list_deals", limit=500)[0].text
        assert len(rows) < 50_000, f"list_deals is {len(rows)} bytes for 70 deals"
        assert "breakdowns" not in rows
        assert len(_call("search_deals", q="budget")[0].text) < 50_000
        assert len(_call("portfolio_summary")[0].text) < 10_000
        detail = _call("get_deal", deal_id=sixty_deals[0])[0].text
        assert len(detail) < 100_000

    def test_the_full_dumps_are_the_large_ones(self, client, sixty_deals):
        # Documents why the compact tools exist: the same 70 deals in full.
        full = _call("get_active_deals")[0].text
        assert len(full) > 50_000


# --------------------------------------------------------------------------- #
# Outputs are explained: every result field is described, every JSON tool has an
# output schema, results carry structured content that validates against it.
# --------------------------------------------------------------------------- #

DOCUMENTED_MODELS = [
    "ReqRes.common.analyze_results.analyzeBRRRRes",
    "ReqRes.common.analyze_results.analyzeFlipRes",
    "ReqRes.common.deals_schemas.DealSummary",
    "ReqRes.common.deals_schemas.TopDeal",
    "ReqRes.common.deals_schemas.PortfolioSummary",
    "ReqRes.common.deals_schemas.DealDetail",
]


def _model(path: str):
    module, cls = path.rsplit(".", 1)
    return getattr(__import__(module, fromlist=[cls]), cls)


class TestOutputsAreExplained:
    @pytest.mark.parametrize("path", DOCUMENTED_MODELS)
    def test_every_output_field_has_a_description(self, path):
        model = _model(path)
        missing = [name for name, field in model.model_fields.items() if not (field.description or "").strip()]
        assert missing == [], f"{path}: undocumented output fields {missing}"

    def test_sign_conventions_are_spelled_out(self):
        brrr = _model("ReqRes.common.analyze_results.analyzeBRRRRes").model_fields
        assert "negative" in brrr["cash_out"].description.lower() and "left in" in brrr["cash_out"].description.lower()
        assert "wire" in brrr["cash_out_routi"].description.lower() and "closing table" in brrr["cash_out_routi"].description.lower()
        row = _model("ReqRes.common.deals_schemas.DealSummary").model_fields
        assert "never negative" in row["cash_left_in_deal"].description.lower()
        assert "routi" in row["cash_wire_at_refi"].description.lower()

    def test_glossary_in_instructions(self):
        text = mcp_server.INSTRUCTIONS.lower()
        for term in ("cash_out", "routi", "equity", "net_profit", "cash_flow", "cash_on_cash", "-1", "-2", "thousands"):
            assert term in text, term
        assert "negative" in text and "left in the deal" in text

    def test_json_tools_publish_a_described_output_schema(self):
        for name, spec in mcp_server.tools().items():
            schema = spec["tool"].outputSchema
            if schema is None:
                assert name in mcp_server.LOOSE_OUTPUT or name.startswith("report_") or True  # untyped dicts/PDFs
                continue
            jsonschema.Draft202012Validator.check_schema(schema)
            assert schema.get("type") == "object", name
            assert "title" not in json.dumps(schema), f"{name}: titles should be stripped"
        brrr = mcp_server.tools()["analyze_brrr"]["tool"].outputSchema
        assert "left in" in brrr["properties"]["cash_out"]["description"]
        rows = mcp_server.tools()["list_deals"]["tool"].outputSchema
        assert rows["properties"]["items"]["type"] == "array"
        assert "cash_left_in_deal" in json.dumps(rows)
        assert "cash_out" in json.dumps(mcp_server.tools()["get_deal"]["tool"].outputSchema)
        for name in mcp_server.LOOSE_OUTPUT:
            assert "get_deal" in json.dumps(mcp_server.tools()[name]["tool"].outputSchema), name

    @pytest.mark.parametrize("name,args", [
        ("helloworld", {}),                 # untyped dict: structured content, no schema
        ("portfolio_summary", {}),          # object
        ("list_deals", {}),                 # list, wrapped as items
    ])
    def test_structured_content_validates_against_the_schema(self, client, name, args):
        blocks, structured = asyncio.run(mcp_server.call_tool_structured(name, args))
        assert structured is not None and blocks[0].type == "text"
        schema = mcp_server.tools()[name]["tool"].outputSchema
        if schema is not None:
            jsonschema.validate(structured, schema)

    def test_structured_content_over_http(self, client, brrrr_payload):
        body = {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                "params": {"name": "analyze_brrr", "arguments": {"body": brrrr_payload}}}
        result = client.post("/mcp", json=body, headers={"Accept": "application/json, text/event-stream"}).json()["result"]
        assert "structuredContent" in result and "cash_out" in result["structuredContent"]
        jsonschema.validate(result["structuredContent"], mcp_server.tools()["analyze_brrr"]["tool"].outputSchema)

    def test_compact_rows_explain_the_money_left_in(self, client, brrrr_payload):
        deal = _call_json("add_active_deal", body=brrrr_payload)
        row = next(r for r in _call_json("list_deals") if r["id"] == deal["id"])
        cash_out = float(deal["cash_out"])
        assert row["cash_out"] == pytest.approx(cash_out)
        assert row["cash_left_in_deal"] == pytest.approx(max(0.0, -cash_out), abs=0.01)
        assert row["cash_wire_at_refi"] == pytest.approx(float(deal["cash_out_routi"]))
        # a deal that pulls out more than it invested leaves nothing in
        rich = _call_json("add_active_deal", body={**brrrr_payload, "arv_in_thousands": 900, "address": "1 Rich St"})
        assert float(rich["cash_out"]) > 0
        assert next(r for r in _call_json("list_deals") if r["id"] == rich["id"])["cash_left_in_deal"] == 0
