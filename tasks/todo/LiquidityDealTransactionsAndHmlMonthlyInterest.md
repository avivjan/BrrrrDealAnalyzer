# LiquidityDealTransactionsAndHmlMonthlyInterest

On branch `claude/zen-brown-nv5tlv` with the open PR avivjan/BrrrrDealAnalyzer#125 (not merged), so that PR grows. The first commit is this plan, saved as `tasks/todo/LiquidityDealTransactionsAndHmlMonthlyInterest.md`. Goldens change only in `Golden update:` commits.

## Context
1. **Undoing an accidental Done on a deal row.** Today it's only possible through the toast's Undo, for about 4 seconds; after that a done row is hidden everywhere. You want each deal in the legend to show its whole story:
   - the Overdue section;
   - a **Transactions** section in place of "Open rows". It holds the important dates and every transaction, open and done, with done rows greyed out and struck through and an Undo on each.
   - Everything the Cash Needed table shows must be there.
2. **Monthly hard-money interest isn't always 1% of the loan.** Each monthly payment is calculated as loan × rate × the month's real day count ÷ 360 (`calc_hml_interest(hml_amount, rate, days_in_month(...))` in `BL/analyze/brrrSteps/cash_needed_schedule.py:150`). At 12% a 30-day month is 1.000%, a 31-day month 1.033%, February 0.933% (0.967% in a leap year).
   - **Decided in chat:** each full month is **loan × annual rate ÷ 12** (1% at 12%).
   - The partial first month (prepaid at the purchase closing) and the payoff month stay per day.

## Design

### A. HML monthly interest = loan × rate ÷ 12 (backend engine)
- **`BL/analyze/common/deal_math.py`:** new `calc_hml_monthly_interest_payment(hml_amount, HML_interest_rate)` = amount × rate ÷ 12 ÷ 100 (`MONTHS_PER_YEAR` already exists).
- **`BL/analyze/brrrSteps/hml_and_holding_costs.py`:**
  - `hml_interest_paid_monthly` = monthly payment × the number of monthly payment dates (`timeline.hml_interest_monthly_payment_dates`). Today it is "the remainder".
  - `prepaid_interest_buy` and `hml_interest_accrued_into_refi_payoff`: unchanged (per day, real days).
  - **`hml_interest` (total until the refi)** = prepaid + monthly + payoff. Today it is per day × `days_until_refi`.
  - `hml_per_diem` unchanged.
  - Cash Needed and the analysis's totals follow the total; the change is small (about ±1–3% of one month's interest per 31-day month or February).
- **`cash_needed_schedule.py`:** each "HML interest for <Month>" row uses the monthly payment, so every row is exactly 1% at 12%. Its total equals `hml_interest_paid_monthly`, so the internal test (Σ rows == −Cash Needed) still holds.
- **Explanation** (`BL/analyze/explain/brrr.py`): the `hml_interest` check becomes the sum of the three slices, and the breakdown text says "monthly = loan × rate ÷ 12; first and payoff months per day".
- **Unchanged:** the late-refi months (the same schedule rows), the refi payoff, and the flip analysis (it already uses monthly interest).
- **Existing deals:** recomputed on the next analysis. Imported liquidity rows of an existing deal get the new amount through the usual "liquidity out of date · Review changes" re-sync. No silent change to the rows.

### B. The legend's deal Transactions section (frontend + one backend field)
- **Backend:** `ImportedLiquidityDealRes` gains `key_dates: [{ key, date, description }]`, the Cash Needed table's markers (`deal_milestones_of_the_schedule`): contract signed, purchase closing, rehab completed, tenant moves in, the Nov 30 tax bill paid from the tax bucket (when inside the hold), refi closing.
  - `list_imported_deals` takes them from `compute_brrr_with_intermediates(deal).cash_needed_schedule_at_lowest_arv.deal_milestones`.
  - If the analysis fails, it falls back to the five milestones' planned dates.
  - MCP: the `list_liquidity_deals` description mentions `key_dates`.
- **`DealLegendPanel.vue`**, expanded deal:
  - **Overdue (N):** as now: Done, postpone, date, amount.
  - **Transactions (N):** replaces "Open rows". One merged timeline grouped by month and collapsible per month (each month shows its row count, its net and "N done"). The current month opens by default (or the first month, if the deal has no rows this month). It holds:
    - **Key dates:** a tinted, uppercase flag line, the same marker style as the Cash Needed table. Each milestone shows its state (✓ approved, overdue, planned) and opens its day on a click. The Nov 30 tax bill is a plain marker.
    - **Every row of the deal**, open and done, in date and day order. This is what the Cash Needed table lists, plus the timeline's own late-refi rows and rows kept because you changed them, each with a small icon.
      - **Open rows:** a click opens the day.
      - **Done rows:** greyed out, struck through, "done <date>" and an **Undo** button (`theater.legend.transaction.<id>.undo`).
