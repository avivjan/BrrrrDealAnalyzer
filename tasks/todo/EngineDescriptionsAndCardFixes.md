# Engine descriptions and card fixes
Branch `claude/lucid-archimedes-8529vo` from `main` (36988cd). Task name `EngineDescriptionsAndCardFixes`;
the session's designated branch is used in place of a `<task_name>` branch.

## Context

The calculation-breakdown popup now surfaces every result field's description and headline number from the
UI, so wrong descriptions and sloppy card formatting are visible to the owner. Six items were listed in
`tasks/todo/CalculationBreakdownPopup.md` ("Noticed, not changed"); the owner picked these six to fix now.
Decisions taken with the owner: descriptions follow the code (no formula changes), DSCR is described as
rent ÷ PITIA, the MCP "warning messages" promise is dropped rather than implemented, and a $0 cash flow is
neutral (not red).

No calculation output changes, so the numeric goldens (`tests/_regression_snapshots/calculations.json`,
`endpoints.json`, `frontend/e2e/golden/*`) stay as they are. Only the OpenAPI/model goldens move, because
they embed the field descriptions.

## Changes

### 1. ROI description — `BackEnd/ReqRes/common/analyze_results.py:50-52`
Code (`BL/analyze/common/deal_math.py:111-114`) is `(12 × cash_flow + net_profit) ÷ |cash_out| × 100`, and
`net_profit = equity + cash_out`. New text: "Return on investment in percent: one year of cash flow (12 x
cash_flow) plus net_profit, divided by the cash left in the deal (|cash_out|). -1 means infinite (no cash
left in the deal); -2 means not applicable (cash flow is 0 or negative)." Add the same formula to the GLOSSARY
sentence in `BackEnd/mcp_server.py:77-78` ("cash_on_cash = ...; roi = ...").

### 2. DSCR description — `analyze_results.py:30-32`
Code (`brrrSteps/dscr.py:67-70`, `deal_math.py:73-82`) is monthly rent ÷ monthly PITIA. New text: "Debt
service coverage ratio after the refinance: monthly rent divided by the monthly PITIA (principal, interest,
taxes, insurance and HOA). Above 1.0 the rent covers the payment; lenders usually want 1.2 or more."
Matches the breakdown formula string already emitted by `BL/analyze/explain/brrr.py:101-112`.

### 3. Flip holding-cost descriptions — `analyze_results.py:129-131, 142-143`
Code (`flipSteps/holding_costs.py:6-12`) is `total_hml_interest + operating`. `total_holding_costs` becomes
"Hard-money interest plus taxes, insurance, HOA and utilities over the holding time, in dollars
(total_hml_interest + the operating costs)." Flip `net_profit` wording "hard-money points and interest,
holding costs" becomes "hard-money points, holding costs (which include the hard-money interest)" so interest
is not read as counted twice.

### 4. My Deals header average CoC — `frontend/src/views/MyDeals.vue:54-71`
Only BRRRR deals with `cash_on_cash > 0` enter the average (this drops the -1 / -2 sentinels and 0). Rename
`cocs` to `positiveCashOnCashValues` and add a one-line comment naming the sentinels. `null` (renders "—")
when nothing qualifies, as today.

### 5. Card money formatting and Cash Flow tone — `DealCard.vue:92-93, 342-352`, `BoughtDealCard.vue:120`
Replace both local `formatMoney` lambdas with `formatCardMoney`, which returns "-" for null/non-finite and
otherwise delegates to the shared `formatMoney` in `frontend/src/utils/money.ts:88-98` on `Math.round(val)`
(so 0 → "$0", -1234 → "-$1,234", 85.04 → "$85", no cents). Cash Flow class becomes a computed
`cashFlowToneClass`: `> 0` → `text-positive`, `< 0` → `text-negative`, else `text-fg`.

### 6. MCP messages promise — `BackEnd/mcp_server.py:90-99`, `analyze_results.py:20`
Drop "warning messages" from `analyze_brrr` and "messages" from `analyze_flip` descriptions. `_MESSAGES`
becomes "Reserved for input-validation warnings; currently never populated (invalid input is rejected with
HTTP 400 instead), so this is null or an empty list." BRRRR keeps `messages=None` (changing it would move the
numeric goldens for no user benefit).

