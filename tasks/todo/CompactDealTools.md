# Compact, searchable deal tools for the MCP server

Branch `feature/mcp-compact-deal-tools` from `main` (38ba79d).

## Why

A regular claude.ai chat with the connector enabled could not answer "what's the best deal we
did so far": it looked the tools up by keyword ("deal query", "deal history"), found nothing,
and answered from memory. Had it found them, `get_active_deals` returns ~2 MB (237 deals,
each with its full calculation breakdown), which a chat cannot digest. Three fixes, all
guarded by tests so neither failure can come back:

1. **Findability.** Tool names and descriptions written in the words a user uses
   ("portfolio", "properties we bought", "closed deals", "deal history", "best deal",
   "search"), server instructions that route deal questions to the compact tools first, and
   MCP tool annotations (read-only / destructive) derived from the HTTP method.
2. **Compaction.** Small endpoints for the common questions: a compact deal list with
   filters and word search across both boards, and a portfolio summary. No breakdowns.
3. **Detail on demand.** One endpoint that returns a single deal in full (inputs, metrics,
   breakdowns, comps) by id, whichever board it is on.

New capabilities are HTTP endpoints, not MCP-only code, so they become tools through the
existing OpenAPI mechanism, stay testable with the normal harness, and the website could use
them later. The frontend is untouched.

## Design

New router `BackEnd/routers/deals.py` + `BackEnd/BL/deals/` (reuses
`BL/common/deal_response.py`, which already produces the full response model per row; the
compact projection just picks fields). 237 rows is small, so filtering and word search run in
Python over the loaded rows, no new SQL.

| Endpoint | Tool | Returns |
| --- | --- | --- |
| `GET /deals?board=&deal_type=&stage=&q=&limit=` | `list_deals` | Compact rows across both boards: id, board (`active`/`bought`), deal_type, address, stage or boughtStage, section, purchase, rehab, ARV or sale price, rent, cash flow, cash-on-cash, ROI, equity, net profit, total cash needed, cash out, created/updated. `q` matches words in address, notes, task, niche, contact. |
| `GET /deals/search?q=` | `search_deals` | Same rows; a dedicated name so a keyword lookup for "search" hits. |
| `GET /deals/portfolio` | `portfolio_summary` | Counts by board/type/stage, totals (equity, monthly cash flow, cash invested), and the top 3 by equity, by cash flow and by cash-on-cash, with ids so a follow-up can fetch detail. |
| `GET /deals/{deal_id}` | `get_deal` | The full record with breakdowns and comps, found on either board; 404 otherwise. |

`mcp_server.py`: descriptions rewritten in user vocabulary (the two big list tools say
"large: prefer list_deals"), `INSTRUCTIONS` routes deal/portfolio/best-deal questions to the
compact tools, and `Tool.annotations` set `readOnlyHint` for GET and `destructiveHint` for
DELETE. `tests/_regression_snapshots` re-recorded with `verify_regression.py snapshot`
(additive: four new paths, new response models), diff reviewed.

## Tests (rule 3)

- **Unit / integration, endpoints** (`tests/test_deals.py`): list across both boards, each
  filter, word search (case-insensitive, multi-word, no hits → empty), limit, portfolio maths
  against seeded deals, detail for active and bought ids, unknown id → 404, compact rows carry
  no `breakdowns`.
- **Through the tools** (`tests/test_mcp_tools.py`): `list_deals`, `search_deals`,
  `portfolio_summary`, `get_deal` round trips; error mapping.
- **Size budgets** (`tests/test_mcp.py`): seed 60 deals; `list_deals` and
  `portfolio_summary` responses under 50 kB, `get_deal` under 100 kB; compact rows never
  include breakdowns. Fails if someone later adds a heavy field.