- **Pure helper** `dealTransactionsTimelineByMonth(transactions, keyDates, milestones, dealKey)` in `theater/legendRows.ts`. It replaces `groupOpenRowsOfDealByMonth`; markers come first on their day.
- **Undo** emits `markNotDone(id)` through the theater to the view: `runQuickAction(() => store.markTransactionNotDone(id), 'Reopened.', () => store.markTransactionDone(id))`. The row counts again at once (overdue if its date has passed).
- **The day modal** (`theater/DayTransactionsModal.vue`), added in chat: below the day's rows, a **Done on this day** list. It shows every one-off row dated that day that is marked done (deal and manual rows), greyed out and struck through, with its deal tag, "done <date>" and an **Undo** button (`theater.day-modal.done-row.<id>.undo`). It uses the same `markNotDone` path as the legend.
- **A deal whose rows are all done** (`open_row_count` 0) is hidden from the legend today, which would make its done rows unreachable. It gets a collapsed "Finished deals (N)" group under Deals, with only its Transactions section.

## Todo (estimates)
- [ ] Commit this plan (5 min)
- [ ] A: `calc_hml_monthly_interest_payment`; the HML slices and total; the schedule rows; the explain check and text (40 min)
- [ ] A: pytest for exactly 1% at 12% in 28-, 30- and 31-day months, the total = sum of slices, Σ rows == −Cash Needed. Update the regression snapshots (`tests/_regression_snapshots`) in a `Golden update:` commit (40 min)
- [ ] B: `key_dates` on the imported deals + pytest (25 min)
- [ ] B: `dealTransactionsTimelineByMonth`, the Transactions section, done rows struck through with Undo, Finished deals, `markNotDone` wiring (75 min)
- [ ] MCP support: the `list_liquidity_deals` description mentions `key_dates`. Marking a row not done is already the tool `mark_liquidity_transaction_not_done` (10 min)
- [ ] Tests (below) (60 min)
- [ ] Security task, from `.claude/security.md`: "Please check through all the code you just wrote and make sure it follows security best practices. make sure there are no sensitive information in the frontend and there are no vulnerabilities that can be exploited throughout all the code in this repo". Concretely (15 min):
  - descriptions and key dates are rendered as text only;
  - Undo only sends ids from the loaded list;
  - `key_dates` exposes nothing the deal endpoints don't already;
  - then `/security-review` on the diff.
- [ ] Build, vitest, pytest; Playwright (liquidity specs, and the analyze / deal goldens, re-recorded in a `Golden update:` commit if the HML amounts change them); push; update PR #125 (30 min)

## Tests
**Unit (vitest)**
- `legendRows.test.ts`:
  - markers and rows are merged by date, markers first;
  - grouped by month with count, net and done count;
  - other deals' and manual rows are left out;
  - done rows are included and flagged.
- `DealLegendPanel.test.ts`:
  - the Transactions section replaces "Open rows";
  - the current month opens by default;
  - a key date shows its state;
  - a done row is struck through, and Undo emits `markNotDone`;
  - an open row opens its day;
  - Finished deals is listed.
- `LiquidityTheaterMode.test.ts`: `markNotDone` is passed on to the view.
- `DayTransactionsModal.test.ts`: the day's done rows are listed struck through; Undo emits `markNotDone`; a day with none shows no list.

**Integration (pytest)**
- An HML row is exactly loan × rate ÷ 12 in February, April and May.
- `hml_interest` = prepaid + monthly + payoff.
- The schedule still adds up to −Cash Needed.
- `GET /liquidity/deals` returns `key_dates`, including the Nov 30 bill inside the hold.

**E2E (Playwright, `liquidity-theater-mode.spec.ts`)**
- Mark an overdue deal row Done and let the toast go. In the deal's Transactions, the row is struck through; Undo brings it back into Overdue and the chip's count is back.
- A done row shows struck through in its day's modal, and Undo there reopens it.
- The key dates show among the rows.
- `liquidity.spec.ts` and `liquidity-deal-import.spec.ts` keep passing. Goldens whose HML amounts change are re-recorded only in a `Golden update:` commit.

## Verification
- `cd BackEnd && pytest`
- `cd frontend && npm run build && npm test`
- `npx playwright test --project=chromium --project="Mobile Chrome"`
- A screenshot of a deal's Transactions section (markers, done rows struck through with Undo).
- Re-analyze a seeded deal: every "HML interest for …" row is 1.00% of the loan at 12%.
