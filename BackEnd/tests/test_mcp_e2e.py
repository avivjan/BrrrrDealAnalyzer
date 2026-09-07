"""End to end: a real `uvicorn` process serving the app with MCP_PATH_SECRET set,
driven by the official MCP client over Streamable HTTP. This is exactly what a
claude.ai connector or Claude Code does, minus the internet.

The server is a subprocess so the transport, the lifespan (session manager)
and the secret path are the real ones, not the in-process shortcuts the other
MCP tests take. It inherits DATABASE_URL from the harness, which conftest.py
has already pointed at the throwaway test PostgreSQL.
"""

from __future__ import annotations

import asyncio
import base64
import json
import os
import pathlib
import socket
import subprocess
import sys
import time

import httpx
import pytest
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

import mcp_server

BACKEND_DIR = pathlib.Path(__file__).resolve().parents[1]
SECRET = "e2e-secret"
ACCEPT = {"Accept": "application/json, text/event-stream"}


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def base_url():
    port = _free_port()
    env = {**os.environ, "MCP_PATH_SECRET": SECRET, "PYTHONDONTWRITEBYTECODE": "1"}
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", str(port), "--log-level", "warning"],
        cwd=BACKEND_DIR, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
    )
    url = f"http://127.0.0.1:{port}"
    deadline = time.monotonic() + 90
    try:
        while True:
            if proc.poll() is not None:
                pytest.fail(f"uvicorn exited early:\n{proc.stdout.read()}")
            try:
                if httpx.get(f"{url}/helloworld", timeout=2).status_code == 200:
                    break
            except httpx.HTTPError:
                pass
            if time.monotonic() > deadline:
                proc.kill()
                pytest.fail(f"uvicorn did not come up in time:\n{proc.stdout.read()}")
            time.sleep(0.25)
        yield url
    finally:
        proc.terminate()
        try:
            proc.wait(10)
        except subprocess.TimeoutExpired:
            proc.kill()


def _run(base_url: str, fn):
    """Open a real client session against the secret URL and run `fn(session, init_result)`."""

    async def go():
        async with streamablehttp_client(f"{base_url}/mcp/{SECRET}") as (read, write, _):
            async with ClientSession(read, write) as session:
                init = await session.initialize()
                return await fn(session, init)

    return asyncio.run(go())


def _json(result):
    assert not result.isError, result.content[0].text
    return json.loads(result.content[0].text)


def test_initialize_and_list_tools(base_url):
    async def go(session, init):
        assert init.serverInfo.name == "brrrr-deal-analyzer"
        assert "THOUSANDS" in (init.instructions or "")
        tools = await session.list_tools()
        assert {t.name for t in tools.tools} == set(mcp_server.tools())
        assert all(t.description for t in tools.tools)

    _run(base_url, go)


def test_deal_round_trip_through_a_real_server(base_url, brrrr_payload):
    async def go(session, _):
        hello = _json(await session.call_tool("helloworld", {}))
        assert hello == {"message": "Hello, World!"}

        analysis = _json(await session.call_tool("analyze_brrr", {"body": brrrr_payload}))
        assert "cash_flow" in analysis and "breakdowns" in analysis

        created = _json(await session.call_tool("add_active_deal", {"body": brrrr_payload}))
        listed = _json(await session.call_tool("get_active_deals", {}))
        assert created["id"] in [d["id"] for d in listed]

        pdf = await session.call_tool("report_brrr_pdf", {"address": created["address"], "body": brrrr_payload})
        assert pdf.content[1].type == "resource"
        assert base64.b64decode(pdf.content[1].resource.blob).startswith(b"%PDF")

        bad = await session.call_tool("delete_deal", {"deal_id": created["id"], "deal_type": "FLIP"})
        assert bad.isError and "HTTP 404" in bad.content[0].text

        deleted = _json(await session.call_tool("delete_deal", {"deal_id": created["id"], "deal_type": "BRRRR"}))
        assert deleted == {"message": "Deal deleted"}

    _run(base_url, go)


def test_secret_path_is_enforced(base_url):
    probe = {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}
    assert httpx.post(f"{base_url}/mcp", json=probe, headers=ACCEPT).status_code == 404
    assert httpx.post(f"{base_url}/mcp/wrong-secret", json=probe, headers=ACCEPT).status_code == 404
    ok = httpx.post(f"{base_url}/mcp/{SECRET}", json=probe, headers=ACCEPT)
    assert ok.status_code == 200
    assert len(ok.json()["result"]["tools"]) == len(mcp_server.tools())
