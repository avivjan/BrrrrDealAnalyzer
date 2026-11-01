# DealCashInLiquidity: import a deal's Cash Needed rows into the liquidity timeline, with Done, overdue and milestone approvals

Developed on `claude/blissful-clarke-t18u4a`, stacked on the unmerged PR avivjan/BrrrrDealAnalyzer#111, so that PR grows to include this feature. Committed first as `tasks/todo/DealCashInLiquidity.md`. Goldens change only in `Golden update:` commits. Check in with you before writing any code (this plan is that check-in).

## Context

PR avivjan/BrrrrDealAnalyzer#111 gave every BRRRR deal a dated Cash Needed schedule (Lowest ARV). The next step is to put those rows into the liquidity timeline so you can see whether you can afford another deal. Today that would mislead you in two ways:
- **Past rows vanish.** `buildDailyLiquiditySeries` (`frontend/src/utils/liquidityEngine.ts`) ignores every row dated before the opening balance date. A payment that was due on the 1st and really leaves on the 5th disappears on the 2nd, but it isn't in the Mercury balance yet. The timeline shows more cash than you have.
- **Mercury counts every account.** `mercury_client._summarize_workspace` sums every active account, including the tax bucket and the high-yield savings account, so money moved there would still count as available.

This plan makes "paid" explicit (Done), keeps unpaid rows visible and counted, lets you approve or move the deal's dates with a before → after list of affected rows, and previews a deal's impact before it is imported. The single Cash Needed number stays for quick estimates.

## Decisions (agreed in chat)
1. **A row leaves the timeline only when marked Done** (one tap), never because its date passed.
2. **Overdue money out** (open, dated before today) moves to today and keeps counting: today's projected balance is the bank balance minus overdue outflows. It shows an "overdue since …" tag, plus an "N overdue" chip on the timeline.
3. **Overdue money in** stays visible but stops counting ("expected, not counted") until you mark it Done or give it a new definite date (default suggestion +7 days); from then it counts on that date.
4. **One type of transaction, one button: "Done ✓"**, the same for payments and holds.
5. **Negative stolen money** stays a single dated row: postpone it until paid, and edit its amount after a partial payment.
6. **The rehab cushion becomes an ordinary row** (money out on the purchase closing date) that you postpone until you mark it Done. The "Must stay in the account" section and the reconciliation summary go away. The single Cash Needed number stays.
7. **Approving, postponing and changing an amount take one or two taps:**
   - on each row: Done, postpone chips (+1 day, +1 week, next 1st, pick a date), and an amount you tap to edit;
   - bulk select to postpone or mark Done;
   - an overdue strip at the top.
8. **Five milestones per imported deal:** contract signed, purchase closed, rehab completed, tenant moved in, refi closed. Approving or changing any of them, with any new date, first shows the full list of affected rows: moved, amount changed, added, removed, and kept because you edited it. Nothing changes until you confirm.
9. **Milestones are managed in the liquidity timeline.** Approving or changing one also writes the date back to the deal, so the deal stays the source of truth and its analysis matches reality.
10. **A refi that isn't approved after its planned date** keeps adding the monthly carrying costs (HML interest, HOA, insurance paid monthly, utilities while vacant) on each 1st after the planned date. These are **real, persisted rows**: the same individual rows the schedule produces, with their normal identity, flagged `created_because_refi_is_late`. Done, postpone and edit work on them, MCP and the backend see them, and approving the refi later updates the same rows instead of duplicating them.
11. **Import is a button on the deal**, and only after a preview. The preview shows one deal at a time, the current timeline vs with the deal, and insights (below). You import only after agreeing.
12. **Exact dollars everywhere:** the liquidity `_k` amounts become dollars.
13. **No manual testing phase:** everything ships in this one plan, in phases.
14. **Moving the purchase closing date always shifts the later milestones** (rehab completed, tenant moved in, refi closed) by the same number of days. Their `days_until_*` values stay as they are; the before → after list shows every moved row.
15. **Any BRRRR deal can be imported** (any My Deals stage or the Bought board).
16. **Editing an imported deal re-syncs only after a confirm.** Saving shows "This changes N liquidity rows" with the same before → after list: Confirm updates the rows; Skip leaves them as they are and the deal shows "liquidity out of date" with a Re-sync button.
17. **Appliances move to the rehab completion date** (money out). This replaces "two months after closing, capped at the refi", so the row follows the rehab-completed milestone.
18. **Rows know which board their deal is on:** `source_deal_board` (`my_deals` / `bought`) next to `source_deal_id`. There are no foreign keys between the deal tables, and moving a deal to Bought creates a copy while the My Deals deal stays. So `move_to_bought` re-points the rows to the new Bought deal in the same database transaction, as it already does for inspections (`repoint_inspection_links`). The My Deals copy then shows "In liquidity through its Bought copy" and can't be imported again, so the same property is never counted twice.
19. **Your overrides are tracked separately:** `user_overrode_date` and `user_overrode_amount`.
    - A re-sync (deal edit, milestone change, re-import) keeps an overridden field and still updates the other one. Moving an HML payment to the 3rd keeps the 3rd, and a bigger loan still updates its amount.
    - A row marked Done is never touched.
    - Every conflict is shown in the before → after list: "kept your $1,800 (the deal now says $2,100)" with a one-tap "Use $2,100"; "kept your date Mar 3 (the planned date moved to Apr 1)" with "Use Apr 1".

