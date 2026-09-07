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

import json
import os
import sys

QUESTION = ("What's the best deal we did so far, in your opinion, and how much of our own money is still left "
            "in that deal? Use the Big Whales tools to check the real data and quote the exact dollar amounts.")
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


def number_forms(amount: float) -> list[str]:
    """The ways a dollar amount is usually written: 26587, 26,587, $26,587, 26.6k, 27k."""
    whole = int(round(amount))
    forms = {str(whole), f"{whole:,}", f"${whole:,}", f"{amount / 1000:.1f}k", f"{round(amount / 1000)}k"}
    return sorted(forms)


def mentions_amount(text: str, amount: float) -> bool:
    """True if the answer quotes the amount in any usual form (case-insensitive, 'K' or 'k')."""
    haystack = text.lower().replace("\u2009", "").replace(" ", "")
    return any(form.lower() in haystack for form in number_forms(amount))


def left_in_by_deal(mcp_url: str) -> dict[str, float]:
    """cash_left_in_deal per bought deal (address -> dollars, only deals with money left in),
    from the site's own compact endpoint on the same host as the connector."""
    import urllib.parse
    import urllib.request

    parts = urllib.parse.urlsplit(mcp_url)
    with urllib.request.urlopen(f"{parts.scheme}://{parts.netloc}/deals?board=bought&limit=500", timeout=60) as resp:
        rows = json.load(resp)
    return {r["address"]: float(r["cash_left_in_deal"]) for r in rows
            if r.get("cash_left_in_deal") and float(r["cash_left_in_deal"]) > 0}


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
    if ok:
        try:
            amounts = left_in_by_deal(url)
        except Exception as exc:  # noqa: BLE001
            print(f"WARN: could not fetch the money-left-in amounts: {type(exc).__name__}")
            amounts = {}
        if amounts:
            hit = next((a for a, v in amounts.items() if mentions_amount(text, v)), None)
            if hit:
                print(f"OK: the answer quotes the money left in {hit} ({amounts[hit]:,.0f})")
            else:
                print("FAIL: the answer quotes none of the money-left-in amounts of the bought deals "
                      f"({', '.join(f'{v:,.0f}' for v in amounts.values())}); it probably misread cash_out")
                ok = False
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
