# LiquidityTheaterOnly: theater mode becomes the whole liquidity page

Stacked on avivjan/BrrrrDealAnalyzer#124 (branch `claude/zen-brown-nv5tlv`, not merged yet), so that PR grows to include this. The first commit is this plan, saved as `tasks/todo/LiquidityTheaterOnly.md`. Goldens change only in `Golden update:` commits.

## Context
PR #124 added theater mode next to the normal liquidity page. You want theater mode to be the only view. Everything the normal page has must have a place in it, so the normal layout can go.

**Decisions from chat**
- No investment in the no-data edge case. The theater always renders; with no data you start from Settings / + Add Flow in the action bar.
- Leaving the theater (`Esc` with nothing open, or `×`) leaves the liquidity page. App navigation, account and server status are reached there; the theater doesn't need them.
- Close the remaining gaps below; fix the small differences as I see fit.

## Design

### 1. `/liquidity` is the theater
- **`views/LiquidityTimeline.vue`:**
  - The theater is always open, mounted from the first render. During the first load, the chart area shows a small spinner, the existing `liquidity.loading` hook, moved into the theater.
  - A failed load shows a toast with the error and a Retry action.
  - The normal dashboard markup goes: hero header, KPI cards, inline overdue strip, deals panel, inline chart, inline DayDetail and the Upcoming rail.
  - All handlers and modals stay as they are: TransactionForm, SimulationWarning, SettingsPanel, the milestone and re-sync modals, and the toast.
- **Leaving the page:** `Esc` with nothing open, or `×`, goes back to the page you came from inside the app, via `router.back()` when `window.history.state.back` is set; with no in-app history (a direct link), it goes to Dashboard `/`.
- **The `?view=theater` link:** still works, as the same page; the query is no longer read or written.
- **`T`** is removed: the theater is always on. `F` / `L` / `D` / `?` and the `Esc` order stay: day modal → popover → sheet → leave.
- **`LiquidityTheaterMode.vue`:** the `open` prop and the open/close emits are replaced by one `leave` emit.
- **Removed as dead code, with their tests:**
  - `LiquiditySidebar.vue`;
  - `LiquidityDealsPanel.vue`. Its "Show its open rows" moves into the legend (3); its Approve / Move / Review / Remove are already in the legend and the sheet.
  - `TimelineChart` and `DayDetail` stay: they are used inside the theater.

### 2. Approving a milestone on a different actual date (gap 2)
- **New button:** "Done on another date…" (calendar icon, `theater.sheet.milestone.done-on-date`) beside **Done** on each open milestone in the bottom sheet. It opens the existing `DealMilestoneChangeModal` with `approve: true`, which already has the "It happened on" date picker and the before → after list.
- **The same button** sits beside Approve in the day modal's "Milestones on this day".
- **Done stays a one-tap approval** on the planned date (`useOneTapMilestoneApproval`).

### 3. All of a deal's open rows in the legend: compact and collapsible (gap 3)
When a deal is expanded in `DealLegendPanel.vue`, it shows two sections:
- **Overdue (N):** expanded by default. The current rows with Done, postpone, date and amount.
- **Open rows (N), grouped by month:** collapsed by default.
  - Each month header shows the month, its row count and its net (for example "Dec 2026 · 4 rows · −$6,240") and expands on its own. The first month with open rows is expanded when the section opens.
  - Each row is one compact line: date · description · amount (with the late-refi icon when `created_because_refi_is_late`).
  - Clicking a row opens that day in the day modal, where every action is.

Pure helper `groupOpenRowsOfDealByMonth(transactions, dealKey)` in the new `components/liquidity/theater/legendRows.ts`, unit-tested.

### 4. Small differences, fixed
- **Mercury last sync time:** the balance popover's header reads "mercury · N accounts across M workspaces · synced HH:MM", from `store.mercuryLastSyncedAt`.
- **Late refi count:** the legend drawer badge reads "Refi late · N added rows" (`late_refi_row_count`).
- **"Review changes" when collapsed:** an out-of-date deal shows a warning icon button on its collapsed legend row (`theater.legend.deal.review-changes-collapsed`), so it's seen without expanding. The drawer keeps its text link.
- **Keyboard:** stays as built. The arrow keys move the selection with the floating preview following, Enter opens the day, and inside the day modal the arrows step days. The shortcuts help says so. This is better than opening a panel on every arrow press, which the normal page did.
- **The normal page's empty-state buttons** ("Set Opening Balance", "Add First Flow"): already covered by Settings and + Add Flow in the action bar.

### 5. Every hook the e2e and perf suites use stays reachable
`hooks-inventory.test.ts` fails on a lost `data-testid`, so the specs are rewritten to the theater hooks (Tests) rather than keeping dead hooks.

