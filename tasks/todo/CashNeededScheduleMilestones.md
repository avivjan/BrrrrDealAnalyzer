# CashNeededScheduleMilestones: the deal's key dates inside the Cash Needed schedule

Branch: the session's designated `claude/settlement-statement-florida-title-5k3j75`. PR avivjan/BrrrrDealAnalyzer#122 is still open (not merged), so this lands as follow-up commits on it. The first commit copies this plan to `tasks/todo/CashNeededScheduleMilestones.md`, and boxes are ticked there.

## Context
The "Cash schedule (Lowest ARV)" table lists every dated cash row of Cash Needed. Today it shows no dates for the events those rows hang off, so the reader has to work out that "Appliances" falls on the rehab-completed day or that rent starts when the tenant moves in. You asked for the deal's key dates (contract, closing, rehab completed, refi, …) inside that table, styled differently from the transactions, so the timeline reads at a glance.

The table appears in three places from one backend result: the website's breakdown popup (`frontend/src/components/deal/CashNeededScheduleTable.vue`), the HTML report and the PDF (`BackEnd/BL/reports/common/cash_needed_schedule_report.py` → `deal_html_report.py`, `deal_pdf.py`). All three get the dates.

**Constraint:** `dated_cash_rows` is also the liquidity import (`BL/liquidity/dealCashRows/deal_cash_rows.py:131`). Every row there is a real transaction that sums to Cash Needed (guarded in `explain/brrr.py:629`). The key dates therefore go in a **separate list** next to it, and the liquidity timeline, Cash Needed and every amount stay unchanged.

**Defaults taken (say if you want different):**
- The dates are the five deal milestones the liquidity timeline already tracks (`deal_milestones.py`): Contract signed, Purchase closing, Rehab completed, Tenant moves in, Refi closing.
- They are joined by the **Nov 30 property tax bill**, only when it falls between the purchase and the refi (it explains the tax-bucket rows around it).
- On a shared day, the date row sits above that day's transactions.

## Design

### Backend: one new list on the schedule
- `BL/analyze/brrrSteps/cash_needed_schedule.py`:
  - `CASH_NEEDED_SCHEDULE_MILESTONE_KEYS = ("contract_signed", "purchase_closed", "rehab_completed", "tenant_moved_in", "property_tax_bill_paid_on_november_30", "refi_closed")`. The first five reuse the liquidity milestone names.
  - `class CashNeededScheduleMilestone(NamedTuple): date, milestone_key, description`.
  - `CashNeededScheduleAtLowestArv` gains `deal_milestones: tuple[CashNeededScheduleMilestone, ...]`, sorted by date, then catalogue order.
  - Built in `cash_needed_schedule_step` from `timeline` and `property_tax_bucket.first_property_tax_payment_date` (already passed in). The descriptions are "Contract signed", "Purchase closing", "Rehab completed", "Tenant moves in", "Property tax bill paid from the tax bucket (Nov 30)" and "Refi closing". The tax bill is listed only when it falls after the purchase closing and on or before the refi closing.
- `ReqRes/common/cash_needed_schedule.py`: `CashNeededScheduleMilestoneRes` (date, milestone_key, description, each described). `CashNeededScheduleAtLowestArvRes.deal_milestones` is described as "key dates of the deal shown among the cash rows; not cash, never imported into the liquidity timeline".
- `BL/analyze/analyzeBRRR.py:96-101` `cash_needed_schedule_response` maps the new list.
- `explain/brrr.py`: a `check` that the milestones are in date order, plus one clause in the schedule note.

### Reports: interleaved, styled apart
- `cash_needed_schedule_report.py`:
  - `CashNeededScheduleReportMilestoneRow(date_text, description)`.
  - `CashNeededScheduleReport` gains `lines_in_date_order: list[CashNeededScheduleReportRow | CashNeededScheduleReportMilestoneRow]`: the cash rows and the milestones merged by date, milestones first on a shared day. `dated_rows` stays as it is.
  - An older result with no `deal_milestones` gives the plain rows.
- `deal_html_report.py` `_cash_needed_schedule_markup` iterates `lines_in_date_order`:
  - A milestone is `<tr class="milestone"><td class="date">…</td><td colspan="2"><span class="milestone-label">◆ Purchase closing</span></td></tr>`.
  - New CSS beside `:459-465`: `.schedule-table tr.milestone td` gets a tinted background (`var(--accent-soft)` or the existing tint token), a 3px left accent border and `font: 700 10.5px/1.4 var(--sans); letter-spacing: 0.1em; text-transform: uppercase; color: var(--accent)`.
  - Interpolation stays through `_text()`, which escapes.
- `deal_pdf.py` `_cash_needed_schedule_flowables` uses the same order. A milestone row is a new `styles["schedule_milestone"]` paragraph (Helvetica-Bold, 8pt, uppercase, `BRAND_NAVY`), with a `SPAN` over item + amount and a light `BACKGROUND` tint, all through `escape()`.

