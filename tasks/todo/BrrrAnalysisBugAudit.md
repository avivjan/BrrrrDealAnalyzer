# BRRRR analysis backend bug audit

Branch: `claude/happy-hypatia-so38gw` (the session's designated branch; CLAUDE.md's `<task_name>` branch rule is
superseded by the harness instruction). Plan file copied to `tasks/todo/BrrrAnalysisBugAudit.md` on that branch.

## Context

The 12 result cards (Cash Flow, Cash Out, Cash-Out Routi, CoC, DSCR, Equity, ROI, Net Profit, Cash Needed,
Cash to Close, Cash-Out Routi at lowest ARV, Stolen Money) are what the owner buys houses on. I read every file
that produces or transports those numbers: the step engine `BackEnd/BL/analyze/analyzeBRRR.py` +
`brrrSteps/*`, the primitives `BL/analyze/common/deal_math.py`, validation, the explain layer, the request and
saved-deal schemas, the ORM columns and migrations, the CRUD writers, the deal-response builder, the MCP
forwarding, the compact rows and the PDF formatter, plus the tests that pin them.

**The core arithmetic is sound.** Purchase settlement sources = uses, the three-way hard-money interest split,
the seller tax proration and tax-bucket set-aside, the refi wire, reserves as equity, Cash Needed = max(floor,
through-refi), and the months to days migration all reconcile, and the explain layer's `check` / `add_sum`
guards would fail loudly on drift. The bugs are in the paths *around* the engine: what reaches it, which
defaults apply, and how sentinels are read.

## Scope agreed with the owner
Implement F1, F2, F4, F6, F7, F8. F3, F5 and F9 are recorded as known conventions and left unchanged.

## Findings, ranked

### F1 (High) Saved deals are recomputed with no validation; one bad row takes the whole board down
- `BL/common/deal_response.py:19,35` call `calculate_brrr_results(deal)` straight on the ORM row, skipping
  `validate_brrr_inputs`. `routers/active_deal.py` POST/PUT and `routers/bought_deal.py` accept
  `BrrrActiveDealCreate`, whose numeric fields are all Optional with no range checks.
- Silent wrong numbers on saved deals that `/analyze/brrr` would have rejected: lowest ARV above ARV (the
  conservative wire then exceeds the baseline and Cash Needed is planned on the *higher* appraisal), down
  payment or LTV above 100, negative closing-cost lines, percents out of range.
- Hard failure: `loanTermYears: 0` saves fine, then `calc_mortgage_payment` (`deal_math.py:95`) raises HTTP 400
  inside `GET /active-deals`, `list_deals`, `portfolio_summary`, so every deal disappears until the row is fixed.
- Fix (owner decision: ranges only, blank zeros allowed): `validate_brrr_inputs_for_saved_deal(payload)` in
  `BL/analyze/common/validation.py`. Refactor the existing function so the range and sign checks live in one
  shared helper (`_brrr_range_and_sign_errors`) used by both validators; the analyzer keeps its "must be > 0"
  checks on ARV, price and rent, the saved-deal one skips them (`createEmptyDealForm` saves those as 0) and only
  checks lowest ARV against a non-zero ARV. Every field it reads is Optional on `BrrrActiveDealCreate`, so the
  helper treats `None` as "not set". Call it from `BL/activeDeal/addActiveDeal.py`,
  `BL/activeDeal/updateActiveDeal.py`, `BL/boughtDeal/addBoughtDeal.py`, `BL/boughtDeal/updateBoughtDeal.py`
  for BRRRR payloads (same HTTP 400 and message text as the analyzer).

### F2 (Medium) Broker points default differs between the analyzer (2%) and a saved deal (1.5%)
- `analyze_inputs.py:51` and `active_deal_schemas.py:36` default `refi_points` to 2; the ORM has
  `server_default='1.5'` (`activeDeal/deals.py:19`, `boughtDeal/deals.py:15`).
- `DAL/crud/active_deal.py:9` and `DAL/crud/bought_deal.py:9` dump with `exclude_unset=True`, so a POST without
  `refiPoints` (the MCP `add_active_deal` tool, any non-form client) stores 1.5 while `analyze_brrr` on the same
  body computes with 2: two different cash-out wires for one deal.
- Fix: drop `exclude_unset=True` from the four `add_*` dumps so the Pydantic defaults (the same ones the analyzer
  uses) always reach the row. Keep the 1.5 DDL default for the already-backfilled rows.

### F3 (Medium) ROI / CoC sentinels hide real numbers  [owner decision: leave as is]
- `deal_math.py:111-114`: ROI returns -2 ("undefined") whenever monthly cash flow <= 0, although its numerator
  (12 x cash flow + net profit) is well-defined. A high-equity deal with -$50/month shows "-inf%" on the card, in
  the PDF and in MCP rankings (`compact._metric` drops it).
