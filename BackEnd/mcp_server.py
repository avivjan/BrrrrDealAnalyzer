"""MCP server: every HTTP endpoint of this app, exposed as one MCP tool.

Claude (claude.ai custom connector, Claude Code, any MCP client) talks to the
website through this. Nothing is duplicated: the tool list is derived from the
app's own OpenAPI document, and a tool call performs the real HTTP request
against this same app in-process (``httpx.ASGITransport``), so validation,
CRUD, PDF rendering, e-mail, Mercury and REPS behave exactly as for the site.

Transport: stateless Streamable HTTP (JSON responses), served by ``mount()`` at
``/mcp/<MCP_PATH_SECRET>`` -- or plain ``/mcp`` when the variable is unset, which
is meant for local development and tests only. The route is a plain Starlette
route, so ``app.openapi()`` is untouched and the regression goldens still hold.

Adding an endpoint to a router makes it a tool automatically; give it a line in
``DESCRIPTIONS`` so Claude knows what it is for (tests enforce this).
"""

from __future__ import annotations

import base64
import json
import logging
import os
from urllib.parse import quote
from contextlib import asynccontextmanager
from typing import Any

import httpx
import mcp.types as t
from fastapi import FastAPI
from fastapi.routing import APIRoute
from mcp.server.lowlevel import Server
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager

logger = logging.getLogger(__name__)

INSTRUCTIONS = (
    "Tools for the Big Whales real-estate site (BrrrrDealAnalyzer): the deal portfolio "
    "(properties analysed, under contract, bought, refinanced or sold), the BRRRR and flip "
    "calculators, PDF reports, the liquidity (cash) timeline, the Mercury bank balance, the "
    "REPS hours log and the send-offer e-mail. "
    "START HERE for any question about deals, the portfolio, deal history, the best or worst "
    "deal, or a specific property: portfolio_summary (headline numbers and top deals), "
    "list_deals (compact rows, filters) and search_deals (words in address, notes, task, "
    "niche, contact); then get_deal for one deal's full inputs, metrics and calculation "
    "breakdown. get_active_deals and get_bought_deals return every deal with its full "
    "breakdown and are very large; use them only when you truly need everything. "
    "Conventions: every field whose name ends in _in_thousands or _k, or whose alias is "
    "purchasePrice, rehabCost, closingCostsBuy, closingCostsRefi, cashReserve, salePrice, "
    "sellingClosingCosts or arv_in_thousands, is in THOUSANDS of dollars (250 = $250k); "
    "rent, taxes, insurance, HOA and utilities are plain dollars; rates and fees are "
    "percentages (75 = 75%). Deal bodies use the camelCase aliases shown in each schema. "
    "Active deals: stage 1 New, 2 Working, 3 Brought, 4 Keep in Mind, 5 Dead; section "
    "1 Wholesale, 2 Market, 3 Off Market. Where a tool takes deal_type it must match the "
    "deal ('BRRRR' or 'FLIP'). Update tools replace the whole record: read it first, edit, "
    "send it back. "
    "GLOSSARY (every output field also carries its own description in the tool's output "
    "schema): cash_out = total cash received from a BRRRR deal (the refinance wire) minus total "
    "cash put in; NEGATIVE cash_out means that much of your own money is still left in the deal "
    "(compact rows also give cash_left_in_deal, never negative). cash_out_routi / "
    "cash_wire_at_refi ('routi') = the cash wire received at the refinance closing table, "
    "before subtracting what was invested. equity = ARV minus the new loan. net_profit = equity "
    "plus cash out. cash_flow = monthly, after the refinance. cash_on_cash and roi are percents; "
    "-1 means infinite (no cash left in the deal), -2 means not applicable. Fields ending in "
    "_in_thousands or _k are thousands of dollars; every other money field is plain dollars."
)

