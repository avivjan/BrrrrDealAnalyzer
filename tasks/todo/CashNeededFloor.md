# CashNeededFloor: Cash Needed never drops below the day-one floor

Branch `claude/exciting-pasteur-v8qhlz` from `main` (the session's designated branch stands in for a `<task_name>` branch, as the previous plans did). This plan is committed first; boxes are ticked as work lands.

## Context

Owner ask: **Cash Needed = max(floor, current Cash Needed)**, where

> floor = EMD + cash to close + cushion + 1 month utilities + 1 month interest + taxes, insurance and HOA for 30 days.

Today `total_cash_needed` (`BackEnd/BL/analyze/brrrSteps/total_cash_needed.py`) is `total_cash_invested + rehab_cushion + cash_to_refi_table_conservative`. `total_cash_invested` (`cash_out.py:22-26`) nets the rent collected before the refi and the construction-budget spread ("stolen money", negative rehab out-of-pocket) against what was spent, so a deal with a generous budget, an early tenant and a refi wire that covers the shortfall can report a Cash Needed below what the investor must actually have on day one plus the first month. The floor is that day-one figure.

On every pytest fixture and scenario the floor is below the current figure (base: floor $56,689.84 vs $77,542.21; legacy: $51,670.83 vs $63,525), so **no pinned number moves**; the floor bites on a "stolen money" deal with a high ARV (`constructionLoanBudget` 70, `rehabContingency` 0, `arv_in_thousands` 400), which is the new test case.

## Design

**Engine** (`brrrSteps/total_cash_needed.py`, now a `CashNeeded` NamedTuple; the step takes `payload, hml_amount, buy_settlement, cash_out_figures`):
- `hml_interest_first_month` = `calc_hml_interest(hml_amount, HML_interest_rate, DAYS_PER_MONTH)` (30 days of the per diem, 360-day year, same as the holding costs).
- `holding_costs_first_month` = `calc_holding_costs(annual_property_taxes, annual_insurance, montly_hoa, DAYS_PER_MONTH)`.
- `cash_needed_floor` = `earnest_money_deposit + cash_to_close_buy + rehab_cushion + monthly_utilities_until_rented + hml_interest_first_month + holding_costs_first_month`.
- `cash_needed_through_refi` = the current formula, unchanged.
- `cash_needed_floor_top_up` = `max(0, cash_needed_floor - cash_needed_through_refi)`.
- `total_cash_needed` = `cash_needed_through_refi + cash_needed_floor_top_up` (= max(floor, through refi); written as a sum so the explain guard folds it exactly).
- The five new figures are carried on `BrrrResultsWithIntermediates` (record only, no API field; `total_cash_needed_for_deal` keeps its name and meaning).

**Explain** (`explain/brrr.py`, all under `CASH_NEEDED`): two checked steps "HML Interest (first month)" and "Holding Costs (first month)"; `add_sum` "Cash Needed Floor" (EMD, Cash to Close (Buy) linked, Rehab Cushion, Utilities (first month), the two first-month steps linked); `add_sum` "Cash Needed through Refi" (today's three terms); checked step "Floor Top-Up" (formula states the max, $0 when the through-refi figure already covers the floor); the "Cash Needed" headline becomes `add_sum` of ("Cash Needed through Refi", "Floor Top-Up") with the max stated in its note. The popup tree therefore still opens on the three familiar terms one level down, and the floor is readable from the top-up row.

**Descriptions**: `ReqRes/common/analyze_results.py` (`total_cash_needed_for_deal`), `mcp_server.py` glossary, `README.md` engine paragraph, `frontend/src/types/index.ts` comment. No frontend logic (no client-side Cash Needed exists; every input of the floor already lists Cash Needed in `brrrInputImpacts.ts`).

**Goldens that move**: `tests/_regression_snapshots/{calculations,openapi,models}.json` (new breakdown steps, description text) and the Playwright golden(s) that record a BRRRR analysis response (`analyze-brrr-save.json`); every number on them is unchanged, only the steps and text.

## Todo (≈ 2 h 45)
- [ ] S1 (5 min) Commit this plan.
- [ ] S2 (30 min) Engine + record + orchestrator mapping + explain steps; descriptions and README/types wording.
- [ ] S3 (35 min) Backend tests. **Unit** (`tests/test_brrr_lifecycle.py`): `TestCashNeededFloor` — the floor is the deposit, the wire, the cushion and one month of utilities, interest and holding costs (components recomputed from the record and the payload); Cash Needed equals `max(floor, through refi)` on every scenario; the floor wins on the stolen-money / high-ARV deal (top-up positive, Cash Needed = floor); the two existing identities at `:289` and `:338` read `cash_needed_through_refi`. **Integration** (`tests/test_analyze.py`): the floor-wins deal through `POST /analyze/brrr` reproduces the floor from response fields and the breakdown carries "Cash Needed Floor" and "Floor Top-Up"; `test_explain.py` link pins updated (helper prefers an exact label match), `TestEveryFieldIsExplained`, terms-add-up and the scenario guards green; `python3 verify_regression.py snapshot` → review the diff → `verify`; `tests/test_mcp.py` green.
- [ ] S4 (30 min) **E2E** (`frontend/e2e`): `npm run e2e:record` (chromium) re-records the BRRRR goldens whose recorded response carries the breakdown; every other golden must come back byte-identical; `npm run e2e`.
- [ ] S5 (10 min) **MCP**: no new endpoint, tool or field; the new wording reaches the tool schemas through the Pydantic description and the `INSTRUCTIONS` glossary; manual `analyze_brrr` call on the floor-wins deal shows `total_cash_needed_for_deal` equal to the floor and the breakdown listing "Cash Needed Floor".
- [ ] S6 (15 min) **Security** (`.claude/security.md`: "Please check through all the code you just wrote and make sure it follows security best practices. make sure there are no sensitive information in the frontend and there are no vulnerabilities that can be exploited throughout all the code in this repo"): re-read every file touched — the engine change is arithmetic on already-validated Decimals (no new input, endpoint, sink or query); the explain text carries no new user-typed string; no frontend code beyond a comment; no secrets; run `bandit -q -r . -x ./tests,./verify_regression.py -ll -ii` and `npm audit`.
- [ ] S7 (20 min) Final: `cd BackEnd && pytest && python3 verify_regression.py verify`; `cd frontend && npm test && npm run build && npm run e2e`; push `-u origin claude/exciting-pasteur-v8qhlz`; open the PR.

## Verification
- Setup in this sandbox: `pip install -r BackEnd/requirements.txt`; `cd frontend && npm ci`; Postgres 16 local cluster started, role/db `brrrr_test`, `TEST_DATABASE_URL=postgresql+psycopg2://brrrr_test:brrrr_test@127.0.0.1:5432/brrrr_test`.
- Backend: `pytest`; `python3 verify_regression.py verify`.
- Frontend: `npm test`; `npm run build`; `npm run e2e` (record first where goldens change).
- Manual: Analyze a BRRRR with a construction budget well above the rehab and a high ARV: the Cash Needed tile reads the floor; the popup shows "Cash Needed through Refi" and a positive "Floor Top-Up"; on an ordinary deal the top-up is $0 and the tile is unchanged.
