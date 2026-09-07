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
    "Tools for the Big Whales real-estate site (BrrrrDealAnalyzer). Conventions: "
    "every field whose name ends in _in_thousands, or whose alias is purchasePrice, "
    "rehabCost, closingCostsBuy, closingCostsRefi, cashReserve, salePrice, "
    "sellingClosingCosts or arv_in_thousands, is in THOUSANDS of dollars (250 = $250k); "
    "rent, taxes, insurance, HOA and utilities are plain dollars; rates and fees are "
    "percentages (75 = 75%). Deal bodies use the camelCase aliases shown in each schema. "
    "Active deals: stage 1 New, 2 Working, 3 Brought, 4 Keep in Mind, 5 Dead; section "
    "1 Wholesale, 2 Market, 3 Off Market. Where a tool takes deal_type it must match the "
    "deal ('BRRRR' or 'FLIP'). Update tools replace the whole record: read it first, edit, "
    "send it back."
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
        "List every deal on the My Deals board (BRRRR and FLIP): saved inputs, address, "
        "stage/section, notes, comps and freshly computed analysis metrics."
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
    # --- Bought Deals ---
    "get_bought_deals": (
        "List purchased deals on the Bought Deals board, with boughtStage (pipeline stage id) "
        "and the completedSubstages checklist, plus analysis metrics."
    ),
    "add_bought_deal": "Create a bought deal directly (normally use move_to_bought instead).",
    "update_bought_deal": (
        "Replace a bought deal. Also how checklist items are ticked (completedSubstages) and "
        "how a deal advances to the next boughtStage. Send the full record back."
    ),
    "delete_bought_deal": "Delete a bought deal. deal_type must match the deal.",
    "move_to_bought": (
        "Copy an active deal onto the Bought Deals board (the site allows this for stage 3 "
        "'Brought' deals). The active deal is kept. deal_type must match the deal."
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
        "Live total balance across the Mercury bank accounts in $k, used to re-anchor the "
        "timeline to today (503 if MERCURY_API_TOKEN is not configured on the server)."
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
        "Log a REPS (Real Estate Professional Status) activity to the user's Google Sheet: "
        "user (Aviv2026 or Yarden2026), description of at least 20 characters, start_time and "
        "end_time as ISO datetimes, optional property, category, evidence items and people."
    ),
    "reps_entries": "All REPS entries of a user plus year-to-date stats (750 h and 500 h material-participation progress).",
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
    return schema.get("type") == "string" and schema.get("format") == "binary"


def _build_tools(app: FastAPI) -> dict[str, dict[str, Any]]:
    spec = json.loads(
        json.dumps(app.openapi()).replace("#/components/schemas/", "#/$defs/")
    )
    defs = spec.get("components", {}).get("schemas", {})
    tools: dict[str, dict[str, Any]] = {}

    for route in app.routes:
        if not isinstance(route, APIRoute) or not route.include_in_schema:
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
            tools[name] = {
                "method": method,
                "path": route.path,
                "path_params": path_params,
                "query_params": query_params,
                "form_fields": form_fields,
                "file_fields": file_fields,
                "json_body": has_json_body,
                "tool": t.Tool(
                    name=name,
                    description=DESCRIPTIONS.get(name) or op.get("summary") or name,
                    inputSchema=input_schema,
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

async def call_tool(name: str, arguments: dict[str, Any] | None) -> list[t.ContentBlock]:
    spec = tools().get(name)
    if spec is None:
        raise ValueError(f"Unknown tool: {name}")
    args = dict(arguments or {})

    missing = [p for p in spec["path_params"] if p not in args]
    if missing:
        raise ValueError(f"Missing required argument(s): {', '.join(missing)}")
    path = spec["path"].format(**{p: args[p] for p in spec["path_params"]})
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

    transport = httpx.ASGITransport(app=_app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://mcp.internal") as client:
        response = await client.request(spec["method"], path, params=params, **request_kwargs)

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
        ]
    if content_type.startswith("application/json"):
        return [t.TextContent(type="text", text=json.dumps(response.json(), indent=2))]
    return [t.TextContent(type="text", text=response.text)]


@server.list_tools()
async def list_tools() -> list[t.Tool]:
    return [spec["tool"] for spec in tools().values()]


@server.call_tool()
async def _call_tool_handler(name: str, arguments: dict[str, Any] | None) -> list[t.ContentBlock]:
    return await call_tool(name, arguments)


# --------------------------------------------------------------------------- #
# Wiring into the FastAPI app
# --------------------------------------------------------------------------- #

def mcp_path() -> str:
    secret = os.getenv("MCP_PATH_SECRET", "").strip()
    return f"/mcp/{secret}" if secret else "/mcp"


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


def mount(app: FastAPI) -> str:
    """Register the MCP endpoint on `app`; returns the path it is served at."""
    global _app, _tools
    _app = app
    _tools = None
    path = mcp_path()
    if path == "/mcp":
        logger.warning("MCP_PATH_SECRET is not set: the MCP endpoint is served unprotected at /mcp")
    app.add_route(path, _Endpoint(), methods=["GET", "POST", "DELETE"], include_in_schema=False)
    return path