- `deal_math.py:106-114`: both return -1 (infinite, rendered green) when cash out >= 0 even if cash flow is
  negative.
- Owner chose to keep today's behaviour. No code change; the existing field descriptions already state the
  rule ("-2 means not applicable (cash flow is 0 or negative)"). Recorded here so it is a known convention.

### F4 (Medium-low) The legacy hard-money flag can silently set the construction budget
- `ReqRes/common/brrr_legacy_inputs.py` fills `constructionLoanBudget` = rehab x (1 + contingency) whenever the
  payload has `use_HM_for_rehab: true` and no non-null budget key. The form still renders that toggle
  (`DealInputsForm.vue:396`), blank deals default it to true (`dealUtils.ts:166`), and clearing the budget field
  omits the key (`DealInputsForm.vue:138-141`). Result: a cleared budget becomes a full-rehab budget, Stolen
  Money reads 0 instead of -rehab, and the analyze response never echoes the budget so nothing shows it.
- Fix: apply the shim only to genuinely legacy payloads (none of the lifecycle keys such as `earnestMoneyDeposit`
  / `rehabCushion` present). Note for the frontend (out of scope here): the toggle should go.

### F5 (Low) Utilities are not capped at the refi while the rent offset is  [owner decision: skip]
- `brrrSteps/hml_and_holding_costs.py:32` bills `monthly_utilities x days_until_rented / 30`;
  `timeline.py:36` caps the rent side at `days_until_refi`. With a tenant placed after the refi (the
  `tenant_after_refi` scenario: 400 vs 180 days) 400 days of utilities land in "Total Cash Invested (pre-refi)".
- Left as is per the owner; noted only.

### F6 (Low) The Cash Needed floor counts the prepaid interest twice when a closing date is set  [owner decision: fix]
- `brrrSteps/total_cash_needed.py:24-27` adds 30 days of hard-money interest to a floor that already contains
  `cash_to_close_buy`, which holds the prepaid slice (closing day through month end). Closing on the 10th puts
  about 52 days of interest in "day one plus the first month"; in cash terms nothing more is due until the 1st
  of the month after next.
- Fix: `hml_interest_first_month_days = max(0, 30 - hml_interest_days_prepaid_at_purchase_closing)` (30 when
  undated, so the pinned legacy figure `EXPECTED_LEGACY_BRRRR_CASH_NEEDED` is untouched); expose the day count on
  `CashNeeded` / `BrrrResultsWithIntermediates`, update the explain guard and label ("HML Interest (rest of the
  first month)") at `explain/brrr.py:388-392`, and the field description in `analyze_results.py:63-68`.

### F7 (Low) Rate columns round eighth-point rates  [owner decision: widen]
- `interest_rate`, `HML_interest_rate`, `refi_points`, `down_payment`, `ltv_as_precent` are `Numeric(5, 2)`
  (`DAL/data_models/common/base_deal.py:48`, `activeDeal/deals.py:19,24,25`). A 7.125% DSCR rate is stored as
  7.13: the saved deal's payment, prepaid interest and cash flow differ from the analyzer's by cents, and the
  input shown back to the user is not what was typed.
- Fix: widen to `Numeric(6, 3)` with a migration step modelled on `migrations/steps/widen_money_columns.py`.

### F8 (Low) `/analyze/brrr` silently ignores snake_case field names
- `analyzeBRRRReq` (`analyze_inputs.py:12`) has no `populate_by_name=True`, unlike the saved-deal model
  (`base_deal.py:50`). A body written with the field names (`days_until_refi`, `earnest_money_deposit`) is
  ignored and the defaults apply, with a 200 response. Fix: `model_config = ConfigDict(populate_by_name=True)` on
  `analyzeBRRRReq` and `analyzeFlipReq`.

### F9 (Low) The PDF prints -$1 / -$2 as infinity  [owner decision: skip]
- `BL/reports/common/deal_pdf.py:58-61`: `_money` decodes -1/-2 as the percent sentinels. Left as is per the
  owner; noted only.

### Verified correct (no change)
Settlement sources = uses; interest split adds back exactly; seller tax proration and the tax-bucket
set-aside; reserves lower the wire and raise equity 1:1; Cash Needed = max(floor, through-refi); the
lowest-ARV wire never exceeds the baseline when validation runs; `Numeric(14,4)` thousands columns are exact to
the dime; the months to days migration is value-preserving; ORM `Numeric` returns `Decimal`; every save path
refreshes the row before recomputing (so JSON-mode strings never reach the engine).

## Todo