## Design

### Phase 1 — Liquidity in exact dollars
- **Rename, with a migration that multiplies existing values by 1000 (idempotent):**
  - `liquidity_transactions.amount_k` → `amount_dollars` (`Numeric(14,2)`)
  - `liquidity_recurring_transactions.amount_k` → `amount_dollars`
  - `liquidity_settings.opening_balance_k` / `reserve_k` → `opening_balance_dollars` / `reserve_dollars`
  - new migration step in `migrations/steps/`, registered in `migrations/runner.py`
- **Mercury summary** (`BL/liquidity/common/mercury_client.py`): `current_balance_k` / `total_balance_k` and the rest become `*_dollars`, with no ÷ 1000.
- **Schemas, CRUD and mappers:** `ReqRes/common/liquidity_schemas.py`, `DAL/crud/liquidity.py`, `BL/liquidity/common/mappers.py`.
- **Frontend:** `types/liquidity.ts`, `utils/liquidityEngine.ts` (`net_k` / `balance_k` → `*_dollars`), `stores/liquidityStore.ts`, `TimelineChart.vue`, `TransactionForm.vue`, `SettingsPanel.vue`, `DayDetail.vue`, `LiquiditySidebar.vue` and `views/LiquidityTimeline.vue`. Inputs become money in dollars, using the existing `MoneyInput`.
- **MCP:** remove `_k` from the liquidity tool descriptions and from `INSTRUCTIONS`.

### Phase 2 — Mercury: only the operating account(s) count
- Settings gain `mercury_account_ids_counted_as_cash` (JSON list). `SettingsPanel` lists the Mercury accounts with their balances as checkboxes.
- `syncFromMercury` anchors the opening balance on the checked accounts only.
- The tax bucket and the HYSA account stay unchecked, so the schedule's deposits into them are real outflows from the operating account.

### Phase 3 — Done and overdue on every one-off transaction
- **New columns on `liquidity_transactions`:**
  - `done_at` (nullable datetime)
  - `originally_planned_date` (the date first imported or created, for the "moved from …" text)
  - `user_overrode_date`, `user_overrode_amount` (booleans, decision 19), set when you postpone or re-date a deal row, or edit its amount
