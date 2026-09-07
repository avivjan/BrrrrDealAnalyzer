"""Nightly behavioural probe for the MCP connector.

Asks Claude, through the Anthropic API with the Big Whales MCP server attached, the
question a regular claude.ai chat once failed on, and checks that it answered *with
the tools*: at least one compact deal tool (portfolio_summary / list_deals /
search_deals / get_deal) must have been called before the answer.

Environment:
  ANTHROPIC_API_KEY   the API key (GitHub Actions secret)
  MCP_PROBE_URL       the connector URL including the secret path segment
  MCP_PROBE_MODEL     optional, default claude-opus-5

Exit code 0 = the tools were used; 1 = Claude answered without them or the call
failed. Prints a one-line verdict for the workflow log; never prints the URL.
"""

from __future__ import annotations

import os
import sys

QUESTION = "What's the best deal we did so far, in your opinion? Use the Big Whales tools to check the real data."
COMPACT_TOOLS = {"portfolio_summary", "list_deals", "search_deals", "get_deal"}
SERVER_NAME = "big-whales"


def tools_used(content) -> list[str]:
    """Names of the MCP tools Claude called, from a response's content blocks.

    Accepts SDK objects (attributes) or plain dicts, so tests can pass canned blocks.
    """
    names = []
    for block in content:
        kind = getattr(block, "type", None) if not isinstance(block, dict) else block.get("type")
        if kind == "mcp_tool_use":
            name = getattr(block, "name", None) if not isinstance(block, dict) else block.get("name")
            if name:
                names.append(name)
    return names


def verdict(names: list[str]) -> tuple[bool, str]:
    used = set(names)
    if used & COMPACT_TOOLS:
        return True, f"OK: answered with {sorted(used & COMPACT_TOOLS)} (all tools: {sorted(used)})"
    if used:
        return False, f"FAIL: used only {sorted(used)}; a compact deal tool was expected first"
    return False, "FAIL: Claude answered without calling any tool"


def ask(url: str, model: str):
    import anthropic  # imported here so the unit tests need no SDK

    client = anthropic.Anthropic()
    with client.beta.messages.stream(
        model=model,
        max_tokens=16000,
        betas=["mcp-client-2025-11-20"],
        mcp_servers=[{"type": "url", "url": url, "name": SERVER_NAME}],
        tools=[{"type": "mcp_toolset", "mcp_server_name": SERVER_NAME}],
        messages=[{"role": "user", "content": QUESTION}],
    ) as stream:
        return stream.get_final_message()


def main() -> int:
    url = os.environ.get("MCP_PROBE_URL", "").strip()
    if not url or not os.environ.get("ANTHROPIC_API_KEY"):
        print("SKIP: MCP_PROBE_URL or ANTHROPIC_API_KEY not set")
        return 0
    model = os.environ.get("MCP_PROBE_MODEL", "claude-opus-5")
    try:
        message = ask(url, model)
    except Exception as exc:  # noqa: BLE001 - one line for the workflow log, no secrets
        print(f"FAIL: API call failed: {type(exc).__name__}: {str(exc)[:300]}")
        return 1
    if message.stop_reason == "refusal":
        print("FAIL: the model refused the request")
        return 1
    ok, reason = verdict(tools_used(message.content))
    text = " ".join(getattr(b, "text", "") for b in message.content if getattr(b, "type", "") == "text")
    print(reason)
    print("answer (first 400 chars):", text[:400].replace("\n", " "))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
