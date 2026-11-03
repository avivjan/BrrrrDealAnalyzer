# SettlementStatementFloridaTitle: date defaults, tax-bill back-solve, $ reserves, insurance moves, Florida title estimate

Branch: the session's designated `claude/settlement-statement-florida-title-5k3j75`, cut from latest `main`. It stands in for a `<task_name>` branch, as in earlier plans. The first implementation commit copies this plan to `tasks/todo/SettlementStatementFloridaTitle.md`, and boxes are ticked there as work lands.

## Context
Seven owner fixes to the BRRRR form and engine after using it on real settlement statements, plus formula explanations for every closing-cost estimate.

**Owner decisions (asked and answered):**
- **Title mode:** the owner's policy is charged only in "We pay all closing costs". "Standard" = $600 office fees + the lender's policy; the seller pays the owner's policy there. On a $100k price with a $123k loan, that is **$1,540** with we-pay-all and **$965** with Standard.
- **"Loan Amount"** in the lender's excess surcharge = the whole hard-money loan (`hml_amount`: purchase loan + construction budget).
- **$ reserves:** all four percent-of-rent fields (Vacancy, Maintenance, CapEx, Property Management) take either a % or a monthly $ amount, through a clean % / $ toggle.
- **Closing date follows the contract date until edited:** a contract-date change moves the closing to contract + 10 only while the closing still sits at old contract + 10 (or is empty).
- **Item 6** moves the whole block, Insurance per Month after Refi plus the read-only "Property tax per month", to Rent & Holding, keeping its heading **"Regular year after the refi"**.

## Design

### 1–2. Date defaults (frontend only)
- `frontend/src/utils/dealUtils.ts:99`: `DEFAULT_DAYS_FROM_CONTRACT_TO_BUY_CLOSING = 10`. `contractDate: todayIsoDate()` is already the new-deal default (`:199`); a test pins it.
- `BuySection.vue` `onContractDate`: if the closing date is empty or equals `addDays(previousContractDate, 10)`, also set `buyClosingDate = addDays(newContractDate, 10)`. A hand-typed closing is never moved. Reuse `addDays` from `brrrAutoCalc.ts`.
- `defaultBuyClosingIsoDate` doc comment → "today + 10".

### 3. Editing the Seller Tax Credit updates the Property Tax Bill (frontend only)
- `BuySection.vue:79-83` `onSellerTaxCreditEdited`: keep writing the typed override (`sellerTaxCreditAtPurchaseClosing`). Also write `annual_property_taxes = annualPropertyTaxesFromSellerTaxCredit(typed, closingDay, sellerAlreadyPaid)` (`brrrAutoCalc.ts:203`, already exists and is tested) when it returns non-null. A Jan 1 unpaid closing returns null, and the bill is then left as is. Both tax-bill boxes (Buy clone and Rent & Holding) follow reactively. Update the doc comment at `:73-78`.

### 4. Monthly reserves in dollars (backend + frontend)
- New nullable inputs in the BRRRR lifecycle set (`ReqRes/common/brrr_lifecycle_inputs.py`, `DAL/data_models/common/brrr_lifecycle.py`, rows in `migrations/steps/brrr_lifecycle_columns.py`, a plain nullable add):
  | Column | Alias | Type | Meaning |
  | --- | --- | --- | --- |
  | `monthly_vacancy_reserve_dollars` | `monthlyVacancyReserveDollars` | NUMERIC(12,2) NULL | null = `vacancyPercent` × rent |
  | `monthly_maintenance_reserve_dollars` | `monthlyMaintenanceReserveDollars` | NUMERIC(12,2) NULL | null = `maintenancePercent` × rent |
  | `monthly_capex_reserve_dollars` | `monthlyCapexReserveDollars` | NUMERIC(12,2) NULL | null = `capexPercent` × rent |
  | `monthly_property_management_fee_dollars` | `monthlyPropertyManagementFeeDollars` | NUMERIC(12,2) NULL | null = `property_managment_fee_precentages_from_rent` × rent |
