# MCP server for every website feature, hosted as a Claude connector

Plan approved in plan mode. One tool per
backend endpoint, generated from the app's own OpenAPI and executed in-process, served over
Streamable HTTP at `/mcp/<MCP_PATH_SECRET>` on the existing Render backend. Estimates are agent
wall-clock minutes.

- [x] **M1** (5 min) — This checklist.
- [x] **M2** (40 min) — `BackEnd/requirements.txt` pin `mcp>=1.13,<2`; `BackEnd/mcp_server.py` (tool list from `app.openapi()`, in-process call via `httpx.ASGITransport`, PDF blob + multipart handling, stateless Streamable HTTP, `lifespan`, `mount`, `MCP_PATH_SECRET`).
- [x] **M3** (10 min) — Wire `BackEnd/main.py` (lifespan + `mcp_server.mount(app)`); confirm `app.openapi()` is unchanged.
- [x] **M4** (20 min) — Hand-written one-line descriptions for all 45 tools.
- [x] **M5** (30 min) — `BackEnd/tests/test_mcp.py`.
- [x] **M6** (20 min) — Local Postgres 16 → full `pytest` + `verify_regression.py verify`.
- [x] **M7** (25 min) — Use the site through the server: uvicorn + MCP client script (analyze, save, list, duplicate, PDF, move to bought, clean up).
- [x] **M8** (15 min) — README section; review below.
- [x] **M9** (10 min) — Commit, push `claude/mcp-server-website-features-j4ix18`, open the PR (owner merges).
- [x] **M9b** (5 min) — Generate the secret, set `MCP_PATH_SECRET` on the Render service.
- [x] **M11** (5 min) — Standing rule in `.claude/CLAUDE.md` + README step 13: every future endpoint/feature is supported over MCP without being asked (backend on Render, frontend on Netlify recorded there too).
- [ ] **M10** (10 min, after merge) — Watch the Render deploy; hand over the connector URL.

## MCP review

**What changed.** One new module, `BackEnd/mcp_server.py` (~330 lines, half of it the
per-tool descriptions), one dependency (`mcp>=1.13,<2`), three lines in `BackEnd/main.py`
(`lifespan=` and `mcp_server.mount(app)`), a new test file `BackEnd/tests/test_mcp.py`
(13 tests), a README section and this checklist. No router, schema, BL or DAL file was
touched.

**How it works.** The tool list is built from `app.openapi()` plus `app.routes` (tool name =
the route's function name, minus a `_route` suffix; input schema = path + query params, the
JSON body under `body`, or the flattened multipart form with files as
`{filename, content_type, content_base64}`; `#/components/schemas` refs rewritten to a pruned
`$defs`). A call performs the real request against the same app in-process through
`httpx.ASGITransport`, so every tool behaves exactly like the website's own call: 45 tools
for 45 operations. JSON comes back as text, PDFs as an embedded `application/pdf` blob, any
4xx/5xx as an `isError` tool result carrying the endpoint's `detail`. Transport is stateless
Streamable HTTP with JSON responses at `/mcp/<MCP_PATH_SECRET>` (plain `/mcp`, with a startup
warning, when the variable is unset); every other `/mcp/...` path is a 404. The session
manager is created inside the FastAPI lifespan, so `with TestClient(app)` blocks can be opened
repeatedly.

**Kept.** `app.openapi()` is byte-identical to the golden (`verify_regression.py verify`: all
five snapshots identical), because the MCP route is a plain Starlette route with
`include_in_schema=False`.

**Verified locally** (Postgres 16 started from the system binaries, Docker daemon
unavailable here): `pytest` 131 passed (118 existing + 13 new); `verify_regression.py verify`
clean; and a real `uvicorn` with `MCP_PATH_SECRET=localdemo` driven by the official MCP client
over Streamable HTTP: initialize → 45 tools → helloworld → analyze_brrr → analyze_flip →
add_active_deal → get_active_deals → duplicate_deal → report_brrr_pdf (10.9 kB, `%PDF-`) →
move_to_bought → get_bought_deals → list_pipeline_templates → get_liquidity_settings → a
deliberate bad call (schema error surfaced as a tool error) → delete_bought_deal → 2×
delete_deal. `/mcp` and `/mcp/wrong` both 404 while the secret is set.

**Not done, on purpose.** "Copy Summary for AI", the appearance settings and the command
palette are client-side only; the JSON a tool returns is a superset of the copied summary.
No OAuth: claude.ai custom connectors accept a plain URL, so the secret lives in the path.
The production endpoint could not be exercised from this sandbox (egress to `*.onrender.com`
is blocked); the deploy is verified through the Render API after the merge, and the first
production call happens from claude.ai once the connector is added.

**Pre-existing, not mine.** pydantic `UnsupportedFieldAttributeWarning` lines for the
`Field(alias=...)` members of the `PUT` union bodies appear in the existing suite and in
`verify_regression.py` as well.

---

