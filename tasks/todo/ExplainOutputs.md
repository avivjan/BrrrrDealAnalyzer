# Explain every MCP output: field descriptions, output schemas, a glossary

Branch `feature/mcp-explain-outputs` from `main` (08b0a88).

## Why

With the compact tools in place, a claude.ai chat found the right deal but misread the
numbers: it took `cash_out: -26587` as "pulled 26.6k out, 0 left in" and ignored
`cash_out_routi: 5520`. The inputs are documented (41 field descriptions) but the outputs
are not: the result models carry zero descriptions, the MCP tools publish no output schema,
and the compact rows reuse the same raw names. Nothing tells Claude that a negative
`cash_out` is money still in the deal, or that "routi" is the wire received at the refi
closing table.

Owner's definitions (verbatim intent): **routi** = the cash wire received at the refinance
closing table; **cash out** = the total received from the deal minus the total put into it
(negative = that much of your money is still in the deal).

## Design

1. **Descriptions on every output field** (`ReqRes/common/analyze_results.py`,
   `deals_schemas.py`): meaning, unit (dollars vs thousands vs percent) and sign convention.
   The active/bought response models inherit the analyze results, so `get_deal`, the full
   dumps and the website's OpenAPI all gain them for free.
2. **Output schemas on the tools** (`mcp_server.py`): each tool with a JSON response gets
   `outputSchema` from the endpoint's 200 response in OpenAPI (refs pruned to `$defs`, so the
   descriptions travel with it); list responses are wrapped as `{"items": [...]}` because
   MCP output schemas must be objects. Tool results return `structuredContent` alongside the
   text, so clients that validate against the schema get a match.
3. **Glossary in the server instructions**: cash_out sign, routi, equity, net profit,
   cash-on-cash, the -1/-2 sentinels, dollars vs thousands.
4. **Two self-explaining compact fields** in `DealSummary`: `cash_left_in_deal` (money still
   in the deal, never negative) and `cash_wire_at_refi` (routi), next to the raw `cash_out`.

## Tests (rule 3)

- **Documentation completeness**: every field of every response model a tool returns
  (analyze results, active/bought responses, DealSummary, TopDeal, PortfolioSummary,
  DealDetail) has a non-empty description; the two sign-sensitive fields mention
  "negative" / "left in" and "wire" / "closing table". Fails the moment someone adds an
  undocumented output field.
- **Output schemas**: every JSON-returning tool has an `outputSchema`; it is a valid
  object schema; its property descriptions are present; `structuredContent` is returned and
  validates against it (checked with `jsonschema`), for a scalar, an object and a list tool.
- **Compact fields**: `cash_left_in_deal` = 26587 for a deal with `cash_out` = -26587 and 0
  for a positive one; `cash_wire_at_refi` equals `cash_out_routi`.
- **Glossary**: instructions mention every headline metric and the sentinels.
- **Probe** (`.github/scripts/mcp_probe.py`): the question also asks "and how much of our
  money is still left in that deal?"; the script fetches `/deals?board=bought` from the same
  host, computes the expected `cash_left_in_deal` of the top deal, and fails if the answer
  text does not contain that number (rounded to thousands, either "26,587" or "26.6k" forms).
  Unit tests for the number-matching helper.
- Existing suites unchanged; goldens re-recorded (OpenAPI gains descriptions and two fields).

## Todo (agent wall-clock, ≈ 2 h 15)

- [x] **X1** (5 min) — Branch + this plan.
- [x] **X2** (30 min) — Field descriptions on the result and compact models; the two compact fields in `BL/deals/compact.py`.
- [x] **X3** (35 min) — `mcp_server.py`: `outputSchema` from OpenAPI responses (object wrap for lists), `structuredContent` in results, glossary in `INSTRUCTIONS`.
- [x] **X4** (30 min) — Tests: documentation completeness, output schemas + structured content validation, compact fields, glossary.
- [x] **X5** (20 min) — Probe: left-in-deal question, expected value from the API, number-matching helper + unit tests.
- [x] **X6** (10 min) — Goldens re-recorded and reviewed (additive); README: one paragraph on the glossary and output schemas.
- [x] **X7** (5 min) — Security task (`.claude/security.md`): descriptions and schemas only expose field meanings, no data; the probe still never prints the URL; the extra API fetch uses the same secret host and reads only.
- [x] **X8** (10 min) — Full `pytest`, `verify_regression.py verify`, nightly package tests, workflow schema; commit, push, PR.

## Review

**What changed.** Every output field of the analyze results and the compact views now has a
description with unit and sign convention, written from the owner's definitions: `cash_out`
= total received from the deal (the refinance wire) minus total put in, negative = that much
of your own money still left in the deal; `cash_out_routi` = the cash wire received at the
refinance closing table, before subtracting what was invested. The active/bought response
models inherit them, so `get_deal`, the full dumps and the website's OpenAPI document all
gain them. `DealSummary` adds `cash_left_in_deal` (never negative) and `cash_wire_at_refi`.

`mcp_server.py`: each JSON tool publishes an `outputSchema` derived from its endpoint's first
2xx JSON response in OpenAPI (refs pruned to `$defs`, pydantic `title` keys stripped, lists
wrapped as `{"items": [...]}` because MCP output schemas must be objects); results carry
`structuredContent` matching it (the public `call_tool` still returns content blocks;
`call_tool_structured` returns both). The eight tools that return full deal records publish
a loose object schema pointing at `get_deal`, which carries the complete described schema
once; that keeps `tools/list` at 174 kB (budget 200 kB) instead of 334 kB. List results are
serialised compactly (a third fewer bytes). The server instructions gained a glossary.
Untyped-dict endpoints (deletes, health, config status, Mercury) and the PDFs publish no
output schema.

**Tests added (rule 3).** `tests/test_mcp.py` (+11): every field of the six documented
response models has a description (parametrised, names the model); the sign conventions are
spelled out; the glossary covers every headline metric and the sentinels; every JSON tool's
output schema is a valid object schema with the descriptions and without titles, loose ones
point at `get_deal`; structured content validates against the schema for an untyped dict, an
object and a wrapped list; structured content also over HTTP; `cash_left_in_deal` /
`cash_wire_at_refi` for a deal with money left in and for one that pulls out more than it
invested. Nightly package (+1): the probe's amount matching. Full backend suite: 278 passed
(248 before). Nightly package: 26 OK.

**Probe.** The question now also asks how much of our own money is still left in that deal;
the script reads `cash_left_in_deal` of every bought deal from the site's own compact
endpoint on the connector's host and fails unless the answer quotes one of those amounts in
a usual form (26,587 / $26,587 / 26.6k / 27k). Any bought deal is accepted because Claude
may reasonably pick a different "best" deal than the top-by-equity one.

**Goldens: one thing to know.** Re-recording `tests/_regression_snapshots` picked up more
than this branch's additions. PR #46 (audit fixes F1-F10) added a "rehab float" step and
changed formula texts in the calculator but did not re-record `calculations.json` and
`endpoints.json`, so `verify_regression.py verify` has been failing on `main` since that
merge (296 differences in calculations) without CI noticing, because CI runs `pytest` but
not `verify_regression.py verify`. This branch's re-record absorbs those PR #46 changes; the
calculator itself is untouched here. Recommended follow-up: run `verify_regression.py
verify` in the Backend CI job so a golden can no longer go stale.

**Security task (X7).** Descriptions and schemas expose field meanings, not data. The probe
still never prints the connector URL; its extra fetch is a read-only GET against the same
host and only the compact amounts are used. No secrets in the diff (scanned).

**Manual step.** None new; the probe still needs the two secrets from the previous task.
