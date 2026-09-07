"""Phase 0 MCP hardening: the endpoint refuses to start unprotected in
production, the access log never carries the path secret, and in-process tool
calls present the shared app key so the routers' gate applies to them too."""

from __future__ import annotations

import logging

import pytest
from fastapi import FastAPI

import mcp_server
from BL.common.logging_redact import MCPPathRedactFilter, redact_mcp_path
from tests.mcp_helpers import call as _call, call_json as _call_json


class TestSecretPolicy:
    def test_production_without_a_secret_refuses_to_mount(self, monkeypatch):
        monkeypatch.delenv("MCP_PATH_SECRET", raising=False)
        monkeypatch.setenv("APP_ENV", "production")
        saved = (mcp_server._app, mcp_server._tools)
        try:
            with pytest.raises(RuntimeError, match="MCP_PATH_SECRET is not set"):
                mcp_server.mount(FastAPI())
        finally:
            mcp_server._app, mcp_server._tools = saved

    def test_render_counts_as_production(self, monkeypatch):
        monkeypatch.delenv("MCP_PATH_SECRET", raising=False)
        monkeypatch.delenv("APP_ENV", raising=False)
        monkeypatch.setenv("RENDER", "true")
        with pytest.raises(RuntimeError):
            mcp_server.check_secret_policy("/mcp")

    def test_development_mounts_unprotected_with_a_warning(self, monkeypatch, caplog):
        monkeypatch.delenv("MCP_PATH_SECRET", raising=False)
        monkeypatch.delenv("RENDER", raising=False)
        monkeypatch.setenv("APP_ENV", "development")
        saved = (mcp_server._app, mcp_server._tools)
        try:
            with caplog.at_level(logging.WARNING, logger="mcp_server"):
                assert mcp_server.mount(FastAPI()) == "/mcp"
        finally:
            mcp_server._app, mcp_server._tools = saved
        assert any("served unprotected" in r.message for r in caplog.records)

    def test_a_short_secret_warns(self, caplog):
        with caplog.at_level(logging.WARNING, logger="mcp_server"):
            mcp_server.check_secret_policy("/mcp/short", production=True)
        assert any("shorter than 32" in r.message for r in caplog.records)

    def test_a_long_secret_is_silent(self, caplog):
        with caplog.at_level(logging.WARNING, logger="mcp_server"):
            mcp_server.check_secret_policy("/mcp/" + "a" * 40, production=True)
        assert not caplog.records


class TestAccessLogRedaction:
    def test_the_secret_segment_is_replaced(self):
        assert redact_mcp_path("/mcp/s3cretvalue") == "/mcp/[redacted]"
        assert redact_mcp_path("/mcp/s3cretvalue?x=1") == "/mcp/[redacted]?x=1"
        assert redact_mcp_path("/mcp") == "/mcp"
        assert redact_mcp_path("/active-deals") == "/active-deals"

    def test_uvicorn_style_records_are_rewritten_in_place(self):
        record = logging.LogRecord("uvicorn.access", logging.INFO, __file__, 1, '%s - "%s %s HTTP/%s" %d', ("1.2.3.4:5", "POST", "/mcp/s3cretvalue", "1.1", 200), None)
        assert MCPPathRedactFilter().filter(record) is True
        assert "s3cretvalue" not in record.getMessage()
        assert "/mcp/[redacted]" in record.getMessage()

    def test_the_filter_is_installed_on_the_access_logger(self):
        assert any(isinstance(f, MCPPathRedactFilter) for f in logging.getLogger("uvicorn.access").filters)


class TestToolsCarryTheAppKey:
    def test_tools_keep_working_when_the_gate_is_enforced(self, client, monkeypatch):
        monkeypatch.setenv("APP_KEY_MODE", "enforce")
        monkeypatch.setenv("APP_KEY", "test-app-key-not-a-secret-0000000")
        assert _call_json("get_active_deals") == []
        assert _call_json("helloworld")["message"]

    def test_without_a_configured_key_the_gate_still_holds(self, client, monkeypatch):
        monkeypatch.setenv("APP_KEY_MODE", "enforce")
        monkeypatch.delenv("APP_KEY", raising=False)
        with pytest.raises(RuntimeError, match="HTTP 401"):
            _call("get_active_deals")