- **Migration:** every existing transaction dated before today is marked done, so your history doesn't suddenly become overdue.
- **Engine** (`liquidityEngine.ts`, pure; "today" is passed in as the browser's local date):
  - a done row is excluded;
  - an open row dated before today: money out is counted on today and flagged overdue; money in is listed as "expected, not counted" and excluded from the balance;
  - `buildDailyLiquiditySeries` and `simulateImpact` take `todayIsoDate`.
- **Recurring rules keep their current behaviour.** Their occurrences are virtual, cannot be marked Done, and pass as before. Deal rows are always one-off rows.
- **Endpoints:** `POST /liquidity/transactions/{id}/done`, `/undone` (for an Undo toast), `POST /liquidity/transactions/bulk` (Done or postpone a selection). Postponing and editing the amount use the existing `PUT`.
- **UX:**
  - each row in `DayDetail` and the sidebar gets ✓ Done, postpone chips and an amount you tap to edit;
  - an overdue strip and an "N overdue" chip above the chart;
  - overdue money in shows greyed with a "Set new date" picker;
  - bulk select mode;
  - an Undo toast after Done.

### Phase 4 — The schedule: the cushion as a row, no reconciliation block
- `brrrSteps/cash_needed_schedule.py`: add an `item_key = "rehab_cushion"` row (money out, on the closing date).
- Appliances: money out on the rehab completion date (decision 17). Drop `APPLIANCES_BOUGHT_MONTHS_AFTER_BUY_CLOSING`; `add_calendar_months_clamped` stays only if something else still uses it, otherwise it goes with its tests. Its docstrings, the plan file of PR #111 and the schedule tests change to match.
- Remove `CashThatMustStayInAccount`, `cash_that_must_stay_in_account*` and `dated_cash_rows_net_outflow_dollars` from the step, the record, the API (`ReqRes/common/cash_needed_schedule.py`), the explain note, the HTML/PDF block (`cash_needed_schedule_report.py`), `CashNeededScheduleTable.vue`, the types and the MCP glossary.
- `total_cash_needed_for_deal` stays unchanged as the quick estimate.
- The internal test keeps checking Σ rows == −Cash Needed (the cushion included); nothing on screen shows it.

### Phase 5 — Deal milestones (stored on the deal)
- **New columns** on `BrrrLifecycleColumns` (both BRRRR tables), nullable datetimes: `contract_date_approved_at`, `buy_closing_date_approved_at`, `rehab_completed_date_approved_at`, `tenant_occupied_date_approved_at`, `refi_closing_date_approved_at`.
- **The five dates map to the deal:** `contract_date` and `buy_closing_date` directly; rehab, tenant and refi through `days_until_*` = date − closing.
- **Changing the closing date** shifts every later milestone by the same number of days (decision 14), which is simply the unchanged `days_until_*` values.
- **Preview** (`POST /liquidity/deals/{deal_ref}/milestones/preview`, body: milestone, new date, approve yes/no):
  1. validate the date order (the rules in `validation.py`);
  2. re-analyze the deal with the new dates;
  3. diff its rows against the imported rows by identity (deal + item_key + occurrence number);
  4. return moved / amount changed / added / removed / kept, plus the timeline impact. For a row with an override, the list names the conflict and offers "Use the deal's value" (decision 19).
- **Apply** (`POST .../milestones/apply`): write the date and the approval to the deal through the existing deal update path (and its validation), re-sync the rows as listed, and audit the change.
- **Overdue milestone** (planned date passed, not approved):
  - its money-out rows are already overdue under Phase 3;
  - **For the refi (decision 10):** the backend re-analyzes the deal with a provisional refi date, the first 1st after today, without writing it to the deal. It persists the monthly money-out rows that analysis gives between the planned refi and that 1st (HML interest, HOA, insurance paid monthly, utilities while vacant), with their normal identity (deal + item_key + occurrence number) and `created_because_refi_is_late = true`:
    - **No pre-counted rent:** money in (rent) is not added, which keeps it conservative.
    - **The refi-day rows** (cash to the table, reserves, insurance C outside the closing, the tax release) stay where they are and are overdue under Phase 3.
    - **When it runs:** whenever the timeline loads, with the browser's local date (`POST /liquidity/deals/refresh-late-refis` with `today`), and on MCP liquidity reads, with a `timezone` stored in the liquidity settings. It's idempotent by identity, so loading twice never creates rows twice.
    - **Approving or moving the refi** runs the normal diff: these same rows are updated or removed by identity, and Done ones stay Done. The list shows "N rows created while the refi was late: kept / updated / removed".
- **UI:** a "Deals" panel in the liquidity view lists each imported deal (address link, overdue badges) and its five milestones with their state (planned / approved / overdue). The actions are Approve (as planned or with a date) and Change date; both open the before → after list with one "Confirm".

### Phase 6 — Import with a preview
- **Eligibility:** any BRRRR deal (decision 15).
- **Button:** "Import to liquidity" in the BRRRR deal modals (`MyDeals.vue`, `BoughtDeals.vue`).
- **Preview modal:**
  - **chart:** `TimelineChart` with a dashed "with this deal" line over the current one;
  - **insights:** lowest balance with and without the deal (amount, date); days below the reserve and the first such date; first negative date if any; the deal's total money out and money in; the largest single-day outflow; cash on hand today vs the deal's money out in the next 30 days; when the balance gets back above the reserve after the refi; and the rows to be imported, by month;
  - **confirm:** an "Import" button.
- **Import** (`POST /liquidity/deals/{deal_ref}/import`):
  - creates one-off rows tagged with `source_deal_board`, `source_deal_id`, `source_item_key`, `source_occurrence_number` and `sequence_within_day` (decision 18);
  - identity = deal + item_key + occurrence number (never the date);
  - a re-import is idempotent: it updates its own rows in place, keeps every overridden field while updating the others (decision 19), never touches a Done row, and removes rows that dropped out unless they carry an override (those stay, flagged "no longer in the deal");
  - the refi wire is never imported;
  - rows show "from 123 Main St" with a link, and the timeline can be filtered by deal.
- **A deal saved after import** (decision 16): the save runs the same diff as the milestone preview and shows a confirm with the list. Skip sets a `liquidity_rows_out_of_date` flag that shows a badge and a Re-sync button on the deal and in the Deals panel.
- **Moving to Bought** (decision 18): `BL/boughtDeal/moveToBought.py` re-points the rows (`source_deal_board` → `bought`, `source_deal_id` → the new id) inside the same transaction, next to `repoint_inspection_links`. The import endpoint refuses a My Deals deal whose Bought copy is already imported (409), and its modal shows "In liquidity through its Bought copy" with a link.
- **Deleting a deal or marking it Dead:** its open rows are removed, after a prompt that offers to add the EMD back as money in.

## Notes to respect while building (from the chat)
1. A passed date doesn't mean paid; only Done removes a row.
2. Overdue money out sits on today and counts; overdue money in doesn't count until it gets a new date or is marked Done.
3. Any milestone approval or change shows the affected rows (moved, changed amount, added, removed, kept) and changes nothing until confirmed.
4. A refi that isn't approved keeps adding carrying costs on each 1st after its planned date, as real persisted rows that approving the refi later updates instead of duplicating.
5. Paying early double-counts until you mark the row Done; rows dated today that have already cleared too.
6. "Today" is the user's local date.
7. Only the checked Mercury accounts count as cash; the tax bucket and the HYSA stay out.
8. The refi wire is never imported.
9. Row identity is deal board + deal + item_key + occurrence number. A re-import is safe to press twice, keeps your overridden date or amount (each on its own), and never touches a Done row.
10. Removed rows go unless touched.
11. A dead or deleted deal: its open rows go, and the EMD may come back as money in.
12. Deal rows are tagged and filterable, and kept apart from manual transactions.
13. The "Lowest-ARV refi" labels stay.
14. Exact dollars, no `_k`.
15. Rows on a shared day keep their order: money out first, then money in.
16. The cushion is an ordinary row, postponed until Done.
17. A date or an amount takes one or two taps to change, alone or in bulk.
18. Every import starts with the preview: one deal at a time, the lowest points and the insights.
19. Moving a deal to Bought re-points its rows in the same transaction; a property is never imported twice.
20. Appliances are paid on the rehab completion date.

## Todo (≈ 16 h 30)
- [ ] T1 (5 min) Commit this plan as `tasks/todo/DealCashInLiquidity.md`.
- [ ] T2 (2 h) Phase 1, dollars: migration, models, schemas, CRUD, Mercury summary, engine, store, components, MCP text; tests.
- [ ] T3 (15 min) `Golden update:` liquidity endpoints/OpenAPI/models + Playwright liquidity goldens for dollars.
- [ ] T4 (1 h) Phase 2, the Mercury accounts counted as cash (setting, panel, sync).
- [ ] T5 (2 h 30) Phase 3, Done / overdue: columns + migration, endpoints, engine with today, UX (row actions, overdue strip, bulk, Undo).
- [ ] T6 (1 h) Phase 4, the cushion row, appliances on the rehab completion, the reconciliation block removed; reports, popup, MCP glossary.
- [ ] T7 (15 min) `Golden update:` the schedule change.
- [ ] T8 (3 h 30) Phase 5, milestones: columns, the date mapping, preview/apply endpoints, the diff with the per-field overrides and their conflicts, the Deals panel, the persisted late-refi rows and their refresh.
- [ ] T9 (3 h) Phase 6, import: preview modal + insights, import/re-import endpoints with identity, the deal tag/filter, the active → bought re-pointing and the no-double-import rule, delete/dead handling.
- [ ] T10 (30 min) MCP: new endpoints become tools (`DESCRIPTIONS` entries, destructive annotations on import/apply/bulk); `INSTRUCTIONS` cover dollars, Done/overdue, milestones and import.
- [ ] T11 (20 min) Security task (`.claude/security.md`: "Please check through all the code you just wrote and make sure it follows security best practices. make sure there are no sensitive information in the frontend and there are no vulnerabilities that can be exploited throughout all the code in this repo"):
  - the new endpoints sit behind the existing auth gate and are audited (`BL/auth/common/audit.record`);
  - dates and amounts are validated by Pydantic;
  - deal references are UUIDs checked to exist;
  - every user string goes through Vue interpolation (no `v-html`);
  - the Mercury account ids are stored, never the tokens;
  - migration SQL is static;
  - run bandit and `npm audit`.
- [ ] T12 (1 h) Playwright flows + re-record; final gates; push; PR.

## Tests by layer
**Unit:**
- engine overdue/Done rules: money out moves to today; money in excluded until re-dated; done excluded; recurring rules unchanged
- the dollars migration ×1000 and idempotency
- the schedule's cushion row and Σ rows == −Cash Needed
- appliances on the rehab completion date
- milestone diff: moved, amount changed (closing → prepaid interest, seller credit), added (refi slips a month), removed, kept-because-edited
- the import identity and idempotency (importing twice gives the same rows)
- per-field overrides: a re-dated row keeps its date and takes the deal's new amount; an amount override keeps its amount and takes a milestone's new date; the conflict appears in the list; a Done row is untouched
- the late-refi rows: persisted with their normal identity and the flag; refreshing twice creates them once; no rent added; approving the refi updates them instead of duplicating; Done ones stay Done
- the Mercury counted-accounts sum
- frontend: `liquidityEngine.test.ts`, the store, the row-action components, the Deals panel, the preview insights

**Integration:**
- Done/undone/bulk endpoints
- import/re-import/preview endpoints (409 on a FLIP deal, 404 on an unknown one)
- saving an imported deal returns the affected-rows list; Confirm re-syncs, Skip sets the out-of-date flag
- milestone preview/apply writes the deal's dates and approvals, and is rejected by the date-order rules
- a deal deleted or marked Dead removes its open rows
- the active → bought move re-points the rows in the same transaction (board + id); a second import of the My Deals copy is refused (409); deleting the My Deals copy afterwards leaves the rows alone
- MCP tools listed, documented and annotated
- `verify_regression.py` snapshots reviewed

**E2E:**
- import a deal through the preview (the insights shown, the dashed line)
- an overdue row on today, then Done with Undo
- postpone with a chip
- edit an amount
- approve a milestone with a new date and confirm the before → after list
- an overdue money-in row given a new date
- bulk postpone

## Verification
- `pytest`, `verify_regression.py verify`, `npm test`, `npm run build`, Playwright chromium.
- Manual:
  1. Import the base deal and check the preview's lowest point.
  2. Advance the clock fixture past the closing: cash to close sits on today until marked Done.
  3. Approve the closing two days late: the list shows the moved rows and the new prepaid interest and seller credit.
  4. Let the refi pass unapproved: real carrying-cost rows appear up to the next 1st and can be marked Done; approving the refi updates them without duplicates.
  5. Move a deal to Bought: its rows now link to the Bought deal, and the My Deals copy can't be imported again.
