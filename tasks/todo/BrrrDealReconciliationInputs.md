# BrrrDealReconciliationInputs: make the calculator match 10th St and Ridgeway to the dollar

Branch: the session branch `claude/optimistic-albattani-fcz4nq`, restarted from the latest `main`. The owner
approved the plan in chat ("go ahead and implement the latest plan"); that approval is the review gate.

## Context

The owner reconciled two finished deals (10th St, Ridgeway: purchase and refi settlement statements plus the bank
transactions) against the engine. Five modelling gaps came out of it, plus one bug:

1. Insurance is one annual figure, accrued per diem. In practice it is a lump at the purchase closing, maybe a
   monthly payment until the refi, a lump at the refi closing, and a monthly figure in a regular year.
2. Appraisal and survey are paid outside the refi closing (POC on both refi statements), so they are not refi
   closing costs.
3. Property tax runs through a bucket. The seller credit goes in at closing. Deposits on the 15th fill it up to the
   Nov 30 bill (× 0.96 discount). Some refi lenders collect the whole bill at the refi.
4. The reserves (and a new HYSA deposit) are the owner's own money set aside. They are not held by the lender, so
   they don't come off the refi wire.
5. A rehab completion date, as groundwork for the dated cash-flow table.
6. Bug: both DSCR lenders quote per diem on a 360-day year, not 365.

## The guiding principle: two time horizons, never mixed

- **Purchase → refi outputs.** Cash to Close (Buy), Total Cash Invested, both Cash-Out Routi wires, stolen money,
  cash out, Cash Needed, equity and net profit. Every lump and every monthly payment made before or at the refi
  lands here.
- **Regular-year outputs.** Operating expenses, NOI, cash flow, PITIA, DSCR, CoC and ROI. They use only steady
  monthly figures: insurance d, and tax bill × 0.96 / 12.

## Design

### New inputs
They go in `ReqRes/common/brrr_lifecycle_inputs.py`, `DAL/data_models/common/brrr_lifecycle.py`, and one row each in
`migrations/steps/brrr_lifecycle_columns.py`.

| Column | Alias | Type | Default | Meaning |
| --- | --- | --- | --- | --- |
| `insurance_purchase_bill_payment_timing` | `insurancePurchaseBillPaymentTiming` | VARCHAR(30) | `inside_purchase_closing` | where insurance a is paid |
| `monthly_insurance_until_refi` | `monthlyInsuranceUntilRefi` | NUMERIC(12,2) | 0 | b, × days until refi / 30 |
| `insurance_bill_at_refi_closing` | `insuranceBillAtRefiClosing` | NUMERIC(12,2) NULL | null = a | c |
| `insurance_refi_bill_payment_timing` | `insuranceRefiBillPaymentTiming` | VARCHAR(30) | `inside_refi_closing` | where c is paid |
| `monthly_insurance_after_refi` | `monthlyInsuranceAfterRefi` | NUMERIC(12,2) NULL | null = c / 12 | d, regular year only |
| `seller_tax_credit_at_purchase_closing` | `sellerTaxCreditAtPurchaseClosing` | NUMERIC(12,2) NULL | null = proration formula | may be negative |
| `monthly_property_tax_bucket_deposit` | `monthlyPropertyTaxBucketDeposit` | NUMERIC(12,2) NULL | null = (bill × 0.96 − credit set aside) / 15ths left to Nov 30 | the deposit on each 15th |
| `property_tax_collection_at_refi` | `propertyTaxCollectionAtRefi` | VARCHAR(40) | `no_tax_collected_at_refi` | or `full_tax_bill_collected_at_refi` |
| `property_tax_lump_sum_at_refi_closing` | `propertyTaxLumpSumAtRefiClosing` | NUMERIC(12,2) NULL | null = the bill | used only with the full-bill option |
| `hysa_deposit_at_refi` | `hysaDepositAtRefi` | NUMERIC(12,2) NULL | null = 3 × monthly P&I | the fourth reserve |
| `days_until_rehab_completed` | `daysUntilRehabCompleted` | INTEGER | 45 | 0 ≤ days ≤ days until rented |

