# CashNeededSchedule: a dated cash schedule next to Cash Needed (Lowest ARV)

Committed first as `tasks/todo/CashNeededSchedule.md` on the designated branch `claude/blissful-clarke-t18u4a` (it stands in for a `<task_name>` branch from latest `main`, as the earlier plans did). Each box is ticked as its work lands. Goldens change only in commits whose message starts with `Golden update:`.

## Context

Cash Needed (`total_cash_needed_for_deal`) is one number today. Nobody can see when that money actually leaves or comes back. A later version will import the cash flows into the liquidity timeline. This change adds a dated, row-per-item **cash schedule for the Lowest-ARV scenario** next to that number: on the analyze response, in the MCP tools, the HTML report, the PDF and the site's breakdown popup. Every row maps 1:1 to a future `LiquidityTransaction` (`frontend/src/types/liquidity.ts`). The rehab cushion becomes a future reserve window. To make the dates real:
- `contract_date` (new) and `buy_closing_date` become mandatory.
- The monthly items move from "days ÷ 30" to real 1sts.
- The Cash Needed floor is deleted.

The liquidity import itself is **not** built.

## Decisions (from the Q&A)
- **Rounding:** every `signed_amount_dollars` is a `Decimal` rounded to the cent. `total_cash_needed` itself is rounded to the cent (ROUND_HALF_UP) in the engine. The rows use **cumulative rounding** in schedule order: row = round(running exact sum) − round(previous running sum). So Σ rows == −(total_cash_needed − rehab cushion) **exactly**. This holds whenever the cushion is whole cents, which is always true for saved deals (`Numeric(12,2)`).
- **Order within a day:** money-out rows first, then money-in rows, each group in the fixed catalogue order below. The refi rows keep the order you gave.
- **Refi on a 1st:** that month's HML interest goes **inside the payoff**, not into a monthly row. HOA, insurance B, utilities and rent still land on the refi date (their windows are (A, refi]), money out before money in.
- **item_key** is the item **type** (shared by its monthly rows). `(item_key, date)` is unique per row, and a test checks that. Appraisal and survey are **two** rows.
- **Appliances:** closing + 2 calendar months, clamped to the last day of a shorter month (Dec 31 → Feb 28/29), then the earlier of that date and the refi date.
- **HTTP codes:** a missing date is a Pydantic 422. An ordering violation is a 400, like every existing rule in `validation.py`.
- `active_deals` and `bought_brrrr_deals` hold BRRRR only (flips live in `flip_deals`), so both date columns can become `NOT NULL`.

## Design

### 1. Mandatory dates (first)
- `ReqRes/common/brrr_lifecycle_inputs.py`: `contract_date: date` (alias `contractDate`) and `buy_closing_date: date` with no default, so they are required in `analyzeBRRRReq`, `BrrrActiveDealCreate` and the bought models. Missing → 422.
- `DAL/data_models/common/brrr_lifecycle.py`: `contract_date = Column(Date, nullable=False)`; `buy_closing_date` becomes `nullable=False`.
- New migration step `migrations/steps/brrr_contract_date_and_required_buy_closing_date.py`, registered in `migrations/runner.py`, idempotent, for both tables:
  1. Backfill the closing date first: `UPDATE … SET buy_closing_date = COALESCE(buy_closing_date, created_at::date + 7)`.
  2. Add `contract_date` via `add_column_if_missing` with backfill `LEAST(created_at::date, buy_closing_date)`. A deal entered after its closing (closing earlier than `created_at`) then still satisfies contract ≤ closing.
  3. `ALTER COLUMN … SET NOT NULL` on both columns.
  - `test_migrations.py` asserts: a NULL closing → created_at + 7 and contract = created_at; a closing earlier than created_at → contract = that closing date.
  - Also update the docstring of `brrr_lifecycle_columns.py`, which says the date "stays NULL".
- Validation (`BL/analyze/common/validation.py`, `_brrr_range_and_sign_errors`, so both the calculator and the saved-deal gates get it):
  - "Contract date must be on or before the buy closing date."
  - "Rehab completion must be on or before the refi closing date." (`days_until_rehab_completed ≤ days_until_refi`)
  - Unchanged: buy closing ≤ rehab completed (days ≥ 0) and rehab ≤ tenant occupied.
  - Old deals that break a rule fail on their next save.