# One line per tool, keyed by tool name (the route's function name without a
# trailing `_route`). tests/test_mcp.py fails if an endpoint has no entry.
DESCRIPTIONS: dict[str, str] = {
    # --- Analyze (pure calculation, nothing saved) ---
    "analyze_brrr": (
        "Run the BRRRR calculator without saving anything. Returns monthly cash flow, DSCR, "
        "cash out at refi, cash-on-cash, ROI, equity, net profit, total cash needed (and with "
        "buffer), warning messages and a per-metric formula breakdown."
    ),
    "analyze_flip": (
        "Run the fix-and-flip calculator without saving anything. Returns net profit, ROI, "
        "annualized ROI, total cash needed (and with buffer), holding costs, hard-money "
        "interest, messages and a per-metric formula breakdown."
    ),
    # --- PDF reports ---
    "report_brrr_pdf": (
        "Render the Big Whales BRRRR deal report as a PDF (same body as analyze_brrr; put the "
        "property address in `address`). The PDF comes back as an embedded resource."
    ),
    "report_flip_pdf": (
        "Render the Big Whales FLIP deal report as a PDF (same body as analyze_flip; put the "
        "property address in `address`). The PDF comes back as an embedded resource."
    ),
    # --- My Deals (active pipeline) ---
    "get_active_deals": (
        "Every deal on the My Deals board (deals being analysed or worked, not yet bought): all "
        "inputs, notes, comps, metrics AND the full calculation breakdown of each. Very large; "
        "for questions about deals, history, the portfolio or a property use portfolio_summary, "
        "list_deals, search_deals or get_deal instead."
    ),
    "add_active_deal": (
        "Create a deal on the My Deals board (what 'Analyze & Save' does on the site). "
        "body.deal_type is 'BRRRR' or 'FLIP'; address, section and stage are required."
    ),
    "update_deal": (
        "Replace an active deal (edit, autosave or stage move on the site). Send the full "
        "deal as returned by get_active_deals with your changes; deal_id is its UUID."
    ),
    "delete_deal": "Delete an active deal. deal_type ('BRRRR'/'FLIP') must match the deal.",
    "duplicate_deal": "Copy an active deal into a new deal with the same inputs and a new id.",
    # --- Compact cross-board views (start here for deal questions) ---
    "list_deals": (
        "Compact list of deals across both boards: the portfolio of properties we analysed, "
        "worked, bought, refinanced or sold, one small row each (address, stage, purchase, "
        "rehab, ARV or sale price, rent, cash flow, cash-on-cash, ROI, equity, net profit, "
        "cash needed, cash out). Filter by board (active/bought), deal_type, stage, or words "
        "with q. Deal history and 'what did we buy' questions start here."
    ),
    "search_deals": (
        "Find deals by words: search the address, notes, task, niche and contact of every deal "
        "on both boards (e.g. 'Jacksonville', 'duplex', a street name, a person). Returns the "
        "same compact rows as list_deals."
    ),
    "portfolio_summary": (
        "Portfolio overview in one small call: how many deals are active and bought, by type "
        "and stage; totals of equity, monthly cash flow, cash invested and net profit across "
        "the properties we bought; and the top deals by equity, cash flow and cash-on-cash. "
        "The right tool for 'best deal', 'worst deal', 'how are we doing' and history "
        "questions; follow up with get_deal for details."
    ),
    "get_deal": (
        "One deal in full by id, whichever board it is on: every input, notes, comps, all "
        "metrics and the step-by-step calculation breakdown (formulas). Use after list_deals, "
        "search_deals or portfolio_summary when the details of a specific property are wanted."
    ),
    # --- Bought Deals ---
    "get_bought_deals": (
        "Every property we bought (closed deals on the Bought Deals board) with the purchase "
        "pipeline stage, checklist, metrics AND the full calculation breakdown of each. Large; "
        "for 'which deals did we buy', 'best deal', history or portfolio questions prefer "
        "portfolio_summary or list_deals with board=bought."
    ),
    "add_bought_deal": "Create a bought deal directly (normally use move_to_bought instead).",
    "update_bought_deal": (
        "Replace a bought deal. Also how checklist items are ticked (completedSubstages) and "
        "how a deal advances to the next boughtStage. Send the full record back."
    ),
    "delete_bought_deal": "Delete a bought deal. deal_type must match the deal.",
    "move_to_bought": (
        "Mark a deal as bought: copy an active deal onto the Bought Deals board (the site "
        "allows this for stage 3 'Brought' deals). The active deal is kept. deal_type must "
        "match the deal."
    ),
    # --- Dashboard: Send Market Offer ---
    "send_offer": (
        "Send a purchase-offer e-mail to a listing agent (the dashboard's 'Send Market Offer' "
        "form). This sends a real e-mail; purchase_price is in plain dollars."
    ),
    # --- Liquidity timeline ---
    "list_liquidity_transactions": (
        "List one-off cash events on the Liquidity timeline (amount_k in thousands, positive "
        "= inflow, negative = outflow)."
    ),
    "create_liquidity_transaction": "Add a one-off cash event to the Liquidity timeline.",
    "update_liquidity_transaction": "Change a one-off cash event (partial update).",
    "delete_liquidity_transaction": "Remove a one-off cash event.",
    "list_liquidity_recurring": (
        "List recurring cash-flow rules (frequency daily/weekly/biweekly/monthly/quarterly/"
        "yearly, interval, and either end_date or occurrences)."
    ),
    "create_liquidity_recurring": "Add a recurring cash-flow rule (amount_k must not be 0).",
    "update_liquidity_recurring": "Change a recurring rule (partial update; re-projects all its events).",
    "delete_liquidity_recurring": "Remove a recurring rule.",
    "get_liquidity_settings": "Read the Liquidity settings: opening balance (k), its date and the reserve (k).",
    "update_liquidity_settings": "Change the opening balance, its date and/or the reserve.",
    "get_mercury_balance": (
        "Live bank balance: the total cash across the Mercury bank accounts in $k, used to "
        "re-anchor the liquidity timeline to today (503 if MERCURY_API_TOKEN is not configured "
        "on the server)."
    ),
    # --- Bought Deals pipeline templates ---
    "list_pipeline_templates": (
        "Get the editable stage / sub-stage checklist templates of the Bought Deals board for "
        "both deal types."
    ),
    "update_pipeline_template": (
        "Replace the whole stage tree of the BRRRR or FLIP pipeline (Edit Pipeline on the "
        "site). Check pipeline_template_stats first before removing a populated stage."
    ),
    "pipeline_template_stats": "Count bought deals per pipeline stage and sub-stage for one deal type.",
    # --- Health ---
    "helloworld": "Health check; the site's connection indicator pings this.",
    # --- REPS tracker ---
    "reps_log": (
        "Log hours: record a REPS (Real Estate Professional Status) activity to the user's "
        "Google Sheet: user (Aviv2026 or Yarden2026), description of at least 20 characters, "
        "start_time and end_time as ISO datetimes, optional property, category, evidence items "
        "and people."
    ),
    "reps_entries": "All logged REPS hours of a user plus year-to-date stats (750 h and 500 h material-participation progress).",
    "reps_upload_batch": (
        "Upload evidence files (base64) into a per-log REPS folder; returns the folder and "
        "file URLs to pass in reps_log evidence_items."
    ),
    "reps_upload": "Upload a single REPS evidence file (legacy; prefer reps_upload_batch).",
    "reps_properties": "Property names for REPS logging: bought-deal addresses first, then saved prospects.",
    "reps_create_prospect": "Save a prospect property name for REPS logging.",
    "reps_delete_prospect": "Delete a saved prospect property.",
    "reps_list_people": "List saved people (for people_involved in REPS logs).",
    "reps_create_person": "Add a person (name must be unique) for REPS logs.",
    "reps_update_person": "Update a saved person's name, role or notes.",
    "reps_delete_person": "Delete a saved person.",
    "reps_list_activity_categories": "List REPS activity categories.",
    "reps_create_activity_category": "Add a custom REPS activity category.",
    "reps_delete_activity_category": "Delete a REPS activity category.",
    "reps_config_status": "Whether the REPS Google Sheets / GCS integration is configured on the server.",
}

