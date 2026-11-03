# LiquidityTheaterMode: fullscreen liquidity timeline, deal colors, legend, milestone sheet, day modal

Branch: `claude/zen-brown-nv5tlv` (the session's designated branch, from latest `main`). The first commit is this plan, saved as `tasks/todo/LiquidityTheaterMode.md`. When it's done: push and open a PR.

## Context

On `/liquidity`, a transaction row such as "Rehab cushion" or "Utilities" doesn't say which deal it belongs to. The chart is also squeezed between the app sidebar, the right "Upcoming" rail and a stack of cards. This change adds a theater/fullscreen mode, like YouTube's large mode:
- the chart fills the viewport;
- every deal gets a color, and every row shows its deal;
- a legend lists the deals and their overdue rows;
- a bottom sheet holds each deal's milestones with a Done button;
- hovering a day shows a preview, and clicking a day opens a full modal with every action.

Nothing on the page is lost: every control and figure from the sidebars gets a place in fullscreen.

## Decisions (agreed in chat)
1. **The legend's "Remove from timeline"** deletes the deal's open rows (EMD refund offered, as today) and removes the deal from the legend and the sheet. The deal stays on My Deals / Bought and can be imported again. Done rows stay as history.
2. **A milestone's "Done"** approves it on its planned date. It loads the preview quietly: if no row would change, it applies at once; otherwise the existing before → after modal (`DealMilestoneChangeModal`) opens.

## Design

### A. Theater mode shell (frontend only, self-contained)
- **New `components/liquidity/theater/LiquidityTheaterMode.vue`**
  - teleported to `<body>`, `fixed inset-0 z-40`: above the app sidebar, topbar and mobile nav (z-20/30/40);
  - below the view's existing modals, toast and command palette (z-50/60), so TransactionForm, SettingsPanel and the milestone and import modals still open on top;
  - the shell isn't changed, so the normal page stays exactly as it is underneath.
- **Toggle:** an expand icon button (`liquidity.theater-open`) in the header next to Today, and a second one in the chart panel's corner.
- **State in the URL:** `?view=theater`, so a refresh or a shared link reopens it.
  - Entering and exiting both use `router.replace({ query: { ...route.query, view: 'theater' | undefined } })`: no history entries, and other query keys are kept (refinement 3).
  - Any other `view` value is ignored.
- **Exit:** the `×` button, or `Esc`. Esc closes the topmost layer first: day modal → legend → bottom sheet → theater. It is ignored while one of the view's own dialogs is open (an `isAnotherDialogOpen` prop computed in the view).
- **Shortcuts** (ignored while typing in an input): `T` theater, `F` browser fullscreen (Fullscreen API on `documentElement`, so the modals stay visible), `L` legend, `D` deals sheet, `←`/`→` days (the chart already does this).
- **Layout:** a column of:
  1. a top bar: title, KPI chips, floating actions;
  2. the chart, `flex-1 min-h-0` and full width;
  3. the collapsed bottom bar.

  The bottom sheet and the legend are overlays that move with `transform`/`opacity`, never resizing the chart's ancestors (the chart re-measures from a ResizeObserver).
- **Floating top-right action bar** (glass): Today, Mercury sync, Settings, + Add Flow, Legend, browser fullscreen, theme toggle (the existing `ThemeToggle`), search (`⌘K`), `×`.
  - Search needs a small `provide('openCommandPalette')` in `AppShell.vue`, injected here.
- **Where the displaced pieces go:**
  - **KPI chips (top left):** Today's balance (hover/click opens a popover with the Mercury per-workspace breakdown and sync status), window minimum, days to negative, reserve floor, 90-day low, next outflow and next inflow (each with its deal tag).
  - **Overdue:** a chip "2 overdue · $5,080". Click opens a popover holding the existing `OverdueTransactionsStrip` (bulk Done and postpone included).
  - **Recurring series:** a section in the legend panel, with edit and delete.
  - **Day detail:** the click modal (E).
  - **Deals panel:** the legend (C) plus the bottom sheet (D).
  - **Toast:** stays as it is (z-50, above the overlay).
- **Mobile:** the KPI chips scroll horizontally; the action bar collapses into a `⋯` menu; the legend becomes a full-width sheet.

### B. Deal colors and attribution (everywhere, not only in theater)
- **New `components/liquidity/dealColors.ts`** (pure):
  - an 8-color categorical palette, checked against the `dataviz` skill for contrast in light and dark;
  - `assignDealColorByDealKey(importedDeals)`: the slot comes from a hash of `${deal_board}:${deal_id}`, probing for collisions in deal-key order, so it's deterministic across devices and mostly stable when a deal is added;
  - `dealKeyOfTransaction(txn)`.
- **New `composables/useLiquidityDealAttribution.ts`:** the view `provide`s `dealAttributionForTransaction(txn) → { dealAddress, dealColor } | null` (null for manual rows and recurring occurrences).
- **New `components/liquidity/DealAttributionTag.vue`** (colored dot + short address chip):
  - it `inject`s the function, with a default of null, so existing contract tests that mount without it are untouched;
  - the row it sits on gets a left border accent in the deal's color.
- **Used in:** `DayDetail.vue`, `OverdueTransactionsStrip.vue`, the `TimelineChart.vue` tooltip rows, `LiquiditySidebar.vue` (next outflow and inflow), and `LiquidityDealsPanel.vue` (a color dot by the address).

### C. Legend panel (theater, top left under the chips)
- **New `theater/DealLegendPanel.vue`:** a non-modal floating panel that leaves the chart interactive (so not `UiDrawer`, whose `inertOutside` would lock the chart). It is collapsible, and its open state is remembered in `localStorage` (wrapped in try/catch).
- **Each deal row:**
  - color dot, address (link to its board), Bought / My Deals badge;
  - a red pill `N overdue` (from `overdue_open_row_count`), plus the refi-late and out-of-date badges with "Review changes";
  - a `⋯` menu → "Remove from timeline".
- **Hovering a deal** highlights its rows on the chart and dims the others (`highlightedDealKey`).
- **Clicking a deal** expands an inline drawer with its overdue items (`store.overdueMoneyOut` + `expectedMoneyInNotCounted`, filtered by `source_deal_board`/`source_deal_id`). Each item has the row actions: Done, the postpone chips, date, amount.
- **"Remove from timeline":** a confirm naming the address and the open-row count, then the EMD refund question, then the existing `store.removeOpenDealRows`, with a toast.
- **Also listed:**
  - an "Other flows" entry (neutral), for manual rows;
  - the Recurring section (from A).

### D. Bottom sheet: deals and milestones
- **New `theater/DealMilestonesBottomSheet.vue`**
  - **Collapsed bar** pinned to the bottom: "Deals · 1 · 5 overdue milestones ⌃". Click or `D` slides the sheet up with `transform: translateY`.
  - **Contents:** a horizontal scroll-snap carousel of deal cards, with ‹ › buttons and a top border in the deal's color.
  - **Each card:** the address; the five milestones in date order, each with planned date, state, a **Done** button and Move; and the row counts.
  - **Approved milestones** are muted (greyed, with a check, no Done).
  - **Overdue milestones** are marked red.
- **New `composables/useOneTapMilestoneApproval.ts`:**
  - `previewMilestoneChange(approve: true, new_date: planned_date)`;
  - if added + updated + removed + kept_no_longer_in_the_deal is 0 → `applyMilestoneChange` + toast;
  - otherwise it opens the existing `DealMilestoneChangeModal` (the view's `milestoneChange` ref).
  - Move opens that modal as today.

### E. Hover tooltip and click modal
- **`TimelineChart.vue`** gains optional props, so the existing contract and tests stay as they are:
  - `tooltipFollowsPointer`: the tooltip sits next to the crosshair and flips at the edges (theater sets it);
  - **touch (refinement 2):** the hover state is set only for `pointerType` mouse or pen, and `tooltipFollowsPointer` is off under `(hover: none)`. On a phone, a tap opens `DayTransactionsModal` directly, with no tooltip in the way, and a drag still pans;
  - `dealColorForTransaction`: the deal color of each tooltip row;
  - `highlightedDealKey`;
  - a "deal dots" strip just above the x-axis: one small dot per deal with rows that day.
- **Today, emphasized** (both modes):
  - a glow behind the today line: a wide, low-opacity stroke of the same `C.todayLine`, plus the existing dashed line;
  - a "TODAY" pill at the top of the plot;
  - a "← Today" / "Today →" edge chip when today is scrolled out of view; clicking it re-centers.
  - No new `chartToken()` reads (`chartTokens.test.ts` requires each of the 32 to be read exactly once): only the existing `C.*` values are reused.
- **New `theater/DayTransactionsModal.vue`** (in theater, a day click opens it instead of the inline DayDetail). A near-fullscreen `UiModalPanel size="full"` with a scale and fade entry. Its contents:
  - **Day summary:** the date, the opening balance (the previous EOD), money in, money out, EOD, and ‹ › to step days (and `←`/`→`).
  - **"Milestones on this day":** the imported deals' milestones planned that day, with **Approve** (one tap, D) and **Move**.
  - **The existing `DayDetail`:** Done, the postpone chips (+1 day, +1 week, next 1st) as **Postpone**, the date picker as **Move**, inline amount, edit, delete, + Add flow. Every row has its deal tag and colored left border.

### F. Backend: a deal with no open rows stops getting late-refi rows (decision 1)
- **Today**, `refresh_late_refis` would add a removed deal's late-refi months back on the next load.
- **Change:** in `BackEnd/BL/liquidity/dealCashRows/liquidity_deals.py`, `refresh_late_refis` skips deals with no open rows.
- **`list_imported_deals` keeps listing every deal with rows, Done-only ones included** (`open_row_count = 0`), so their Done rows keep their address and color (refinement 1).
- **Hidden in the frontend:** the legend, the bottom sheet and the normal Deals panel show only deals with `open_row_count > 0`. Deal attribution and color assignment use the full list.
- **Re-import:** it works as before, and its Done rows match by identity, so they stay done (`kept_done`).

### G. Polish
- **Motion:** `transform`/`opacity` transitions only, through the existing `UiTransition` presets (`drawer`, `fade`, `listItem`), and disabled under `prefers-reduced-motion`.
- **Focus:** it moves into the theater on open and back to the toggle on close; the modal has `aria-modal` and its own heading.

## Todo (estimates)
- [ ] Commit this plan as `tasks/todo/LiquidityTheaterMode.md` (5 min)
- [ ] B: `dealColors.ts`, attribution composable, `DealAttributionTag`, wired into DayDetail, overdue strip, sidebar, deals panel (60 min)
- [ ] E: TimelineChart today emphasis, follow-pointer tooltip, deal-colored tooltip rows, deal dots, highlight (75 min)
- [ ] A: `LiquidityTheaterMode` shell, URL state, Esc stack, shortcuts, browser fullscreen, action bar, KPI chips + Mercury popover, overdue chip popover; AppShell `openCommandPalette` provide (120 min)
- [ ] C: `DealLegendPanel` with overdue pills, inline overdue drawer, Remove from timeline, recurring section (75 min)
- [ ] D: `DealMilestonesBottomSheet` + `useOneTapMilestoneApproval` (75 min)
- [ ] E: `DayTransactionsModal` with milestones-on-this-day and day stepping (60 min)
- [ ] F: backend `refresh_late_refis` skips deals with no open rows; frontend hides those deals in the legend, the sheet and the Deals panel (20 min)
- [ ] MCP support: update the `remove_liquidity_deal_open_rows` description and `INSTRUCTIONS` in `BackEnd/mcp_server.py` (removing a deal's open rows takes it out of the timeline and stops its late-refi months), and their MCP tests if any pin the text. No new endpoint, so no new tool (15 min)
- [ ] Tests (below) (120 min)
- [ ] Security task, from `.claude/security.md`: "Please check through all the code you just wrote and make sure it follows security best practices. make sure there are no sensitive information in the frontend and there are no vulnerabilities that can be exploited throughout all the code in this repo". Concretely (30 min):
  - no `v-html`;
  - deal addresses and descriptions rendered as text only;
  - `localStorage` holds only UI flags;
  - the `?view=` query is whitelisted;
  - the Mercury account data shown in theater is the same as already shown;
  - no new secrets or env in the frontend;
  - the backend filter adds no new input;
  - then `/security-review` on the diff.
- [ ] `npm run build`, `npm test`, `npm run audit`, the contrast audit, pytest; push; open the PR (20 min)

## Tests
**Unit (vitest)**
- `dealColors.test.ts`:
  - the same deals give the same colors;
  - ≤ 8 deals get distinct colors;
  - adding a deal keeps the existing colors when no collision happens;
  - a manual row gets no deal.
- `useLiquidityDealAttribution.test.ts`:
  - a row maps to its deal by board and id;
  - a Done row of a deal with no open rows keeps its address and color;
  - a recurring occurrence or manual row maps to null.
- `TimelineChart.test.ts` (touch): a touch `pointermove` sets no hover tooltip; a tap emits `selectDay`.
- `TimelineChart.test.ts` (add to it):
  - today badge and glow rendered;
  - the edge chip shows when today is off-screen and re-centers on click;
  - the tooltip follows the pointer only with the prop;
  - tooltip rows show the deal color;
  - the existing cases still pass.
- `LiquidityTheaterMode.test.ts`:
  - opens and closes with `×`;
  - Esc closes the layers in order;
  - Esc is ignored while `isAnotherDialogOpen`;
  - shortcuts are ignored inside inputs;
  - the query is set and cleared.
- `DealLegendPanel.test.ts`:
  - deal rows, colors and overdue pills;
  - a click lists only that deal's overdue rows;
  - Remove asks for confirmation and emits; Cancel emits nothing.
- `DealMilestonesBottomSheet.test.ts`: one card per deal; an approved milestone is muted with no Done; Done emits.
- `useOneTapMilestoneApproval.test.ts`: zero changes → applies without the modal; with changes → opens the modal; a failed preview → error toast.
- `DayTransactionsModal.test.ts`: the day summary figures; the milestones of that day; deal tags; day stepping.
- `DayDetail` / `OverdueTransactionsStrip`: a deal tag shows when attribution is provided and is absent otherwise (existing contract tests unchanged).

**Integration (pytest, `BackEnd/tests/test_liquidity_deal_import.py`)**
- After `remove-open-rows`, `GET /liquidity/deals` lists the deal with `open_row_count = 0` (its Done rows keep their address).
- `refresh-late-refis` adds no rows for it.
- Re-importing brings its open rows back, and its Done rows stay done.

**E2E (Playwright, new `e2e/flows/liquidity-theater-mode.spec.ts`, plus an axe check)**
- Open theater: the app sidebar and the Upcoming rail aren't visible and the chart is the full width. Esc and `×` exit. The `?view=theater` deep link opens it.
- Legend: a deal's overdue pill → its inline overdue list → Done on one item.
- Bottom sheet: Done on a milestone with no row change → muted.
- Hover tooltip shows the deal-tagged rows. A click opens the day modal; Postpone moves the row.
- Remove from timeline → confirm → the deal is gone from the legend.
- Existing liquidity specs and network goldens stay green. Goldens change only in a `Golden update:` commit if needed.

## Critical files
- New:
  - `frontend/src/components/liquidity/theater/{LiquidityTheaterMode,DealLegendPanel,DealMilestonesBottomSheet,DayTransactionsModal}.vue`
  - `frontend/src/components/liquidity/{dealColors.ts,DealAttributionTag.vue}`
  - `frontend/src/composables/{useLiquidityDealAttribution,useOneTapMilestoneApproval}.ts`
- Edited:
  - `frontend/src/views/LiquidityTimeline.vue`
  - `frontend/src/components/liquidity/{TimelineChart,DayDetail,OverdueTransactionsStrip,LiquiditySidebar,LiquidityDealsPanel}.vue`
  - `frontend/src/components/shell/AppShell.vue` (the provide only)
  - `BackEnd/BL/liquidity/dealCashRows/liquidity_deals.py`
  - `BackEnd/mcp_server.py`
- Reused as they are:
  - `store.removeOpenDealRows` / `previewMilestoneChange` / `applyMilestoneChange` / `overdueMoneyOut`
  - `TransactionRowActions`, `InlineAmountEditor`, `DealMilestoneChangeModal`, `DealImportPreviewModal`
  - `UiModalPanel`, `UiTransition`, `ThemeToggle`
  - `addDays` / `firstOfNextMonth` / `todayISO` (`utils/liquidityEngine.ts`)

## Verification
- `cd frontend && npm run build && npm test && npm run audit && npm run audit:contrast`
- `npx playwright test e2e/flows/liquidity*.spec.ts e2e/flows/a11y.spec.ts`
- `cd BackEnd && pytest tests/test_liquidity_deal_import.py`
- Run the app (`/run`), open `/liquidity?view=theater`, and screenshot it at desktop and phone widths, light and dark: today emphasis, legend, bottom sheet, hover tooltip, day modal.