- Frontend `src/utils/dealInputValidation.ts` mirrors these rules (`invalid` kind: red + shake + blocks the save/analysis, the existing mechanism). The field gets an error if either date is cleared.
- `contractDate` is added to:
  - `types/index.ts`
  - `BuySection.vue`: a date input next to Closing Date, in the same anatomy
  - `dealInputPhaseTabs.ts` (buy tab)
  - `brrrInputImpacts.ts`
  - `deal_input_sections.py` (the report inputs)
  - `dealUtils.ts` text export
- New-deal defaults in `dealUtils.ts`: `contractDate: todayIsoDate()` and `buyClosingDate: todayIsoDate() + 7` (via `addDays`). The engine never reads `today()`.
- **Remove the no-date mode everywhere:**
  - `timeline.py` (the `None` branch; `Timeline` dates become `date`)
  - `property_tax_bucket.py` (days ÷ 30 fallback)
  - `closing_costs_buy.py` (`None` → `seller_paid_current_year_taxes: bool`)
  - `explain/brrr.py` (`has_buy_closing_date` and every "No buy closing date →" text)
  - `deal_input_sections.py` `_has_buy_closing_date`
  - `brrrAutoCalc.ts` (null-date branches and their comments)
  - the record docstring and `Optional[date]` on `BrrrResultsWithIntermediates`
  - `refi_closing_date` / `tenant_occupied_date` / `rehab_completed_date` on `analyzeBRRRRes`, which become required `date`
- **Tests removed:**
  - every `no_date` scenario (`test_explain.py`, `test_brrr_lifecycle.py`, `test_brrr_deal_reconciliation_inputs.py`)
  - `test_deal_crud.py::test_no_date_…`
  - `test_report_pdf.py` `no_buy_closing_date`
  - `test_report_deal_inputs.py` undated
  - `test_brrr_lifecycle.py::…test_reproduces_the_pinned_legacy_figures`
  - `LEGACY_EQUIVALENT_OVERRIDES` and the `legacy_brrrr_payload` fixture (`tests/conftest.py`)
  - `EXPECTED_LEGACY_*` and `test_180_days_reproduces_the_old_6_month_result` (`test_analyze.py`); `EXPECTED_BRRRR_CASH_FLOW` becomes its literal value
- `test_migrations.py`: the "date stays unknown" test becomes "contract = created_at, a NULL closing = created_at + 7, both NOT NULL".
- Payloads get `contractDate` (and dates where they had none):
  - `conftest.py` and `verify_regression.py` `BRRRR_PAYLOAD`: `"contractDate": "2026-01-03"`
  - `no_date_cash_rehab` → `cash_rehab_dated` with `buyClosingDate="2026-04-15"`
  - `one_day_refi` gets `daysUntilRehabCompleted=1`, so it stays a valid edge case under the new rule
  - the e2e `fixtures/payloads.ts` / seed
- MCP `INSTRUCTIONS`: "contractDate and buyClosingDate are required for BRRRR (ISO dates); contract ≤ closing ≤ rehab completed ≤ refi; rehab completed ≤ tenant occupied."

### 2. Engine changes
- `deal_math.py`:
  - `first_of_month_dates(after_day, through_day)`: the 1sts in (after, through]. It is a sibling of `property_tax_bucket_deposit_dates`; both use a shared `day_of_month_dates(after, through, day_of_month)`.
  - `add_calendar_months_clamped(day, months)`.
  - `round_to_cents(value)` (ROUND_HALF_UP).
- `timeline.py` gains date tuples (counts are `len()` of them):
  - `first_of_month_dates_after_closing_through_refi`: HOA and insurance B
  - `utility_bill_dates_until_refi`: the 1sts in (closing, min(tenant, refi)], plus the next 1st if it is ≤ refi
  - `rent_collection_dates_before_refi`: the 1sts in (tenant, refi]
  - `hml_interest_monthly_payment_dates`: the 1st after each full month strictly after the purchase month whose 1st falls **strictly before** the refi
  - **HML split change:** a month whose payment 1st is on or after the refi goes into `hml_interest_days_accrued_into_refi_payoff`. On refi Jul 1 it carries June's 30 days. Otherwise it is unchanged (refi.day − 1).
  - `days_tenant_occupied_before_refi` is replaced by the rent dates.