## Todo (estimates)
- [ ] Commit this plan as `tasks/todo/LiquidityTheaterOnly.md` (5 min)
- [ ] 1: the view renders only the theater; leave = back / Dashboard; drop `T` and the query handling; loading spinner and error toast in the theater; delete `LiquiditySidebar` and `LiquidityDealsPanel` and their tests (60 min)
- [ ] 2: "Done on another date…" in the sheet and the day modal (20 min)
- [ ] 3: open rows by month in the legend drawer + `legendRows.ts` (60 min)
- [ ] 4: last sync time, late-refi count, the collapsed "review changes" button (20 min)
- [ ] MCP support: no new endpoint or tool. Check that no MCP text mentions the removed page layout, and leave it unchanged otherwise (5 min)
- [ ] Tests (below) (120 min)
- [ ] Security task, from `.claude/security.md`: "Please check through all the code you just wrote and make sure it follows security best practices. make sure there are no sensitive information in the frontend and there are no vulnerabilities that can be exploited throughout all the code in this repo". Concretely (20 min):
  - leaving the page only goes back or to `/`, with no URL taken from input;
  - no `v-html`; month labels and descriptions are text only;
  - no new storage;
  - then `/security-review` on the diff.
- [ ] `npm run build`, `npm test`, pytest; Playwright on Chromium and Mobile Chrome; push; update the PR description (20 min)

## Tests
**Unit (vitest)**
- `legendRows.test.ts`:
  - rows grouped by month in date order, with count and net per month;
  - done rows and other deals' rows left out;
  - late-refi rows flagged.
- `DealLegendPanel.test.ts` (add):
  - the Open rows section is collapsed by default, and the first month opens when it opens;
  - a row click emits `openDay(date)`;
  - "Refi late · N added rows";
  - the collapsed review-changes button emits `reviewChanges`.
- `DealMilestonesBottomSheet.test.ts` and `DayTransactionsModal.test.ts` (add): "Done on another date…" emits `changeMilestone(deal, milestone, approve = true)`; an approved milestone has no such button.
- `LiquidityTheaterMode.test.ts` (update):
  - `Esc` with nothing open and `×` emit `leave`;
  - `T` does nothing;
  - the loading spinner shows while loading with no days;
  - the Mercury popover shows the sync time.
- `useOneTapMilestoneApproval.test.ts` unchanged.
- The deleted components' tests go with them.

**Integration (pytest):** no backend change. The full suite is re-run as a regression check.

**E2E (Playwright)**
- `liquidity.spec.ts` rewritten on theater hooks, with the same journeys and the same network goldens (the requests don't change):
  - load, then settings and a one-off flow, starting from `theater.settings` and `theater.add-flow` (no empty state);
  - the Mercury breakdown through `theater.figure.balance`;
  - the arrow keys, then Enter opening the day modal.
- `liquidity-deal-import.spec.ts`:
  - overdue Done / Undo, postpone, amount and bulk postpone through the overdue chip's popover;
  - the milestone move through the sheet's Move.
- `liquidity-theater-mode.spec.ts`:
  - open directly at `/liquidity`;
  - `Esc` / `×` leave back to the previous page, or to Dashboard when opened directly;
  - "Done on another date" approves with the picked date;
  - a deal's Open rows by month, where a row click opens its day.
- `a11y.spec.ts` and `checks/perf.spec.ts`: the liquidity route's ready hook becomes `theater.add-flow`. The axe baseline for `liquidity` is re-recorded in a `Golden update:` commit if the scan differs.

## Critical files
- **Edited:**
  - `frontend/src/views/LiquidityTimeline.vue`
  - `frontend/src/components/liquidity/theater/{LiquidityTheaterMode,DealLegendPanel,DealMilestonesBottomSheet,DayTransactionsModal}.vue`
- **New:** `frontend/src/components/liquidity/theater/legendRows.ts` (+ test)
- **Deleted:** `frontend/src/components/liquidity/{LiquiditySidebar,LiquidityDealsPanel}.vue` and their tests
- **E2E:**
  - `frontend/e2e/flows/{liquidity,liquidity-deal-import,liquidity-theater-mode,a11y}.spec.ts`
  - `frontend/e2e/checks/perf.spec.ts`
  - `frontend/e2e/golden/axe-baseline.json` (only if needed)
- **Reused as they are:**
  - `DealMilestoneChangeModal` (approve with a date)
  - `useOneTapMilestoneApproval`
  - `DayDetail`, `TransactionRowActions`, `InlineAmountEditor`, `OverdueTransactionsStrip`
  - the deal lookup in `composables/useLiquidityDealAttribution.ts`
  - `store.mercuryLastSyncedAt`

## Verification
- `cd frontend && npm run build && npm test`
- `cd BackEnd && pytest`
- `npx playwright test e2e/flows/liquidity*.spec.ts e2e/flows/a11y.spec.ts e2e/checks/perf.spec.ts --project=chromium --project="Mobile Chrome"`
- Screenshots at desktop and phone width, light and dark: `/liquidity` opens straight into the theater; `Esc` returns to the previous page; a deal's open rows by month; "Done on another date"; the Mercury popover with the sync time.
