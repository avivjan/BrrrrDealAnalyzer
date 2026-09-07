"""MCP hardening (F-24): tool annotations, the MCP_SCOPES allow-list, and an
audit row per tool call."""

from __future__ import annotations

import asyncio

import pytest
from sqlalchemy import select

import mcp_server
from DAL.data_models.audit.models import AuditLog
from db import SessionLocal
from tests.mcp_helpers import call_json as _call_json


class TestAnnotations:
    def test_get_tools_are_read_only(self):
        for name, spec in mcp_server.tools().items():
            ann = spec["tool"].annotations
            assert ann is not None, name
            assert ann.readOnlyHint is (spec["method"] == "GET"), name
            if ann.readOnlyHint:
                assert ann.destructiveHint is False, name

    @pytest.mark.parametrize("name", ["send_offer", "delete_deal", "delete_bought_deal", "reps_log", "reps_upload_batch", "reps_delete_person", "delete_liquidity_transaction"])
    def test_side_effect_tools_are_destructive(self, name):
        assert mcp_server.tools()[name]["tool"].annotations.destructiveHint is True

    @pytest.mark.parametrize("name", ["send_offer", "get_mercury_balance", "reps_log", "reps_upload_batch"])
    def test_tools_that_leave_the_app_are_open_world(self, name):
        assert mcp_server.tools()[name]["tool"].annotations.openWorldHint is True

    def test_plain_crud_is_not_open_world(self):
        assert mcp_server.tools()["add_active_deal"]["tool"].annotations.openWorldHint is False


class TestScopes:
    def test_default_exposes_every_tool(self, monkeypatch):
        monkeypatch.delenv("MCP_SCOPES", raising=False)
        listed = asyncio.run(mcp_server.list_tools())
        assert len(listed) == len(mcp_server.tools())

    def test_a_scope_list_hides_and_refuses_the_rest(self, client, monkeypatch):
        monkeypatch.setenv("MCP_SCOPES", "helloworld, get_active_deals")
        listed = {t.name for t in asyncio.run(mcp_server.list_tools())}
        assert listed == {"helloworld", "get_active_deals"}
        assert _call_json("helloworld")["message"]
        with pytest.raises(ValueError, match="Unknown tool"):
            asyncio.run(mcp_server.call_tool("send_offer", {"body": {}}))


class TestAudit:
    def test_every_tool_call_leaves_a_row(self, client):
        _call_json("helloworld")
        with SessionLocal() as s:
            rows = s.execute(select(AuditLog).where(AuditLog.event == "mcp_tool_call")).scalars().all()
        assert [r.detail for r in rows] == [{"tool": "helloworld", "status": 200}]