- `hml_and_holding_costs.py`:
  - `hoa_dues_until_refi` = n × HOA
  - `utilities_until_rented` = n × utilities
  - `pre_refi_rental_income` = n × rent
  - No proration, no remainder.
- `insurance.py`: `insurance_step(payload, timeline)`; `insurance_paid_monthly_until_refi` = n × monthly.
- `property_tax_bucket.py` exposes `property_tax_bucket_first_bill_deposit_dates_until_refi` and `property_tax_bucket_later_deposit_dates_until_refi`; the counts become `len()`. Its math is unchanged.
- `total_cash_needed.py` drops the floor. It returns `total_cash_needed = round_to_cents(total_cash_invested + rehab_cushion + cash_to_refi_table_conservative + reserves_funded_from_own_pocket_at_lowest_arv)`, with no clamping (it may be negative).
- Removed from step, record, orchestrator mapping, explain, tests and descriptions:
  - `cash_needed_floor`, `cash_needed_floor_top_up`, `hml_interest_first_month_days`, `hml_interest_first_month`, `holding_costs_first_month`, `cash_needed_through_refi`
  - the explain steps "HML Interest (first month)", "Holding Costs (first month)", "Cash Needed Floor", "Floor Top-Up", "Cash Needed through Refi"
- The explain "Cash Needed" becomes an `add_sum` of the four terms, with the fold rounded to cents (a `rounded_to_cents` option on `CalcBreakdown.add_sum` in `common/calc_breakdown.py`).
- The texts of "HOA until Refi", "Insurance paid monthly until Refi", "Utilities until Rented", "Pre-Refi Rental Income" and "HML Interest paid monthly" now state "n × $x on the 1sts from … to …".
- Descriptions follow the new definitions: `analyze_results.py` (`total_cash_needed_for_deal`), the `mcp_server.py` glossary, README, the `types/index.ts` comment.
- `brrrAutoCalc.ts` mirrors the 1sts counts for `insurancePaidMonthlyUntilRefi`, `preRefiRentalIncome` and `utilitiesUntilRented` (`daysRentedBeforeRefi` → `rentCollectionCountBeforeRefi`). `brrrAutoCalc.test.ts` pins them.

### 3. The schedule (new step `brrrSteps/cash_needed_schedule.py`)
NamedTuples, Decimal math:
- `CashNeededScheduleRow(date, sequence_within_day, description, signed_amount_dollars, item_key)`
- `CashThatMustStayInAccount(item_key, description, amount_dollars, reserve_starts_on_date, reserve_ends_on_date)`
- `CashNeededScheduleAtLowestArv(dated_cash_rows, cash_that_must_stay_in_account, dated_cash_rows_net_outflow_dollars, cash_that_must_stay_in_account_total_dollars, total_cash_needed_dollars)`

The step builds the exact rows and drops zero amounts. It sorts by (date, out-before-in, catalogue order), applies cumulative rounding, and numbers `sequence_within_day`. It runs after `total_cash_needed_step`, and the record carries `cash_needed_schedule_at_lowest_arv`.

Catalogue (item_key → date, sign):
- `earnest_money_deposit`: contract_date, out
- `cash_to_close_buy`: buy_closing_date, out. It already holds the points, the prepaid interest, the seller credit, insurance A inside the closing and the closing costs; none of them gets its own row.
- `insurance_bill_at_purchase_outside_closing`: closing, out
- `stolen_money` when negative: closing, out
- `seller_tax_credit_set_aside_in_tax_bucket`: closing + 1 day, out
- `property_tax_bucket_deposit`: each first-bill 15th (or the Nov 30 fallback) ≤ refi, out
- `property_tax_bucket_deposit_after_first_payment`: each later 15th ≤ refi, out
- `property_tax_bucket_shortfall_topped_up_on_november_30`: that Nov 30, out
- `hml_interest_paid_monthly`: each payment 1st, out, = `calc_hml_interest(hml_amount, rate, days in the month paid for)`; description "HML interest for May 2026"
- `hoa_dues`, `insurance_paid_monthly_until_refi`: (closing, refi] 1sts, out
- `utilities`: the utility bill 1sts, out
- `maintenance_before_refi`: an equal split over the 1sts in (rehab completed, refi], with the last share taking the remainder; with no such 1st, the whole amount on the rehab completion date; out
- `appliances`: min(closing + 2 calendar months, refi), out
- `stolen_money` when positive: rehab completion date, in
- `appraisal_fee`, `survey_fee`: rehab completion date, out
- `pre_refi_rental_income`: the rent 1sts, in
- On refi_closing_date ("at the Lowest-ARV refi"), in this order and only when non-zero:
  - `cash_to_refi_table_conservative` (out)
  - `reserves_funded_from_own_pocket_at_lowest_arv` (out)
  - `insurance_bill_at_refi_outside_closing` (out)
  - `property_tax_bucket_balance_released_at_refi` (in)