BODY_ARG = "body"

# Authentication plumbing never becomes a tool: an LLM must not enroll a
# passkey, approve a device or mint a session.
EXCLUDED_PREFIXES = ("/auth", "/devices", "/sessions", "/credentials")

# Tools whose call has a side effect beyond this app's own database, or that
# an LLM should never run without a human confirming: annotated so a client
# can ask first (MCP `ToolAnnotations`). Everything else is plain CRUD on the
# site's own data; GET tools are read-only.
OPEN_WORLD_TOOLS = {"send_offer", "get_mercury_balance", "reps_log", "reps_upload", "reps_upload_batch"}
DESTRUCTIVE_PREFIXES = ("delete_", "reps_delete_")
DESTRUCTIVE_TOOLS = {"send_offer", "reps_log", "reps_upload", "reps_upload_batch", "update_pipeline_template"}


def tool_annotations(name: str, method: str) -> t.ToolAnnotations:
    read_only = method.upper() == "GET"
    destructive = name in DESTRUCTIVE_TOOLS or name.startswith(DESTRUCTIVE_PREFIXES)
    return t.ToolAnnotations(
        readOnlyHint=read_only,
        destructiveHint=(not read_only) and destructive,
        idempotentHint=read_only or method.upper() in {"PUT", "DELETE"},
        openWorldHint=name in OPEN_WORLD_TOOLS,
    )