### Goldens
`tests/test_mcp.py:48-50` asserts `app.openapi()` equals `tests/_regression_snapshots/openapi.json`, and
`models.json` embeds the same descriptions. Re-record with `python3 verify_regression.py snapshot` (needs the
throwaway PostgreSQL from `BackEnd/docker-compose.test.yml`) and confirm with `git diff --stat` that only
description strings changed in `openapi.json` / `models.json` and the other three snapshot files are untouched.

## Tests

**Unit**
- `BackEnd/tests/test_mcp.py` (`TestOutputDocs`, near line 329): roi description mentions "cash flow" and
  "left in"; dscr mentions "rent" and "pitia"; flip `total_holding_costs` mentions "hard-money interest";
  `analyze_brrr` / `analyze_flip` tool descriptions do not contain "warning" or "messages"; the messages field
  description says "never populated".
- `frontend/src/components/DealCard.contract.test.ts`: cash_flow 0 → "$0" with `text-fg` and neither tone
  class; -1234 → "-$1,234" with `text-negative`; 350 stays "$350" with `text-positive`; missing → "-".
- `frontend/src/components/BoughtDealCard.contract.test.ts`: a negative figure renders "-$1,234", a zero
  renders "$0".
- `frontend/src/views/MyDeals.figures.contract.test.ts` (new, mounts the view the way
  `MyDeals.settle.contract.test.ts` does, mocking `api.getActiveDeals`): deals with CoC 12, 8, -1, -2, 0 and a
  FLIP show "10.00%"; all sentinels/zero show "—".

**Integration**
- Full `pytest -ra` in `BackEnd/` against the compose PostgreSQL (OpenAPI golden equality, MCP tool list,
  explain suite, analyze suite unchanged).
- `npm test` in `frontend/` (vitest, whole suite).

**E2E**
- `npx playwright test` in `frontend/` for the My Deals and Bought Deals flows; no golden re-record expected
  because the calculation JSON is unchanged. Manual: My Deals header "Avg cash on cash" ignores an ∞ deal; a
  BRRRR card with negative cash flow reads "-$1,234" in red; a $0 rehab reads "$0".

**MCP server support**
- Covered by item 6 plus the GLOSSARY line in item 1; `test_mcp.py` findability phrases ("brrrr calculator",
  "analyze a flip") still match after the wording change.

**Security** (contents of `.claude/security.md`)
- "Please check through all the code you just wrote and make sure it follows security best practices. make
  sure there are no sensitive information in the frontend and there are no vulnerabilities that can be
  exploited throughout all the code in this repo." Descriptions and formatters only; confirm nothing new is
  interpolated as HTML and no secrets touched. `bandit` job in CI stays green.

## Todo (≈ 2 h)
- [x] **F1** (5 min) — Plan file at `tasks/todo/EngineDescriptionsAndCardFixes.md`, first commit.
- [x] **F2** (15 min) — Backend descriptions: items 1, 2, 3, 6 in `analyze_results.py` and `mcp_server.py`.
- [x] **F3** (15 min) — `test_mcp.py` description assertions; re-record `openapi.json` / `models.json`; pytest.
- [x] **F4** (15 min) — `MyDeals.vue` average CoC filter + new figures contract test.
- [x] **F5** (25 min) — `DealCard.vue` / `BoughtDealCard.vue` `formatCardMoney` + `cashFlowToneClass` + tests.
- [x] **F6** (20 min) — `npm test`, Playwright smoke for the two boards, security read-through.
- [ ] **F7** (10 min) — Tick the six items in `CalculationBreakdownPopup.md`'s "Noticed, not changed" list as
  fixed here, push, open the PR.

## Verification
1. `docker compose -f BackEnd/docker-compose.test.yml up -d --wait`; `pip install -r BackEnd/requirements.txt`;
   `cd BackEnd && python3 verify_regression.py snapshot && git diff --stat tests/_regression_snapshots` (only
   openapi.json and models.json change); `pytest -ra`.
2. `cd frontend && npm ci && npm test`; then `npx playwright test e2e/flows` for the board flows.
3. MCP: `analyze_brrr` via the Big Whales MCP tool list shows the new description and the `dscr`/`roi` field
   descriptions in its output schema.