- **Vocabulary** (`tests/test_mcp.py`): a table of user phrases ("best deal", "deal history",
  "portfolio", "properties we bought", "closed deals", "search deals", "cash balance", "log
  hours", "send an offer", "pdf report", ...) — for each, at least one tool's name or
  description contains every word. Guards descriptions written in internal jargon.
- **Per-tool contract** (`tests/test_mcp.py`): every GET tool is `readOnlyHint`, every
  DELETE is `destructiveHint`, descriptions ≤ 400 chars, the large list tools are marked.
- **Nightly behavioural probe** (optional, needs your decision): `.github/scripts/mcp_probe.py`
  asks Claude through the Messages API with the connector attached "what's the best deal we
  did so far?" and asserts a compact tool was called before answering. Runs in the nightly
  only, skipped unless an `ANTHROPIC_API_KEY` repository secret exists; result line in the
  email. A unit test covers the assertion logic with a canned response. Implementation reads
  the `claude-api` skill first for the current MCP-connector request shape.
- Existing suites unchanged; goldens re-recorded.

## Todo (agent wall-clock, ≈ 2 h 45)

- [x] **P1** (5 min) — Branch + this plan.
- [x] **P2** (35 min) — `BL/deals/` + `routers/deals.py` (compact projection, filters, word search, portfolio, detail), registered in `routers/__init__.py`.
- [x] **P3** (15 min) — `mcp_server.py`: vocabulary descriptions, routing instructions, annotations.
- [x] **P4** (25 min) — `tests/test_deals.py`.
- [x] **P5** (25 min) — MCP tests: tool round trips, size budgets, vocabulary table, annotations.
- [x] **P6** (30 min) — Nightly probe script + gated job + email line + unit test (only if approved).
- [x] **P7** (10 min) — Re-record goldens, review the diff; README API-reference rows and MCP section.
- [x] **P8** (5 min) — Security task (`.claude/security.md`): the new endpoints are read-only and unauthenticated like the rest of the API (same exposure as today, behind the secret path for MCP); word search is Python-side, no SQL built from input; the probe's API key lives only in a GitHub secret and is never logged or echoed; nothing added to the frontend.
- [x] **P9** (10 min) — Full `pytest`, `verify_regression.py verify`, nightly package tests, workflow schema; commit, push, PR.

## Review

**What changed.** Four read-only endpoints in a new router (`BackEnd/routers/deals.py`,
logic in `BackEnd/BL/deals/compact.py`, models in `ReqRes/common/deals_schemas.py`,
~200 lines), which become four MCP tools automatically: `list_deals`, `search_deals`,
`portfolio_summary`, `get_deal`. They reuse the existing full-response builders and only
project, filter and rank, so every number matches the website. `mcp_server.py`: server
instructions now route deal / portfolio / best-deal questions to the compact tools first,
every tool description is written in the words a user uses (portfolio, properties we
bought, closed deals, deal history, search, log hours, bank balance ...), the two full board
dumps are marked large, and each tool carries MCP annotations (read-only for GET,
destructive for DELETE) derived from the HTTP method. Total: 49 tools; `tools/list` is
104 kB, under the 200 kB budget.

**Tests added (rule 3).** `tests/test_deals.py` (10): list across boards, every filter,
word search (case-insensitive, all words, task / niche / contact fields, no-hit), bad
filters → 400, portfolio counts / totals / top lists and the empty case, detail on either
board, unknown and malformed ids → 404. `tests/test_mcp_tools.py` (+1): the four tools
round-trip. `tests/test_mcp.py` (+30): 25 user phrases each matched by a tool name or
description (a description written in internal jargon fails by phrase), instructions route
to the compact tools, annotations follow the method, and with 70 deals seeded
`list_deals` / `search_deals` < 50 kB, `portfolio_summary` < 10 kB, `get_deal` < 100 kB,
no breakdowns in compact rows, and the full dump is shown to be the large one. Nightly
package (+2): the probe's verdict logic and its skip-without-secrets path. Full backend
suite: 248 passed (206 before). Goldens re-recorded: additive only (four paths, eight
endpoint recordings, no removed lines); `verify_regression.py verify` clean.

**Nightly probe (P6).** `.github/scripts/mcp_probe.py` asks Claude (`claude-opus-5`,
Anthropic Python SDK, MCP connector beta `mcp-client-2025-11-20`, streaming) the real
question with the connector attached and passes only if a compact tool was called. New
nightly job **MCP connector probe** runs it and reports `success` / `failure` / `skipped`;
the notify job gets `MCP_PROBE_OUTCOME` and the e-mail lists the job (feeding the verdict)
only when it actually ran. It skips cleanly until the two repository secrets exist.

**Security task (P8).** The new endpoints are read-only and unauthenticated like the rest
of the API (same exposure as today; the MCP path secret still gates the connector). Word
search runs in Python over already-loaded rows, no SQL built from input; `deal_id` is
validated as a UUID before any query. The probe reads its key and URL from GitHub secrets
only, never prints the URL, and truncates exceptions. Nothing added to the frontend; no
secret in the repo (scan of the diff clean).

**Manual steps for the owner.** Add repository secrets `ANTHROPIC_API_KEY` and
`MCP_PROBE_URL` (the connector URL with the secret path) under *Settings → Secrets and
variables → Actions* to switch the probe on; it costs roughly one short conversation per
night. Until then the nightly shows nothing for it.

**Not done, on purpose.** No ReqRes per-endpoint shim files for `/deals` (the models live
in `ReqRes/common/deals_schemas.py` like the others' real definitions); the website does not
use the new endpoints yet.