def allowed_scopes() -> set[str] | None:
    """`MCP_SCOPES`: comma-separated tool names the connector may see and call.

    Unset or `*` means every tool (the default -- nothing changes for the
    owner). Anything else hides the other tools from `tools/list` and refuses
    them in `tools/call`.
    """

    raw = (os.getenv("MCP_SCOPES") or "*").strip()
    if raw in {"", "*"}:
        return None
    return {name.strip() for name in raw.split(",") if name.strip()}


def tool_allowed(name: str) -> bool:
    scopes = allowed_scopes()
    return scopes is None or name in scopes

server: Server = Server("brrrr-deal-analyzer", instructions=INSTRUCTIONS)

_app: FastAPI | None = None
_session_manager: StreamableHTTPSessionManager | None = None
_tools: dict[str, dict[str, Any]] | None = None


# --------------------------------------------------------------------------- #
# Tool list, derived from the app's routes + OpenAPI document
# --------------------------------------------------------------------------- #

def _tool_name(route: APIRoute) -> str:
    name = route.name
    return name[: -len("_route")] if name.endswith("_route") else name


def _referenced_defs(schema: Any, defs: dict[str, Any]) -> dict[str, Any]:
    """The subset of component schemas that `schema` (transitively) refers to."""
    wanted: dict[str, Any] = {}
    pending = [schema]
    while pending:
        node = pending.pop()
        if isinstance(node, dict):
            ref = node.get("$ref")
            if isinstance(ref, str) and ref.startswith("#/$defs/"):
                key = ref[len("#/$defs/"):]
                if key not in wanted and key in defs:
                    wanted[key] = defs[key]
                    pending.append(defs[key])
            pending.extend(node.values())
        elif isinstance(node, list):
            pending.extend(node)
    return wanted


def _file_field_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "description": "A file to upload.",
        "properties": {
            "filename": {"type": "string"},
            "content_type": {"type": "string"},
            "content_base64": {"type": "string", "description": "File bytes, base64-encoded."},
        },
        "required": ["filename", "content_base64"],
    }


def _is_binary(schema: dict[str, Any]) -> bool:
    # Starlette < 1.0 wrote `format: binary`; newer versions write
    # `contentMediaType: application/octet-stream` for upload fields.
    return schema.get("type") == "string" and (
        schema.get("format") == "binary" or "contentMediaType" in schema
    )


def _api_routes(routes) -> list[APIRoute]:
    """Every `APIRoute`, depth-first.

    FastAPI >= 0.13x keeps an included router as a nested entry in `app.routes`
    instead of flattening its operations, so the walk has to recurse.
    """

    found: list[APIRoute] = []
    for route in routes:
        if isinstance(route, APIRoute):
            found.append(route)
            continue
        # FastAPI's `_IncludedRouter` keeps the router it was built from; the
        # routers here are unprefixed, so the original paths are the served ones.
        inner = getattr(route, "original_router", None) or route
        nested = getattr(inner, "routes", None)
        if nested and nested is not routes:
            found.extend(_api_routes(nested))
    return found