### Website popup
- `frontend/src/types/index.ts`: `CashNeededScheduleMilestone { date; milestone_key; description }`, with an optional `deal_milestones?` on `CashNeededScheduleAtLowestArv` (older saved results have none).
- `CashNeededScheduleTable.vue`:
  - A computed `scheduleLinesInDateOrder` merges `deal_milestones` and `dated_cash_rows` by date, milestones first, and tags each line as a milestone or a cash row.
  - Cash rows render exactly as today.
  - A milestone row is `<tr data-part="schedule-milestone" :data-milestone-key>`:
    - a date cell in the milestone colour;
    - a `colspan="2"` cell with `<i class="pi pi-flag">` and the label in `text-[11px] font-semibold uppercase tracking-wider text-primary`;
    - row styling `bg-primary/5 border-l-2 border-primary`, plain interpolation only.

  The result: transactions read as normal sentence-case rows with amounts, and milestones read as small uppercase tinted dividers with no amount.
- The doc comment says the date rows are markers, not cash.

### What stays out
No change to any amount, to Cash Needed, to the liquidity import or its timeline, or to the FLIP results.

## Todo (≈ 3 h 30)
- [x] M1 (10 min) Copy the plan to `tasks/todo/CashNeededScheduleMilestones.md`; commit.
- [x] M2 (35 min) Backend engine + response + explain check (above).
- [x] M3 (30 min) Backend tests.
  - **Unit** (`tests/test_cash_needed_schedule.py`):
    - `test_deal_milestones_are_the_contract_closing_rehab_tenant_and_refi_dates_in_order` (fixture: 2026-01-03, 2026-01-10, +45, tenant, +180);
    - `test_the_november_30_tax_bill_is_a_milestone_only_inside_the_hold` (a Jan closing with a 180-day refi: absent; a Sep closing: present on 2026-11-30);
    - `test_milestones_are_not_cash_rows_and_cash_needed_is_unchanged`.
  - **Integration:**
    - `test_liquidity_deal_import.py`: the imported rows are unchanged (no milestone becomes a transaction);
    - `test_report_html.py` / `test_report_pdf.py`: the schedule shows "Purchase closing" before "Cash to close (the purchase wire)", with `class="milestone"` in the HTML;
    - `verify_regression.py snapshot`, review (only the added `deal_milestones`), `verify`.
- [x] M4 (30 min) Reports: `cash_needed_schedule_report.py` merge, HTML markup + CSS, PDF row style.
- [ ] M5 (40 min) Frontend types + `CashNeededScheduleTable.vue`.
  - **Unit** (`CashNeededScheduleTable.test.ts`):
    - milestones interleaved by date and first on a shared day;
    - styled as `schedule-milestone` with no amount cell;
    - cash rows unchanged;
    - no `deal_milestones` (older result) renders only cash rows.
- [ ] M6 (35 min) **E2E**: a new `flows/cash-needed-schedule-milestones.spec.ts`.
  - Open the Cash Needed popup on a seeded bought deal.
  - Expect the six milestone rows (Nov 30 included for a Sep-dated deal) in date order, with "Purchase closing" right above "Cash to close".
  - Expect them to look different from transactions (computed font-size, uppercase).
  - Then `npm run e2e:record` (goldens gain `deal_milestones` only), `a11y.spec.ts`, `npm run e2e`.
  - Visual check in light and dark at desktop and phone width.
- [ ] M7 (10 min) **MCP**: no new tool. `deal_milestones` reaches `analyze_brrr` / `get_deal` through the response schema. Its descriptions stay short to keep `tools/list` under budget, and `tests/test_mcp.py` stays green.
- [ ] M8 (15 min) **Security** (`.claude/security.md`: "Please check through all the code you just wrote and make sure it follows security best practices. make sure there are no sensitive information in the frontend and there are no vulnerabilities that can be exploited throughout all the code in this repo"):
  - Re-read every touched file.
  - The milestone text comes from fixed engine strings and dates. HTML goes through `_text()`, the PDF through `escape()`, the Vue code through interpolation; there is no `v-html` or new sink.
  - Run bandit, pip-audit and `npm audit --omit=dev`.
- [ ] M9 (15 min) Final: `pytest`, `verify_regression.py verify`, `npm test`, `vue-tsc`, `npm run e2e` (chromium). Tick the boxes, push, and update the PR #122 description with this section.

## Verification
- Backend: `pytest` (local Postgres 16), `verify_regression.py verify`.
- Frontend: `npm test`, `vue-tsc`, `npm run e2e` (chromium, Mobile Chrome).
- Manual:
  - In a bought deal → Cash Needed → "Cash schedule (Lowest ARV)", the six key dates are tinted uppercase rows with a flag and no amount, each above that day's transactions.
  - The same lines appear in the HTML report and the PDF.
  - The liquidity import of the same deal shows exactly the transactions it showed before.