- Never emitted: the refi wire, the full reserves transfer, insurance C inside the closing, the tax lump.

Hard rules, asserted in the step and in tests:
- No money-out row falls after the refi date.
- `(item_key, date)` is unique.
- The HML rows add up to `hml_interest_paid_monthly` to the cent.
- Σ signed == −(total_cash_needed − cushion).

### 4. Must stay in the account
The single entry is `rehab_cushion`: the amount, from buy_closing_date to rehab_completed_date. It is never a dated row. It is modelled as a reserve window, so it can later raise `reserve_k` for those dates.

### 5. Summary and surfaces
- **Summary:** dated rows total (net out) + rehab cushion = Total Cash Needed. No running balance, no peak.
- **API:** `analyzeBRRRRes.cash_needed_schedule_at_lowest_arv` (nested Pydantic models with a description on every field; the Decimal is serialized as a JSON string). Saved-deal responses inherit it.
- **MCP:** `analyze_brrr`, `get_deal` and the get-deals tools carry it through the schemas. Add a glossary entry and say the dates are required.
- **Explain:** reads the schedule (keeping the every-field-read test green), `check`s the reconciliation, and adds a note on the "Cash Needed" step pointing to the schedule.
- **HTML report** (`deal_html_report.py`): on the Cash Needed card, a "Cash schedule (Lowest ARV)" table (date, description, amount), a "Must stay in the account" block and the summary lines. All text goes through `escape`. No new script.
- **PDF** (`deal_pdf.py`): the same three blocks as a table under the Cash Needed section.
- **Frontend:** new `CashNeededScheduleTable.vue`, shown by `CalculationBreakdownPopup.vue` when `metricKey === 'total_cash_needed_for_deal'` and the schedule is present (new prop wired from `ResultTileWithCalculationButton`). Types go in `types/index.ts`. Rows are shown in cents, with the same money formatter as `calculationStepFormat.ts`.

## Expected golden deltas (on purpose)
- **Base fixture** (close 2026-01-10, refi 2026-07-09, tenant 2026-04-10, $80 utilities, $2,600 rent, no HOA or insurance B):
  - Utilities: 90/30 × 80 = $240 → 4 bills (Feb 1, Mar 1, Apr 1 + May 1 arrears) = $320, **+$80**.
  - Rent: 3 × $2,600 (May 1, Jun 1, Jul 1) = $7,800, unchanged.
  - So total_cash_invested +$80, Cash Needed +$80 (plus sub-cent rounding), cash_out −$80, net_profit −$80, and ROI and CoC move with them.
  - The floor steps leave the breakdown.
- **Regression cases:**
  - `all_cash`, `no_rehab`, `ten_year_refi` fall from their floor to the plain sum.
  - `year_refi`: rent 9 × 2,600 vs 275/30 × 2,600 → −$433.33 rent, +$80 utilities.
  - `ten_year_refi`: rent 117 vs 118.67 months, −$4,333.33.
  - `one_day_refi`: utilities $240 → $0.
  - `with_hoa`: HOA 6 × 450 = $2,700, unchanged.
  - `dated_december_we_pay_all`: utilities +$80, rent unchanged.
  - `cash_rehab_dated` replaces the undated case.
  - Every case: the schedule is added, `contractDate` is added to the models goldens, and the OpenAPI marks both dates required.
- **Playwright:** the goldens that record a BRRRR response (`analyze-brrr-save.json`, the deal-report and bought-deal ones) are re-recorded. The frontend breakdown-tree test drops the pinned floor figure ($56,350.68) and walks Cash Needed → Total Cash Invested directly.