ITEMS = "items"


# Tools that return full deal records. Their output schema is kept loose so tools/list stays
# small; `get_deal` publishes the complete, described schema of a deal record once.
LOOSE_OUTPUT = {
    "get_active_deals", "get_bought_deals", "add_active_deal", "update_deal", "duplicate_deal",
    "move_to_bought", "add_bought_deal", "update_bought_deal",
}
LOOSE_DESCRIPTION = (
    "A full deal record: every input (camelCase aliases, money in thousands), notes, comps, all "
    "metrics and the calculation breakdowns. The complete field-by-field schema, with each "
    "metric's meaning and sign convention, is the output schema of get_deal."
)


def _strip_titles(node: Any) -> Any:
    """Drop pydantic's per-field `title` keys: no information, a fifth of the bytes."""
    if isinstance(node, dict):
        return {k: _strip_titles(v) for k, v in node.items() if k != "title"}
    if isinstance(node, list):
        return [_strip_titles(v) for v in node]
    return node


def _output_schema(name: str, op: dict[str, Any], defs: dict[str, Any]) -> tuple[dict[str, Any] | None, bool]:
    """The tool's outputSchema from the endpoint's 200 JSON response, and whether the
    result has to be wrapped as {"items": [...]} (MCP output schemas must be objects).
    Field descriptions from the response models travel with it. None for non-JSON
    (PDF) responses."""
    responses = op.get("responses") or {}
    content: dict[str, Any] = {}
    for status, spec in sorted(responses.items()):        # first 2xx with a JSON body (200, 201, ...)
        if str(status).startswith("2") and "application/json" in (spec.get("content") or {}):
            content = spec["content"]
            break
    if not content:
        return None, False
    schema = dict(content["application/json"].get("schema") or {})
    if not schema:                                   # no response model (plain dicts, PDFs): unknown shape
        return None, False
    if name in LOOSE_OUTPUT:                         # full deal records: get_deal carries the canonical schema
        loose = {"type": "object", "additionalProperties": True, "description": LOOSE_DESCRIPTION}
        if schema.get("type") == "array":
            return {"type": "object", "properties": {ITEMS: {"type": "array", "items": loose}}, "required": [ITEMS]}, True
        return loose, False
    wrap = False
    if schema.get("type") == "array":
        schema = {"type": "object", "properties": {ITEMS: schema}, "required": [ITEMS]}
        wrap = True
    elif "$ref" in schema and len(schema) == 1:
        schema = dict(defs[schema["$ref"][len("#/$defs/"):]])
    elif "type" not in schema:                      # untyped dict responses, unions
        schema = {"type": "object", **schema}
    used = _referenced_defs(schema, defs)
    if used:
        schema["$defs"] = used
    return _strip_titles(schema), wrap