Existing fields that change meaning, without moving:
- `annual_insurance` becomes insurance a, "Insurance bill at purchase closing".
- `annual_property_taxes` becomes this year's bill.

Flip keeps both exactly as before.

### Engine

**Insurance**
- **a**
  - Inside the closing: a line of `closing_costs_buy_total`, so it lands in Cash to Close (Buy).
  - Outside the closing: a term of Total Cash Invested and of the Cash Needed floor.
- **b** × days until refi / 30 goes in Total Cash Invested.
- **c**
  - Inside the closing: a line of `closing_costs_refi_total` at both ARVs.
  - Outside the closing: Total Cash Invested.
- **d** (default c / 12) is `monthly_insurance`, the only insurance in the regular year.
- The BRRRR daily holding costs become HOA only. The first-month holding cost is HOA for 30 days + b + one tax deposit.

**Tax bucket** (new step `brrrSteps/property_tax_bucket.py`)
- **Bill paid on Nov 30:** bill × 0.96. The first Nov 30 is the closing year's, or the next year's after a December
  closing.
- **First-bill deposits** are made on the 15ths strictly after closing through that Nov 30.
  - The default amount is (bill × 0.96 − credit set aside) / count, floored at 0.
  - With no 15th left, there is one deposit, dated Nov 30.
- **Later deposits** start after a Nov 30 that falls inside the hold: bill × 0.96 / 12 on each 15th.
- **Until the refi:** deposits dated on or before the refi date count in Total Cash Invested. So does any shortfall
  topped up on a Nov 30 inside the hold.
- **Without a buy closing date:** the deposit default is bill × 0.96 / 12, and the count is days until refi / 30.
- **Full bill collected at the refi:**
  - The lump (default = the bill) is a line of `closing_costs_refi_total` at both ARVs.
  - The bucket balance at the refi (credit set aside + deposits − the Nov 30 payment if one was made) comes back,
    as a negative term of Total Cash Invested.
- **Regular year:** monthly taxes = bill × 0.96 / 12.
- **Seller credit:** the effective credit is the override, or else the formula.

**Appraisal and survey**
- They leave `_refi_settlement_lines` at both ARVs.
- They join Total Cash Invested as paid outside closing at the end of the rehab.

**Reserves**
- `reserves_total` = maintenance + vacancy + capex + HYSA (default 3 × P&I). The mortgage payment is now computed
  before the refi step.
- The wires no longer subtract the reserves.
- `cash_out = wire − reserves − Total Cash Invested`. Equity keeps `+ reserves`.
- Cash Needed through refi adds `reserves_funded_from_own_pocket_at_lowest_arv`
  = max(0, reserves − max(0, lowest-ARV wire)). That keeps the old figure for the old three reserves.

**DSCR per diem:** `DSCR_DAYS_PER_YEAR = 360`.

**Rehab completion:** `Timeline.rehab_completed_date`, also on the response.

### Validation
- **Non-negative:** every new dollar input except the seller credit override. Also days until rehab completed.
- **Cross-field:** rehab completed ≤ rented. It lives in `_brrr_range_and_sign_errors`, so it covers the calculator
  and the saved deals, and is skipped when either field is None.
- **Frontend:** the same rule in `dealInputValidation.ts`, so the field turns red, shakes and blocks save.
- **Old deals** with rented < 45 fail on their next save. That is the owner's call.

### Frontend
- **`brrrAutoCalc.ts` mirrors:**
  - a and c (inside the closing), and the tax lump, in the closing-cost totals;
  - appraisal and survey out of the refi costs;
  - the wires without the reserves;
  - the 360-day DSCR per diem;
  - the seller credit override;
  - the defaults for the tax deposit, d, HYSA and c;
  - the rehab completed date.
- **Form:**
  - Rent & Holding: the relabelled bill fields, the payment-timing picker, b, the tax deposit.
  - Refinance: c with its picker, d, the tax-collection option and lump, the outside-closing group for appraisal and
    survey, the reserves relabelled as the owner's, HYSA.
  - Rehab: rehab completion as a `DaysOrDateField`.
  - Buy: the seller-credit pencil now writes the override, with an "auto" reset.