## Todo (≈ 9 h 50)
- [x] S1 (5 min) Commit this plan as `tasks/todo/CashNeededSchedule.md`.
- [x] S2 (60 min) Mandatory dates, backend: model, migration, validation, removal of the no-date branches in the engine, explain and report inputs, the MCP instructions; remove the undated and legacy tests and fixtures; add `contractDate` to the payloads.
- [x] S3 (45 min) Mandatory dates, frontend: Contract Date field, defaults (today / +7), validation mirror with red + shake + block, `brrrAutoCalc.ts` no-date removal, phase tab, impacts.
- [x] S4 (15 min) `Golden update:` the models/OpenAPI/calculations snapshots for the dates alone.
- [x] S5 (60 min) Engine: real 1sts (timeline dates, HOA/utilities/insurance B/rent), refi-on-1st HML into the payoff, floor deleted, Cash Needed rounded; explain texts; descriptions; `brrrAutoCalc.ts` mirror.
- [x] S6 (15 min) `Golden update:` calculations + OpenAPI after the engine change (deltas reviewed against the list above).
- [x] S7 (75 min) Schedule step + record + API models + explain guard.
- [x] S8 (75 min) Backend tests (below).
- [x] S9 (50 min) HTML report + PDF blocks and their tests.
- [x] S10 (60 min) Frontend popup table + types + vitest.
- [x] S11 (20 min) `Golden update:` regression snapshots with the schedule; Playwright re-record.
- [x] S12 (15 min) **MCP:** no new tool or endpoint. `analyze_brrr` / `get_deal` output schemas carry `cash_needed_schedule_at_lowest_arv` with field descriptions (`test_mcp.py` undocumented-field check). Instructions: both dates required and the schedule glossary. Manual `analyze_brrr` call checks that the rows add up.
- [x] S13 (20 min) **Security** (`.claude/security.md`: "Please check through all the code you just wrote and make sure it follows security best practices. make sure there are no sensitive information in the frontend and there are no vulnerabilities that can be exploited throughout all the code in this repo"):
  - re-read every touched file
  - the descriptions are server-built strings, but they still go through `escape` in the HTML report, `Paragraph`-safe escaping in the PDF and Vue text interpolation (no `v-html`)
  - the migration SQL is static (no interpolation of user data)
  - the new date inputs are validated by Pydantic
  - no secrets in the frontend
  - run `bandit -q -r . -x ./tests,./verify_regression.py -ll -ii` and `npm audit`
- [x] S14 (15 min) Final: `pytest`, `verify_regression.py verify`, `npm test`, `npm run build`, `npm run e2e`; push `-u origin claude/blissful-clarke-t18u4a`; open the PR.

## Tests by layer
**Unit** (`tests/test_cash_needed_schedule.py` new, plus `test_brrr_lifecycle.py` and `test_brrr_deal_reconciliation_inputs.py`):
- `first_of_month_dates` and `add_calendar_months_clamped` (Jan 31 + 2, Dec 31 + 2, a leap year).
- Section 2 counts:
  - base: utilities 4, rent 3
  - tenant after refi: rent 0, utilities stop at the refi
  - tenant on closing day: one arrears bill
  - refi on a 1st: HOA/insurance/rent rows on the refi date
  - HML refi on a 1st: June in the payoff
- HML rows:
  - close Apr 15 → no May 1 row, first row Jun 1 for May
  - their sum equals `hml_interest_paid_monthly` to the cent
- The floor is gone and Cash Needed is the four-term sum, rounded; a negative Cash Needed stays negative.
- **Reconciliation, exact** (Σ signed == −(total − cushion)) on these scenarios:
  - base
  - positive stolen money
  - negative stolen money
  - tenant after the refi
  - seller already paid (Oct/Dec closing)
  - full tax bill collected at refi (release row)
  - insurance A and C outside both closings
  - short hold with the refi inside the first month (Apr 15 → Apr 30 and Apr 15 → May 10)
  - refi on a 1st
  - Nov 30 inside the hold with a shortfall
  - Nov 30 fallback deposit
  - maintenance with no 1st after rehab
  - a negative cash to close