def _build_tools(app: FastAPI) -> dict[str, dict[str, Any]]:
    spec = json.loads(
        json.dumps(app.openapi()).replace("#/components/schemas/", "#/$defs/")
    )
    defs = spec.get("components", {}).get("schemas", {})
    tools: dict[str, dict[str, Any]] = {}

    for route in _api_routes(app.routes):
        if not route.include_in_schema or route.path.startswith(EXCLUDED_PREFIXES):
            continue
        for method in route.methods:
            op = spec["paths"][route.path][method.lower()]
            props: dict[str, Any] = {}
            required: list[str] = []
            path_params: list[str] = []
            query_params: list[str] = []
            for p in op.get("parameters", []):
                schema = dict(p.get("schema", {}))
                if p.get("description") and "description" not in schema:
                    schema["description"] = p["description"]
                props[p["name"]] = schema
                (path_params if p["in"] == "path" else query_params).append(p["name"])
                if p.get("required"):
                    required.append(p["name"])

            form_fields: list[str] = []
            file_fields: list[str] = []
            has_json_body = False
            content = (op.get("requestBody") or {}).get("content") or {}
            if "multipart/form-data" in content:
                form_schema = content["multipart/form-data"]["schema"]
                if "$ref" in form_schema:
                    form_schema = defs[form_schema["$ref"][len("#/$defs/"):]]
                for fname, fschema in form_schema.get("properties", {}).items():
                    if _is_binary(fschema):
                        file_fields.append(fname)
                        props[fname] = _file_field_schema()
                    elif fschema.get("type") == "array" and _is_binary(fschema.get("items", {})):
                        file_fields.append(fname)
                        props[fname] = {"type": "array", "items": _file_field_schema()}
                    else:
                        form_fields.append(fname)
                        props[fname] = fschema
                required.extend(form_schema.get("required", []))
            elif "application/json" in content:
                has_json_body = True
                props[BODY_ARG] = content["application/json"]["schema"]
                if op["requestBody"].get("required", False):
                    required.append(BODY_ARG)

            input_schema: dict[str, Any] = {"type": "object", "properties": props}
            if required:
                input_schema["required"] = required
            used = _referenced_defs(input_schema, defs)
            if used:
                input_schema["$defs"] = used

            name = _tool_name(route)
            output_schema, wrap_items = _output_schema(name, op, defs)

            tools[name] = {
                "method": method,
                "path": route.path,
                "path_params": path_params,
                "query_params": query_params,
                "form_fields": form_fields,
                "file_fields": file_fields,
                "json_body": has_json_body,
                "wrap_items": wrap_items,
                "tool": t.Tool(
                    name=name,
                    description=DESCRIPTIONS.get(name) or op.get("summary") or name,
                    inputSchema=input_schema,
                    outputSchema=output_schema,
                    annotations=tool_annotations(name, method),
                ),
            }
    return tools


def tools() -> dict[str, dict[str, Any]]:
    global _tools
    if _tools is None:
        if _app is None:
            raise RuntimeError("mcp_server.mount(app) has not been called")
        _tools = _build_tools(_app)
    return _tools


# --------------------------------------------------------------------------- #
# Tool execution: the real HTTP request, in-process
# --------------------------------------------------------------------------- #

def _path_segment(name: str, value: Any) -> str:
    """One URL path segment from a tool argument (an id). httpx normalises
    dot segments before the app sees the path, so `../auth/me` in a deal id
    would escape the tool's route and reach an excluded one; a segment may
    therefore hold no separators at all, and is percent-encoded besides."""
    text = str(value)
    if not text or any(c in text for c in "/\\?#%") or text in {".", ".."}:
        raise ValueError(f"Invalid value for {name}")
    return quote(text, safe="")


async def call_tool(name: str, arguments: dict[str, Any] | None) -> list[t.ContentBlock]:
    """Run a tool; the content blocks only (JSON as text, PDFs as a blob resource)."""
    blocks, _ = await call_tool_structured(name, arguments)
    return blocks