# MCP server: more tests, in CI and the nightly

Plan approved in plan mode. Broad tool coverage per feature area, a real-server end-to-end test
with the official MCP client, a dedicated CI check, and an MCP row in the nightly email.

- [x] **T1** (5 min) — This checklist.
- [x] **T2** (20 min) — `tests/test_mcp.py`: per-tool schema validity, size budget, transport edge cases, secret mount, concurrency.
- [x] **T3** (45 min) — `tests/test_mcp_tools.py`: FLIP, bought flow, pipeline templates, liquidity, REPS, multipart, send-offer, error mapping.
- [x] **T4** (30 min) — `tests/test_mcp_e2e.py`: uvicorn subprocess + official MCP client.
- [x] **T5** (15 min) — `ci.yml` job "MCP server tests" + `mcp_result` output; README CI paragraph.
- [x] **T6** (25 min) — Nightly: download MCP JUnit, `MCP_OUTCOME`, `--mcp-junit`; email row + jobs line; preview fixture; package unit tests; README nightly paragraph.
- [x] **T7** (15 min) — Local verification: full pytest, CI-style MCP run, goldens, nightly unit tests + preview, YAML parse.
- [x] **T8** (10 min) — Review below; commit; push to the PR #37 branch.

## MCP tests review

**What changed.** The MCP suite grew from 13 to 88 tests across three files, and it now has
its own CI check and its own row in the nightly email.

- `BackEnd/tests/test_mcp.py` — per-tool parametrised checks for all 45 tools (valid Draft
  2020-12 schema, every path param required, properties match the route, description present
  and trimmed), body-required parity with OpenAPI, a 200 kB budget on `tools/list`, transport
  edge cases (GET without an event-stream Accept → 406, wrong Accept → 406, unknown tool →
  `isError`, FLIP PDF over HTTP as an embedded resource), the secret path on a scratch app,
  and ten concurrent calls with two different payloads that must not cross-talk.
- `BackEnd/tests/test_mcp_tools.py` (new) — every feature area through tools: FLIP parity,
  update and delete; the bought flow (move to bought, tick a checklist item, stage stats,
  delete, direct create, wrong deal type → 404); pipeline templates (round trip, invalid type
  → 400); liquidity transactions, recurring rules (incl. `amount_k=0` → 422), settings and the
  unconfigured Mercury 503; REPS people/prospects/categories CRUD, unconfigured Sheets → 503,
  invalid user → 400, short description → 422; the two multipart uploads with the BL
  monkeypatched so the base64 → bytes plumbing is asserted; send-offer with the mailer
  monkeypatched. `tests/mcp_helpers.py` holds the two call helpers both files use.
- `BackEnd/tests/test_mcp_e2e.py` (new) — a real `uvicorn` subprocess with
  `MCP_PATH_SECRET` set, driven by the official `mcp` client over Streamable HTTP:
  initialize, 45 tools, analyze, save, list, PDF, a 404 as `isError`, delete; and the secret
  enforced (`/mcp` and a wrong secret → 404).
- `.github/workflows/ci.yml` — new job **MCP server tests** (own Postgres service, runs the
  three files, uploads `junit-mcp-<run>`), exposed as `mcp_result`. The Backend job is
  unchanged and still runs everything, so `mcp_server.py` stays in its coverage report.
- `.github/workflows/e2e-nightly.yml` + `.github/scripts/nightly/` — the notify job downloads
  the MCP JUnit and passes `MCP_OUTCOME` / `--mcp-junit`; the email lists the job in its jobs
  block (it feeds the PASS/FAIL verdict) and shows an "MCP server · pytest, Streamable HTTP"
  column in the suites section (title now "Backend, MCP and frontend suites"); the preview
  fixtures write an `mcp-junit.xml`; two package unit tests cover the row and a missing
  artifact. History totals are untouched on purpose: the MCP cases are already inside the
  backend suite, so counting them again would double the headline.
- README: CI paragraph names the three checks to require; nightly paragraphs mention the job.

**Verified locally.** CI-style run `pytest tests/test_mcp.py tests/test_mcp_tools.py
tests/test_mcp_e2e.py`: 88 passed in ~6 s. Full backend suite: 206 passed (131 before this change, so 75 net new; the 13 original MCP tests were extended in place).
`verify_regression.py verify`: all five goldens identical. Nightly package unit tests: 23 OK
(21 + 2). Both workflow files parse as YAML.

**Worth knowing.** A GET with `Accept: text/event-stream` on the stateless endpoint opens a
stream that never ends (that is the SDK's behaviour, not ours); the first draft of one test
did exactly that and hung, so the test now sends a plain-JSON Accept and expects 406. Also,
`routers/__init__.py` rebinds `routers.reps` / `routers.email` to the router objects, so
monkeypatching the BL functions needs `importlib.import_module("routers.reps")`. And the
REPS prospect API never exposes ids (create/list return name + source only), so the delete
test reads the id from the database; a small API gap, unchanged here.
