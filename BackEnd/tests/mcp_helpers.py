"""Shared helpers for the MCP server tests (test_mcp*.py)."""

from __future__ import annotations

import asyncio
import json

import mcp_server


def call(name: str, **arguments):
    """Call a tool in-process and return its content blocks."""
    return asyncio.run(mcp_server.call_tool(name, arguments))


def call_json(name: str, **arguments):
    """Call a tool whose only content block is JSON text; return it parsed."""
    blocks = call(name, **arguments)
    assert len(blocks) == 1 and blocks[0].type == "text", blocks
    return json.loads(blocks[0].text)