Each item ends with its unit / integration tests (see the test matrix).

- [x] Environment: `pip install -r BackEnd/requirements.txt`; run `pytest` in `BackEnd/` to get a green baseline (10 min)
- [x] Copy this plan to `tasks/todo/BrrrAnalysisBugAudit.md` on the branch (5 min)
- [x] F1 save-time validation: `validate_brrr_inputs_for_saved_deal` + wire into the four BRRRR save paths (45 min)
- [x] F2 drop `exclude_unset=True` from `add_brrr_deal`, `add_flip_deal`, `add_bought_brrr_deal`, `add_bought_flip_deal` (15 min)
- [x] F4 restrict `construction_budget_from_legacy_hm_flag` to payloads without lifecycle keys (20 min)
- [x] F6 floor interest = 30 days minus the prepaid days: `total_cash_needed_step`, results record field, explain guard + label, result description (25 min)
- [x] F7 `Numeric(6,3)` on the five rate columns (both BRRRR tables, flip tables for the shared `down_payment` / `HML_points` / `HML_interest_rate`) + `migrations/steps/widen_rate_columns.py` + `migrations/runner.py` hook + `test_migrations.py` (40 min)
- [x] F8 `populate_by_name=True` on `analyzeBRRRReq` / `analyzeFlipReq` (10 min)
- [x] MCP support task (below) (20 min)
- [x] Security task (below) (20 min)
- [ ] Run the full backend suite, frontend unit tests and the Playwright checks; re-record the goldens F6 moves (30 min)
- [ ] Push the branch and open the PR (10 min)

## Tests by layer

Unit (`BackEnd/tests`)
- `test_brrr_lifecycle.py`: floor interest equals 30 days minus the prepaid days when dated and 30 days undated, and `EXPECTED_LEGACY_BRRRR_CASH_NEEDED` still holds (F6); `test_the_explanation_holds_on_every_scenario` keeps passing.
- New `test_saved_deal_validation.py`: blank deal (zeros) passes; `loanTermYears 0`, `lowestArv > arv`, `down_payment 150`, negative closing line each raise 400 with the existing messages (F1).
- `test_brrr_lifecycle.py`: the legacy shim fires on a payload with only legacy keys and does not fire when any lifecycle key is present (F4).
- `test_analyze.py`: snake_case body equals alias body to the last digit (F8).

Integration (`TestClient`, `test_deal_crud.py`)
- POST `/active-deals` without `refiPoints`, then compare `cash_out_routi` to POST `/analyze/brrr` on the same body: equal (F2).
- PUT with `loanTermYears: 0` returns 400 and `GET /active-deals` still lists every deal (F1).
- Bought deal PUT with `lowestArv > arv` returns 400 (F1).
- F7: `test_migrations.py` asserts the five columns reflect at scale 3 after the runner; a saved 7.125 reads back as 7.125.

E2E (`frontend/e2e`)
- Existing Playwright flows and golden checks run; the Cash Needed goldens (`frontend/e2e/golden`, re-recorded in commit 2c45cd2 for the floor steps) may move for dated fixtures because of F6, so re-record them with the repo's script only if they do and tick the plan.
- Manual: MCP `analyze_brrr` and `add_active_deal` with the same body report the same wire.

## MCP server support task
- The result shape gains nothing new for MCP except the F6 label/description change on `total_cash_needed_for_deal` (`ReqRes/common/analyze_results.py`); `tests/test_mcp.py` fails on an undocumented output field, so run it.
- `tests/test_mcp_tools.py`: `add_active_deal` then `get_deal` equals `analyze_brrr` on the same body (F2 through the MCP path).
- No new endpoint, so no new tool.

## Security task
From `.claude/security.md`: "Please check through all the code you just wrote and make sure it follows security best practices. make sure there are no sensitive information in the frontend and there are no vulnerabilities that can be exploited throughout all the code in this repo."
- Review the new validator for error-message content (no echoing of raw input), the migration DDL for injection (constant identifiers only, as the existing steps), and confirm no new fields leak to the frontend bundle.

## Verification
1. `cd BackEnd && pytest -q` all green; `python verify_regression.py verify` to see which goldens moved and confirm each is an intended F-item.
2. `cd frontend && npm test` and the Playwright checks.
3. Against the live database (read-only, Render MCP `query_render_postgres`): count BRRRR rows that the new save-time validator would reject (`loan_term_years <= 0`, `lowest_arv_in_thousands > arv_in_thousands`, percents outside 0-100, negative dollar lines) so the owner can fix any before the deploy blocks their PUT.
4. Post-deploy: open the board, the PDF for one deal, and MCP `portfolio_summary`; the cards for a deal with no closing date must be unchanged, the F-items only move where predicted.