- **Wiring:** types, defaults, impacts, phase tabs, copy-for-AI text, the store comment.

## Todo (≈ 9 h 30)
- [ ] R1 (10 min) Branch from `main`, this plan.
- [ ] R2 (90 min) Backend inputs, columns, migration rows, record fields, response fields with descriptions.
- [ ] R3 (120 min) Engine: insurance a–d and the pickers, the tax bucket step, appraisal/survey, owner-held
  reserves + HYSA, 360-day DSCR, rehab completed date. Explain narration and guards for all of it.
- [ ] R4 (30 min) Validation: new non-negative fields, the rehab ≤ rented rule.
- [ ] R5 (30 min) Report inputs (`deal_input_sections.py`), MCP `INSTRUCTIONS` prose.
- [ ] R6 (90 min) Backend tests (below), fixtures, the legacy parity overrides.
- [ ] R7 (120 min) Frontend: auto-calc mirror, sections, types, defaults, validation, impacts, phase tabs,
  copy-for-AI, Vitest.
- [ ] R8 (30 min) Golden update commits: backend snapshots, then the e2e network goldens if they move.
- [ ] R9 (20 min) Security pass.
- [ ] R10 (10 min) Push the branch and open the PR.

## Tests

**Unit**: `tests/test_brrr_lifecycle.py`, `tests/test_explain.py`, `brrrAutoCalc.test.ts`, the validation tests.
- Insurance:
  - Both pickers: a in Cash to Close (Buy) vs in Total Cash Invested; c in both wires vs in Total Cash Invested.
    Cash out is the same either way.
  - b, c and d each hit only their own horizon.
  - Defaults: d = c / 12 (Ridgeway 2,410.01 → 200.83; 10th St 1,343.46 → 111.96), and c = a.
- Tax bucket:
  - Deposit counts: 10th St (01/16 → 10 to Nov 30, 6 before a 07/17 refi). Ridgeway (04/29 → 7, 4 before 08/31).
    Also a Nov 30 inside the hold, a December closing, a Nov 16–30 closing, and no date.
  - The lump lowers both wires and releases the bucket.
  - Regular-year taxes are bill × 0.96 / 12.
  - The seller credit override.
- Appraisal/survey move, and cash out is unchanged.
- Reserves:
  - The wire excludes the reserves; cash out and Cash Needed are unchanged for the old three.
  - The HYSA default (Ridgeway 3 × 1,220.94 = 3,662.83).
- DSCR prepaid interest: 10th St 07/17 → 597.09; Ridgeway 08/31 → 36.54.
- Rehab completion: the date, and the bounds 0, = rented, rented + 1.
- The explain guards hold on every scenario.
- Legacy parity: still reproduced, with the new inputs neutralised.

**Integration**
- `test_deal_crud.py`: round trip of the new fields.
- `test_migrations.py`: the columns and their backfills.
- `test_saved_deal_validation.py`: the rehab rule on POST/PUT.
- `/analyze/brrr`: the response fields.
- MCP: the new fields in the tool schema.
- Regenerate the regression snapshots.

**E2E (Playwright)**
- Rehab completion after the rented date → red field, shake, save blocked; fixing it clears the error.
- The insurance pickers and the tax-lump option move the on-screen figures.

## MCP task
The new fields reach every tool through the route schemas. The `INSTRUCTIONS` prose in `mcp_server.py` describes:
insurance a–d and the pickers, the tax bucket and the refi lump option, HYSA, rehab completion, reserves as owner-held,
and the two-horizon rule.

## Security task
Please check through all the code you just wrote and make sure it follows security best practices. make sure there
are no sensitive information in the frontend and there are no vulnerabilities that can be exploited throughout all the
code in this repo

In this change specifically:
- Every new input is sign- and range-checked server-side, not only in the UI.
- The pickers are `Literal`-validated (422 on anything else).
- Notes and labels carry no deal data into error messages.