- Engine `BL/analyze/brrrSteps/operating_expenses.py`: `vacancy = effective(payload.monthly_vacancy_reserve_dollars, rent × pct / 100)`, and the same for maintenance, capex and management. Explain (`explain/brrr.py:124-127`) labels each term "Vacancy $X/month as entered" or "Vacancy 5% of rent". Validation: ≥ 0 (join `_BRRR_NON_NEGATIVE_DOLLARS`). The report input list (`reports/common/deal_input_sections.py`) gains the four fields, and shows "$X/mo" or "Y% of rent" per reserve.
- Frontend: types, `BRRR_LIFECYCLE_DEFAULTS` (null), copy-for-AI lines, impact map (same outputs as the % key), `dealInputPhaseTabs.ts` rentHolding keys.
- New small `components/ui/PercentOfRentOrMonthlyDollarsInput.vue`:
  - **Look:** the existing input styling (`ui-input`, the label row with ⓘ), plus a compact two-segment pill toggle `% | $` aligned right in the label row. It uses design tokens (`rounded-ctl`, `bg-surface-3`, the active segment `bg-primary text-on-primary`) and is the same height as the label row, so the 4-column grid stays aligned.
  - **Inside the box:** in % mode the suffix is "%"; in $ mode the prefix is "$" and the suffix "/mo".
  - **Muted note under the box:** in % mode it shows the other unit, `≈ $X/mo`; in $ mode it shows `≈ Y% of rent`. Both values are always visible without clutter.
  - **Behaviour:**
    - Switching to $ seeds the dollar field with rent × % (rounded to cents).
    - Switching to % sets the dollar field to null and seeds the % back from dollars ÷ rent, when rent > 0.
    - The toggle is a `role="radiogroup"` with labelled buttons (keyboard and axe friendly).
  - `RentHoldingSection.vue:489-526` uses it for all four (Vacancy, Maint., CapEx, Prop. Mgmt).

### 5–6. Insurance fields move tabs (frontend only)
- Move `annual_insurance` ("Insurance Bill at Purchase", keeps `needed-to-run-analysis`) and `insurancePurchaseBillPaymentTiming` ("Insurance Bill Paid") from `RentHoldingSection.vue:451-470` into `BuySection.vue`'s Closing Costs (Buy) block. They sit next to the total, whose hint already names the insurance bill.
- Move the "Regular year after the refi" block (`RefinanceSection.vue:563-578`) to the end of `RentHoldingSection.vue`, as its own sub-section with the same `UiSectionHeader` title **"Regular year after the refi"**, placed next to the four reserves it shares the regular-year operating expenses with.
- Update `NEEDED_FIELDS_BY_PHASE_TAB` (`DealInputsForm.vue:190`: `annual_insurance` goes rentHolding → buy) and `config/dealInputPhaseTabs.ts` (`annual_insurance` and `insurancePurchaseBillPaymentTiming` go to buy; `monthlyInsuranceAfterRefi` goes to rentHolding). Update both sections' doc comments.

### 7. Florida title & escrow estimate (backend + frontend mirror)
- `BL/analyze/common/deal_math.py`: replace `TITLE_ESCROW_BUY_STANDARD` / `_WE_PAY_ALL*` with named constants:
  - `TITLE_SETTLEMENT_CLOSING_FEE = 350`, `TITLE_SEARCH_FEE = 150`, `MUNICIPAL_LIEN_SEARCH_FEE = 100`
  - `FLORIDA_OWNERS_POLICY_RATE_PER_THOUSAND_UP_TO_100K = 5.75`, `FLORIDA_OWNERS_POLICY_RATE_PER_THOUSAND_ABOVE_100K = 5.00`, `FLORIDA_OWNERS_POLICY_FIRST_TIER_UPPER_BOUND = 100000`
  - `LENDERS_POLICY_ENDORSEMENTS_AND_SIMULTANEOUS_ISSUE_FEE = 250`, `LENDERS_POLICY_EXCESS_LOAN_RATE_PER_THOUSAND = 5.00`

  New functions:
  - `florida_owners_title_policy_premium(purchase_price)`: price ≤ 100k → price/1000 × 5.75; otherwise 575 + (price − 100k)/1000 × 5.00.
  - `lenders_title_policy_and_endorsements(loan_amount, purchase_price)`: 250 + max(0, loan − price)/1000 × 5.00.
  - `title_escrow_buy_itemized_default(title_mode, purchase_price, hml_amount) -> TitleEscrowBuyItemizedDefault` (NamedTuple: `settlement_closing_fee`, `title_search_fee`, `municipal_lien_search_fee`, `owners_title_policy_premium` (0 on Standard), `lenders_title_policy_and_endorsements`, `total`).

  `title_escrow_buy_default` becomes `.total`.