async def call_tool_structured(
    name: str, arguments: dict[str, Any] | None,
) -> tuple[list[t.ContentBlock], dict[str, Any] | None]:
    """Run a tool; the content blocks plus the structured result that matches the tool's
    outputSchema (list responses wrapped as {"items": [...]}), or None for non-JSON."""
    spec = tools().get(name)
    if spec is None or not tool_allowed(name):
        raise ValueError(f"Unknown tool: {name}")
    args = dict(arguments or {})

    missing = [p for p in spec["path_params"] if p not in args]
    if missing:
        raise ValueError(f"Missing required argument(s): {', '.join(missing)}")
    path = spec["path"].format(**{p: _path_segment(p, args[p]) for p in spec["path_params"]})
    # Belt and braces: whatever the segments were, the final path must still be
    # the tool's own route, never one of the excluded auth surfaces.
    if path.startswith(EXCLUDED_PREFIXES) or "/../" in f"{path}/":
        raise ValueError("Invalid path argument")
    params = {q: args[q] for q in spec["query_params"] if args.get(q) is not None}

    request_kwargs: dict[str, Any] = {}
    if spec["json_body"] and BODY_ARG in args:
        request_kwargs["json"] = args[BODY_ARG]
    if spec["form_fields"]:
        request_kwargs["data"] = {
            f: args[f] for f in spec["form_fields"] if args.get(f) is not None
        }
    if spec["file_fields"]:
        files = []
        for f in spec["file_fields"]:
            items = args.get(f) or []
            for item in items if isinstance(items, list) else [items]:
                files.append((
                    f,
                    (
                        item["filename"],
                        base64.b64decode(item["content_base64"]),
                        item.get("content_type") or "application/octet-stream",
                    ),
                ))
        request_kwargs["files"] = files

    # The MCP endpoint is itself protected (path secret today, OAuth in Phase 2),
    # so the in-process request presents the shared app key on the caller's
    # behalf; the routers' `require_app_key` dependency then applies as usual.
    headers = {"X-Requested-With": "mcp"}
    app_key = os.getenv("APP_KEY", "").strip()
    if app_key:
        headers["X-App-Key"] = app_key
    # When passkey sessions are on, the connector acts as its own device: the
    # same `require_session` gate applies to tools. Under MCP_AUTH_MODE=oauth
    # the bearer token IS that device's session (BL.auth.oauth); under the
    # path secret it is the shared connector session (BL.auth.service).
    cookies, user_id = _caller_cookies()

    transport = httpx.ASGITransport(app=_app, raise_app_exceptions=False)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://mcp.internal", headers=headers, cookies=cookies
    ) as client:
        response = await client.request(spec["method"], path, params=params, **request_kwargs)

    _audit_tool_call(name, response.status_code, user_id=user_id)
    if response.status_code >= 400:
        raise RuntimeError(f"HTTP {response.status_code} from {spec['method']} {path}: {response.text}")

    content_type = response.headers.get("content-type", "")
    if content_type.startswith("application/pdf"):
        filename = "report.pdf"
        disposition = response.headers.get("content-disposition", "")
        if 'filename="' in disposition:
            filename = disposition.split('filename="', 1)[1].split('"', 1)[0]
        return [
            t.TextContent(type="text", text=f"PDF generated: {filename} ({len(response.content)} bytes)"),
            t.EmbeddedResource(
                type="resource",
                resource=t.BlobResourceContents(
                    uri=f"file:///{filename}",
                    mimeType="application/pdf",
                    blob=base64.b64encode(response.content).decode("ascii"),
                ),
            ),
        ], None
    if content_type.startswith("application/json"):
        data = response.json()
        structured = {ITEMS: data} if spec["wrap_items"] else (data if isinstance(data, dict) else {"value": data})
        # Lists are serialised compactly (a third fewer bytes for a chat to read); single
        # objects keep the indentation that makes a breakdown readable.
        text = json.dumps(data, separators=(",", ":")) if spec["wrap_items"] else json.dumps(data, indent=2)
        return [t.TextContent(type="text", text=text)], structured
    return [t.TextContent(type="text", text=response.text)], None


def _caller_cookies() -> tuple[dict[str, str], Any]:
    """The session cookie the in-process request carries, and whose it is."""
    from mcp.server.auth.middleware.auth_context import get_access_token

    from BL.auth import session as sessions
    from BL.auth.common import settings
    from BL.auth.service import service_cookies

    token = get_access_token()
    if token is None:
        return service_cookies(), None
    return {settings.cookie_name(sessions.ACCESS_COOKIE): token.token}, token.subject


def _audit_tool_call(name: str, status: int, *, user_id: Any = None) -> None:
    try:
        from BL.auth.common.audit import record

        record("mcp_tool_call", None, detail={"tool": name, "status": status}, user_id=user_id)
    except Exception:  # noqa: BLE001 -- auditing never breaks a tool call
        logger.exception("mcp: audit failed for %s", name)


@server.list_tools()
async def list_tools() -> list[t.Tool]:
    return [spec["tool"] for name, spec in tools().items() if tool_allowed(name)]


@server.call_tool()
async def _call_tool_handler(name: str, arguments: dict[str, Any] | None):
    blocks, structured = await call_tool_structured(name, arguments)
    return (blocks, structured) if structured is not None else blocks


# --------------------------------------------------------------------------- #
# Wiring into the FastAPI app
# --------------------------------------------------------------------------- #

MIN_SECRET_LENGTH = 32