- **Invariants** on all of those:
  - no money-out row after the refi
  - out before in within a day
  - `(item_key, date)` unique
  - `sequence_within_day` 0..n−1 per date
  - the refi-day rows in the given order
  - no row for the wire, the reserves transfer, insurance C inside the closing or the tax lump
  - no cushion row
  - every row amount is whole cents
- Validation: contract > closing, rehab > refi, rehab > tenant → 400 messages; frontend `dealInputValidation.test.ts` mirror.

**Integration:**
- `test_analyze.py`: `POST /analyze/brrr` returns the schedule and its summary adds up; a missing `contractDate` or `buyClosingDate` → 422; an ordering violation → 400.
- `test_deal_crud.py` / `test_saved_deal_validation.py`: a saved deal carries the schedule and an invalid old deal fails on save.
- `test_migrations.py`: backfill + NOT NULL.
- `test_explain.py`: every field is read, the guards pass, the floor labels are gone.
- `test_report_html.py` / `test_report_pdf.py`: the schedule block renders, escaped, with the summary lines.
- `test_mcp*.py`: green, and the new fields are documented.
- `verify_regression.py snapshot` → review → `verify`.

**E2E** (`frontend/e2e`):
- re-record the BRRRR goldens; every other golden stays byte-identical
- a flow check: the popup for Cash Needed shows the schedule table, the "Must stay in the account" section and the summary
- a new deal is pre-filled with today / today + 7
- a contract date after the closing turns red, shakes and blocks the save

## Verification
- Setup as before: `pip install -r BackEnd/requirements.txt`; local Postgres 16 with `TEST_DATABASE_URL`; `cd frontend && npm ci`; Playwright with `PW_CHROMIUM_PATH=/opt/pw-browsers/chromium`.
- `cd BackEnd && pytest && python3 verify_regression.py verify`; `cd frontend && npm test && npm run build && npm run e2e`.
- Manual: analyze the base deal and open Cash Needed. The schedule should list:
  - EMD on the contract date and cash to close on Jan 10
  - the seller credit on Jan 11
  - tax deposits on the 15ths
  - HML interest from Mar 1 (for Feb)
  - utilities Feb 1 to May 1
  - appraisal and survey on Feb 24
  - appliances on Mar 10
  - rent May 1 to Jul 1
  - the Lowest-ARV refi rows on Jul 9

  Then check: the cushion shows under "Must stay in the account" (Jan 10 → Feb 24), and rows total + cushion = Cash Needed to the cent. The same blocks appear in the HTML report and the PDF.

## Review

- **Dates:** `contractDate` and `buyClosingDate` are mandatory (422 when missing; 400 for contract > closing or rehab > refi). Both columns are NOT NULL. The migration fills a missing closing with created_at + 7 first, then sets contract = the earlier of created_at and the closing. A new deal starts at today / today + 7. The no-date mode is gone from the engine, explain, reports, brrrAutoCalc and the tests.
- **Engine:**
  - HOA, insurance paid monthly, utilities (plus one arrears bill) and pre-refi rent are n x the monthly amount on real 1sts.
  - A refi on a 1st puts the month before it inside the HML payoff.
  - The floor is gone: Cash Needed = the four-term sum, to the cent, never clamped.
  - Golden deltas match the plan's list (base +$80 utilities; all_cash / no_rehab / ten_year_refi off the floor; year_refi and ten_year_refi rent; one_day_refi -$240).
- **Schedule:** `cash_needed_schedule_at_lowest_arv` sits on the analyze and saved-deal responses, the MCP tools, the HTML report, the PDF and the popup. Rows are whole cents, rounded on the running total item by item, so they add up exactly to Cash Needed less the cushion. The cushion is a "must stay in the account" window. 18 reconciliation scenarios check the totals exactly and each item within a cent; a mutation of the appliances amount was caught.
- **Also fixed:** the PDF result bookmark landed a page early once the Cash Needed tree got shorter, so the destination is now an anchor in the title. The all-steps list no longer sits in a KeepTogether that could leave a blank page.
- **Verification:** pytest green; `verify_regression.py verify` identical; vitest 1730 passed; build OK; Playwright chromium 123 passed (5 skipped; WebKit isn't installed here); bandit clean; npm audit 0.
