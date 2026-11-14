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


class TestConstructionAccountTools:
    """tasks/todo/ConstructionAccountPerRehab.md: Claude reads a rehab's construction account and corrects its numbers,
    and never moves money between bank accounts."""

    READ_TOOLS = {"list_liquidity_construction_accounts", "list_liquidity_construction_account_transactions",
                  "preview_liquidity_construction_account_switch", "get_liquidity_construction_accounts_last_change",
                  "list_liquidity_construction_account_rehab_summaries"}
    WRITE_TOOLS_ON_THE_APPS_OWN_DATA = {
        "refresh_liquidity_construction_accounts", "save_liquidity_construction_account_link",
        "save_liquidity_construction_account_rehab_figures",
        "add_liquidity_construction_account_manual_adjustment", "update_liquidity_construction_account_manual_adjustment",
        "set_liquidity_construction_account_transaction_override", "mark_liquidity_construction_account_ready_for_close_out",
        "mark_liquidity_construction_account_closed_out", "reopen_liquidity_construction_account",
        "send_liquidity_construction_account_rehab_summary_again",
    }
    DESTRUCTIVE_TOOLS = {"unlink_liquidity_construction_account", "switch_liquidity_construction_account",
                         "delete_liquidity_construction_account_manual_adjustment",
                         "clear_liquidity_construction_account_transaction_override"}

    def test_every_construction_account_tool_is_listed_with_its_annotations(self):
        tools = mcp_server.tools()
        construction_account_tools = {name for name in tools if "construction_account" in name}
        assert "get_liquidity_mercury_connection_status" in tools and tools["get_liquidity_mercury_connection_status"]["tool"].annotations.readOnlyHint
        assert construction_account_tools == self.READ_TOOLS | self.WRITE_TOOLS_ON_THE_APPS_OWN_DATA | self.DESTRUCTIVE_TOOLS
        for name in self.READ_TOOLS:
            assert tools[name]["tool"].annotations.readOnlyHint is True, name
        for name in self.WRITE_TOOLS_ON_THE_APPS_OWN_DATA:
            annotations = tools[name]["tool"].annotations
            assert (annotations.readOnlyHint, annotations.destructiveHint) == (False, False), name
        for name in self.DESTRUCTIVE_TOOLS:
            assert tools[name]["tool"].annotations.destructiveHint is True, name

    def test_the_tools_that_e_mail_the_rehab_summary_are_open_world(self):
        tools = mcp_server.tools()
        for name in ("mark_liquidity_construction_account_closed_out", "send_liquidity_construction_account_rehab_summary_again"):
            assert tools[name]["tool"].annotations.openWorldHint is True, name

    def test_the_tools_that_read_the_bank_are_open_world(self):
        tools = mcp_server.tools()
        for name in ("refresh_liquidity_construction_accounts", "list_liquidity_construction_account_transactions",
                     "preview_liquidity_construction_account_switch"):
            assert tools[name]["tool"].annotations.openWorldHint is True, name

    def test_no_tool_moves_money_between_bank_accounts(self):
        assert not [name for name in mcp_server.tools() if "deposit" in name or "steal" in name or "transfer" in name]
        assert "No tool moves money between bank accounts" in mcp_server.INSTRUCTIONS


    def test_every_write_takes_preview_only_and_points_to_the_full_status_schema(self):
        tools = mcp_server.tools()
        for name in mcp_server.CONSTRUCTION_ACCOUNT_WRITE_TOOLS:
            tool = tools[name]["tool"]
            assert "preview_only" in tool.inputSchema["properties"], name
            assert "list_liquidity_construction_accounts" in tool.outputSchema["description"], name
        assert "preview_only=true first" in mcp_server.INSTRUCTIONS