def mcp_path() -> str:
    secret = os.getenv("MCP_PATH_SECRET", "").strip()
    return f"/mcp/{secret}" if secret else "/mcp"


def _is_production() -> bool:
    env = (os.getenv("APP_ENV") or ("production" if os.getenv("RENDER") else "development")).strip().lower()
    return env == "production"


def check_secret_policy(path: str, *, production: bool | None = None) -> None:
    """Refuse an unprotected endpoint in production; warn about a weak secret.

    The unsuffixed `/mcp` exposes every tool (bank balance, e-mail, the REPS
    audit sheet) to anyone who finds the host, so outside development it is a
    startup error rather than a warning.
    """

    production = _is_production() if production is None else production
    if path == "/mcp":
        if production:
            raise RuntimeError(
                "MCP_PATH_SECRET is not set: refusing to serve the MCP endpoint "
                "unprotected at /mcp in production. Set MCP_PATH_SECRET (32+ random "
                "characters) on the service, or APP_ENV=development locally."
            )
        logger.warning("MCP_PATH_SECRET is not set: the MCP endpoint is served unprotected at /mcp")
        return
    if len(path) - len("/mcp/") < MIN_SECRET_LENGTH:
        logger.warning(
            "MCP_PATH_SECRET is shorter than %d characters; rotate it to a longer random value",
            MIN_SECRET_LENGTH,
        )


class _Endpoint:
    """ASGI endpoint delegating to the (lifespan-started) session manager."""

    async def __call__(self, scope, receive, send):
        if _session_manager is None:
            raise RuntimeError("MCP session manager is not running (lifespan not started)")
        await _session_manager.handle_request(scope, receive, send)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _session_manager
    _session_manager = StreamableHTTPSessionManager(server, stateless=True, json_response=True)
    async with _session_manager.run():
        yield
    _session_manager = None


def _oauth_protected(app: FastAPI, path: str):
    """MCP_AUTH_MODE=oauth (SECURITY_PLAN.md §3.6): the SDK's OAuth 2.1 +
    PKCE authorization-server routes go on `app`, and the MCP endpoint only
    answers a bearer token minted for an approved connector device."""
    from mcp.server.auth.middleware.auth_context import AuthContextMiddleware
    from mcp.server.auth.middleware.bearer_auth import BearerAuthBackend, RequireAuthMiddleware
    from mcp.server.auth.routes import build_resource_metadata_url, create_auth_routes, create_protected_resource_routes
    from mcp.server.auth.settings import ClientRegistrationOptions, RevocationOptions
    from pydantic import AnyHttpUrl
    from starlette.middleware.authentication import AuthenticationMiddleware

    from BL.auth import oauth

    provider = oauth.BigWhalesOAuthProvider()
    issuer = AnyHttpUrl(oauth.issuer_url())
    resource = AnyHttpUrl(f"{oauth.issuer_url()}{path}")
    app.router.routes.extend(
        create_auth_routes(
            provider,
            issuer_url=issuer,
            client_registration_options=ClientRegistrationOptions(enabled=True, valid_scopes=[oauth.SCOPE], default_scopes=[oauth.SCOPE]),
            revocation_options=RevocationOptions(enabled=True),
        )
        + create_protected_resource_routes(
            resource_url=resource, authorization_servers=[issuer], scopes_supported=[oauth.SCOPE], resource_name="Big Whales"
        )
    )
    protected = RequireAuthMiddleware(_Endpoint(), required_scopes=[oauth.SCOPE], resource_metadata_url=build_resource_metadata_url(resource))
    return AuthenticationMiddleware(AuthContextMiddleware(protected), backend=BearerAuthBackend(provider))


def mount(app: FastAPI) -> str:
    """Register the MCP endpoint on `app`; returns the path it is served at."""
    global _app, _tools
    _app = app
    _tools = None
    path = mcp_path()
    from BL.auth.oauth import mcp_auth_mode

    if mcp_auth_mode() == "oauth":
        endpoint = _oauth_protected(app, path)
    else:
        check_secret_policy(path)
        endpoint = _Endpoint()
    app.add_route(path, endpoint, methods=["GET", "POST", "DELETE"], include_in_schema=False)
    return path