- `closing_costs_buy.py`: pass `hml_amount`. `BuySettlement`, the record, `analyzeBRRR.py` mapping and the response (`ReqRes/common/analyze_results.py`, described) gain `title_office_and_search_fees_buy`, `owners_title_policy_premium_buy` and `lenders_title_policy_and_endorsements_buy` (the formula's itemization; the total stays `title_escrow_buy`, so an override still wins). Update the `title_mode_buy` / `title_escrow_buy` descriptions (`brrr_lifecycle_inputs.py:54-58`).
- **Breakdown popup** (`explain/brrr.py`, replacing `_title_escrow_buy_formula` at `:75-91` and the step at `:245-250`): three child steps under CLOSE, each with a formula and a plain-English note.
  - Office fees: "$350 settlement + $150 title search + $100 municipal lien search = $600".
  - Owner's policy: "Florida promulgated rate (F.A.C. 69O-186.003): $5.75 per $1,000 up to $100,000, $5.00 per $1,000 above: …"; on Standard: "$0: the seller pays the owner's policy".
  - Lender's policy: "$250 base (Florida ALTA 8.1, Form 9, simultaneous-issue rate) + $5.00 per $1,000 of the loan above the price ($123,000 − $100,000 = $23,000 → $115) = $365"; or "$250 flat: the loan does not exceed the price".

  `Title & Escrow (Buy)` becomes an `add_sum` of the three when it is on the formula, with each `check()` guard. "As entered" stays when it is typed. `wePayAllExtraClosingCost` (UI) is now the owner's policy + deed tax.
- **Near the input** (`BuySection.vue:266-274`): while `titleEscrowBuy` is on its default, the same three lines with the deal's numbers show under the input, through the shared mechanism in §8. They are hidden once a dollar amount is typed. The we-pay-all hint (`:261-264`) says "owner's title policy + 0.70% deed transfer tax".
- Frontend mirror (`utils/brrrAutoCalc.ts:161-171`): `floridaOwnersTitlePolicyPremium`, `lendersTitlePolicyAndEndorsements`, `titleEscrowBuyItemizedDefault(titleMode, price, hmlAmount)`, and `BrrrAutoCalc.titleEscrowBuyItemizedDefault`.
- MCP: `mcp_server.py` glossary gets one sentence on the Florida title estimate (within the `tools/list` budget).

### 8. Explain every closing-cost estimate, in the popup and next to its input
This covers four inputs: Title & Escrow / Settlement (Buy), Recording & Transfer (Buy), Title & Escrow / Settlement (Refi) and Recording & Transfer (Refi). Their engine formulas are unchanged, except the buy title (§7).
- **Near the input:** `components/ui/AutoDefaultMoneyInput.vue` gains an opt-in `estimateExplanation?: string` prop. It renders as `<p data-part="estimate-explanation">` under the box **only while the field is on its formula default** (`modelValue == null`), and disappears the moment a dollar amount is typed (it comes back on "auto" reset). The text is built once, in a new `utils/closingCostEstimateExplanations.ts` with one function per line, fed the deal's numbers from `brrrAutoCalc`:
  - `titleEscrowBuyEstimateExplanation(itemized)`: the three Florida lines of §7. This replaces the ad-hoc `<p>` described in §7.
  - `recordingTransferBuyEstimateExplanation(hmlAmount, deedTransferTax, total)`: "$250 recording (deed, mortgage, LLC affidavit) + 0.55% of the whole hard-money loan $X (0.35% + 0.20% on the mortgage recorded: purchase loan + construction budget) + deed transfer tax $Y (0.70% of the price only when we pay all closing costs, else the seller's) = $Z".
  - `recordingTransferRefiEstimateExplanation(refiLoan, total)`: "0.55% × refi loan $X (0.35% + 0.20% on the mortgage recorded) + $250 recording = $Z".
  - `titleEscrowRefiEstimateExplanation(refiLoan, total)`: "$800 flat + 0.45% × refi loan $X = $Z". The refi loan is the one at ARV, which the input's default uses.

  Wired in `BuySection.vue:243-251, 266-274` and `RefinanceSection.vue:158-175`. The input's ⓘ tooltip stays the impact list.
- **Breakdown popup** (`BackEnd/BL/analyze/explain/brrr.py`): the formula lines exist today (`:239-242` buy recording, `:432-438` refi recording and title). Each gets a fuller `note` with the same wording as the hint: what the $250 covers, that the 0.55% is 0.35% + 0.20% on the loan recorded, the deed-tax rule, and the refi title's $800 + 0.45%. When the input is typed, the step keeps "As entered: $X" and the note says it overrides the estimate (`_default_note`). This applies to the Lowest ARV refi variants too. Formula strings stay pinned by the `check()` guards; only `note` text changes.

### Numbers that move
Every BRRRR deal on the title default: Standard $1,000 → $850 + excess-loan surcharge; we-pay-all from the tier to the full formula. That moves the closing costs, Cash to Close, Cash Needed, net profit, ROI and cash-on-cash results. Re-record the backend goldens (`verify_regression.py snapshot`: calculations, openapi, models) and the Playwright goldens. Every diff is reviewed so that only title-sized moves and the new fields appear.

## Todo (≈ 8 h 25)
- [ ] T1 (10 min) Copy the plan to `tasks/todo/SettlementStatementFloridaTitle.md`; commit.
- [ ] T2 (60 min) Backend title: constants, functions and itemized NamedTuple; step, record, response and descriptions; explain child steps, `add_sum` and notes.
- [ ] T3 (45 min) Backend $ reserves (all four): inputs, DAL columns, migration rows, `operating_expenses_step`, explain labels, validation, report input section.
- [ ] T4 (50 min) Backend tests.
  - **Unit** (`test_brrr_lifecycle.py`):
    - `test_florida_title_we_pay_all_100k_price_123k_loan_is_exactly_1540`
    - `test_florida_title_standard_100k_price_123k_loan_is_965_without_owners_policy`
    - `test_owners_policy_premium_at_80k_is_460_and_at_250k_is_1325`
    - `test_lenders_policy_is_250_flat_when_loan_does_not_exceed_price`
    - `test_title_itemized_fields_sum_to_title_escrow_buy`
    - `test_typed_title_escrow_overrides_the_florida_estimate`
    - `test_monthly_vacancy_maintenance_capex_and_management_dollars_override_the_percent`
    - `test_null_reserve_dollars_keep_the_percent_of_rent`
  - **Integration:**
    - `test_explain.py`: every-field-explained, terms add up, and the three title steps linked under Title & Escrow.
    - `test_deal_crud.py`: round trip of the four reserve-dollar fields.
    - `test_migrations.py`: the new columns exist and are NULL.
    - `test_saved_deal_validation.py`: negative reserve dollars are rejected.
    - Then `verify_regression.py snapshot`, review the diff, and `verify`.
- [ ] T5 (40 min) Frontend calc and the title explanation: `brrrAutoCalc.ts` mirror, BuySection explanation line and we-pay-all hint. **Unit** (`brrrAutoCalc.test.ts`): 1540 / 965 / 460 / 1325 / lender 250 parity with the backend numbers. `BuySection.test.ts`: the explanation shows on the default and hides once a value is typed. Update the breakdown parity fixture if it moves.
- [ ] T5b (45 min) Closing-cost estimate explanations (§8): the `estimateExplanation` prop on `AutoDefaultMoneyInput`, `closingCostEstimateExplanations.ts`, wiring on the four inputs, fuller explain notes in `explain/brrr.py`.
  - **Unit:**
    - `AutoDefaultMoneyInput.test.ts`: the explanation shows on the default, hides once a value is typed, and comes back on reset.
    - `closingCostEstimateExplanations.test.ts`: the exact strings for the fixture deal, e.g. buy recording on a $123k loan reads "$250 + 0.55% × $123,000 + $0 = $926.50".
    - `BuySection.test.ts` / new `RefinanceSection.test.ts`: each of the four inputs shows its line on the default and none when overridden.
  - **Integration:** `test_explain.py`: the four closing-cost steps carry a non-empty note naming their formula parts on the default, and "As entered" with the override note when typed.
- [ ] T6 (30 min) Dates + tax back-solve: `dealUtils.ts` +10; `onContractDate` follow-until-edited; `onSellerTaxCreditEdited` back-solve. **Unit:**
  - `DealInputsForm.test.ts` "+10 default", with `defaultBuyClosingIsoDate(new Date(2026, 11, 28)) === "2027-01-07"`.
  - `BuySection.test.ts`:
    - the contract date moves a default closing;
    - a hand-typed closing is not moved;
    - typing credit 177.53 on 2026-01-10 sets the tax bill to 7199.83 and keeps the override;
    - December paid: −167.67 gives 3600;
    - Jan 1: no pencil.
- [ ] T7 (60 min) $ reserves UI: `PercentOfRentOrMonthlyDollarsInput.vue` + test (radiogroup toggle, seeding both ways, back to % clears the dollars, the "≈" note in each mode, $0 rent keeps the % unchanged), wiring of all four in RentHolding, types, defaults, impact map, phase-tab keys, copy-for-AI. Check visually in light and dark at phone and desktop widths (Playwright screenshot).
- [ ] T8 (30 min) Tab moves: the insurance pair to Buy, the regular-year block to Rent & Holding, the needed-fields map and phase-tab keys. **Unit:** `DealInputsForm.test.ts` label lists per tab, the DOM-ordered needed list (`:254-263`) and tab dots updated; the Buy tab dot lights when `annual_insurance` is empty.
- [ ] T9 (60 min) **E2E** (Playwright):
  - update `seller-tax-credit-edit` (today + 10; typing the credit updates both tax-bill boxes);
  - new `flows/florida-title-estimate.spec.ts` (price 100k, rehab 23k at 0% down, we-pay-all → the title input default reads $1,540 and the explanation lists $600 / $575 / $365; opening the breakdown popup shows the three steps; typing a dollar amount in Recording & Transfer (Buy) hides its explanation, and the Refinance tab shows the refi title and recording explanations);
  - new `flows/monthly-reserve-dollars.spec.ts` (toggle Vacancy to $, type 75, analyze, the cash-flow breakdown shows "Vacancy $75.00/month as entered");
  - an insurance-on-the-Buy-tab assertion;
  - then `npm run e2e:record`, review the golden diffs, `a11y.spec.ts`, `npm run e2e`.
- [ ] T10 (15 min) **MCP**: no new tool or endpoint. The new inputs and result fields reach `analyze_brrr` / `get_deal` through the Pydantic schemas, the descriptions and a glossary sentence. `tests/test_mcp.py` (descriptions ≤ limits, `tools/list` budget, OpenAPI golden) stays green. Manual `analyze_brrr` with `titleModeBuy: we_pay_all`, price 100k, 23k rehab at 0% down → `title_escrow_buy == 1540` and itemized 600 / 575 / 365; `monthlyVacancyReserveDollars: 75` → `vacancy == 75`.
- [ ] T11 (20 min) **Security** (`.claude/security.md`: "Please check through all the code you just wrote and make sure it follows security best practices. make sure there are no sensitive information in the frontend and there are no vulnerabilities that can be exploited throughout all the code in this repo"):
  - Re-read every touched file.
  - The new inputs are bounded Decimals validated ≥ 0 on both sides; the migration is a static column list, with no string-built SQL from input.
  - No `v-html`, inline handlers or secrets in the frontend; the explanation text is rendered with interpolation only.
  - Run `bandit -q -r . -x ./tests,./verify_regression.py -ll -ii`, `pip-audit` and `npm audit`.
- [ ] T12 (20 min) Final: `cd BackEnd && pytest && python3 verify_regression.py verify`; `cd frontend && npm test && npm run build && npm run e2e`; tick the boxes; push `-u origin claude/settlement-statement-florida-title-5k3j75`; open the PR. It lists the ⚠ decisions and states that title defaults move every BRRRR result.

## Verification
- Backend: `pytest` (local Postgres 16, as in `tasks/todo/DealFormTabsAndDefaults.md`); `verify_regression.py verify` after the re-record.
- Frontend: `npm test`, `npm run build` (vue-tsc), `npm run e2e` (chromium).
- Manual (`npm run dev` + backend), Analyze BRRRR:
  - The contract date reads today and the closing today + 10; changing the contract moves the closing.
  - Pencil on the Seller Tax Credit → type the statement figure → both Property Tax Bill boxes update.
  - The Buy tab holds the insurance bill and its timing; Rent & Holding holds "Regular year after the refi".
  - Vacancy toggled to $ 75 gives cash flow lower by $75 − 5% × rent.
  - Price 100k, rehab 23k, 0% down, we-pay-all → Title & Escrow default $1,540 with the three-line explanation under it. "How is this calculated" shows Office fees $600, Owner's policy $575 and Lender's policy $365 with the statutory notes.
