# DealImpactSimulator: "Import to liquidity" becomes a full-screen decision view

On `claude/zen-brown-nv5tlv`. If avivjan/BrrrrDealAnalyzer#126 is merged by then, `main` is merged in first and a new PR is opened. The first commit is this plan, saved as `tasks/todo/DealImpactSimulator.md`. Goldens change only in `Golden update:` commits.

## Context
`DealImportPreviewModal.vue` answers "can I afford this deal?" badly:
- a small modal;
- a 7-day chart window (the chart is fixed at 48 px a day and scrolls);
- seven stacked metrics, all equally loud.

On your example, the most important fact ("this deal takes you $54,935 below zero, from today, and you don't recover") is spread across four rows: lowest balance, below reserve for 781 days, first negative day, and "not in the timeline". It should look and feel like the liquidity theater page and answer three questions at a glance:
1. **Verdict:** safe, below my reserve, or negative?
2. **Crunch point:** the lowest balance before → after, when it happens, and how much cash would cover it.
3. **Exposure and recovery:** how long am I below the line, and does the refi bring me back?

The same view also serves "Review changes" (re-sync after a deal edit), opened from the legend and the deal boards.

## Design

### Layout (full screen, same look as the theater page)
`components/liquidity/dealImpact/DealImpactView.vue` replaces `DealImportPreviewModal.vue`'s markup. It keeps the props, emits, store calls and the `deal-import-preview*` test hooks, so both callers (`ImportDealToLiquidityButton.vue`, `LiquidityTimeline.vue`) are unchanged.
- **Frame:** teleported, `fixed inset-0 z-50` (above the theater's z-40), `bg-page`; Esc and × close it. Only opacity animates on the root; panels slide in with transform.
- **Top bar:**
  - the deal's color dot, its address, "Import to liquidity" or "Re-sync with liquidity";
  - figure chips: Cash today, the deal's money out / in;
  - Cancel and the primary action ("Import 37 rows" / "Re-sync N rows"). On a phone the action is a sticky bottom bar.
- **Verdict banner**, full width, under the top bar (C).
- **Body:** on desktop, the chart takes the left part (flex-1, about 60% of the height) and the insight rail is on the right (`w-[24rem]`, scrolls). On a phone the chart is about 45vh with the rail stacked below.

### A. The comparison chart: a new `DealImpactChart.vue`
A purpose-built SVG: fit to its width, no scrolling. `TimelineChart` stays as it is: its 48 px-a-day scroll suits the timeline page, not a whole-lifecycle comparison.
- **Range chips:** **Deal lifecycle** (default: a week before today through 60 days after the refi, or after the low point if later), **6 months**, **1 year**, **All**.
- **Lines:**
  - **Current** (without the deal): a thin muted line;
  - **With this deal**: a 2 px line in the deal's color (the same color the legend will give it);
  - the gap between them is shaded in the deal's color at low opacity: what the deal costs at each moment.
- **Danger zones** on the projected line: below the reserve, a warning tint under the dashed reserve line; below zero, a negative tint. The zero line and the reserve line are labelled at the right edge.
- **Annotations, the "where to look" layer:**
  - **Low point:** a pin with "Lowest −$54,935 · Dec 15".
  - **Key dates** as vertical flag rules: contract, purchase closing (with its outflow), rehab completed, refi (with what it brings back), the Nov 30 tax bill. These are the deal's key dates (backend, D).
  - **Back above the reserve:** a point with "Back above reserve · Mar 2", when there is one.
  - **Today:** the same TODAY pill and glow as the timeline page.
  - Labels that would collide are stacked or tucked into a "+2" chip.
- **Hover / tap:** a crosshair and a tooltip with the date, Current $X, With the deal $Y, Δ −$Z, and that day's deal rows. Arrow keys step through days.
- **Colors:** Tailwind tokens (`stroke-negative`, `fill-warning/10`, …), so every look and light/dark works. The deal color comes from `dealColors.ts`. No new `chartToken()` reads.
- **Geometry:** pure, in `dealImpact/dealImpactGeometry.ts` (x for a date over a range, y range including 0 and the reserve, the gap polygon, the zone runs, label stacking), unit-tested.

### B. Decision insights: a new pure `buildDealImpactDecision`
`utils/dealImpactDecision.ts`. It reuses `buildDealImportInsights` and `transactionsAfterDealChanges`, and adds:
- **riskLevel:**
  - `stays_above_reserve`;
  - `dips_below_reserve` (never below zero);
  - `goes_negative`.
  - Plus `alreadyBelowReserveWithoutTheDeal`, so a timeline that already breaches isn't blamed on the deal.
- **The crunch:**
  - the lowest balance before → after, with its date and the change;
  - **cash to keep your reserve** = max(0, reserve − lowest with the deal), needed by the first date below the reserve;
  - **cash to stay above zero** = max(0, −lowest with the deal), needed by the first negative date.
- **Cash tied up at the peak:** the deepest running total of the deal's own rows, i.e. the most money the deal has out at once.
- **Exposure:**
  - days below the reserve and days below zero;
  - the longest stretch below the reserve, with its from–to dates;
  - "doesn't recover in the timeline (ends <date>)" when it never comes back.
- **Recovery:** what the refi brings back (money in on the refi day), the date back above the reserve and the number of days after the refi, or how far short the timeline still ends.
- **The deal's cash:** money out, money in, net; the largest single day; and the next-30-days test (cash today vs the deal's money out in the next 30 days, as a covered percentage).

### C. How the insights are shown (signal first, details on demand)
1. **Verdict banner** (`data-testid="deal-impact.verdict"`, `data-risk-level`): an icon, a tone and one sentence that names the consequence.
   - **Negative:** "This deal takes you **$54,935 below zero** on **Dec 15, 2026** and doesn't recover in the timeline."
   - **Below reserve:** "You'd be under your $5,000 reserve for **42 days** (lowest **$2,100** on Feb 3)."
   - **Safe:** "You stay above your reserve: lowest **$18,400** on Feb 3."
   - A second line gives the fix: "Bring **$59,935** by **Nov 3** to keep your reserve."
2. **Three insight cards** in the rail, each one headline number plus one supporting line:
   - **Crunch point:** lowest before → after (with the change), its date, and the cash needed to keep the reserve and to stay above zero.
   - **Exposure & recovery:** days below the reserve / below zero as a compact bar over the deal's lifecycle; the refi's money back; the back-above-reserve date or "doesn't recover"; and the peak cash tied up.
   - **The deal's cash:** out / in / net, the largest day (usually the closing), and the next-30-days test as a progress bar.
3. **Details**, collapsed:
   - "By month": small bars of the deal's net per month, replacing the text chips;
   - "**37 rows to import**": the existing `DealCashRowChangesList`. In re-sync mode the list is open by default, because it's the point of the view.
4. **Re-sync mode** ("Review changes" on an already-imported deal; added in review):
   - The comparison is "**Now**" (the timeline with the deal's current imported rows) vs "**After these changes**" (with the deal's updated rows), in the chart's legend, its tooltip and the cards.
   - The verdict talks about the changes, not a new deal: "Applying these changes takes you $X below zero on …", "Applying these changes keeps you above your reserve", "These changes improve your lowest point by $Y".
   - When the changes barely move anything, the verdict says "These changes barely move your timeline (lowest $A → $B)".
   - The crunch card's before → after and the bridge cash compare those same two states.
   - Each phrase comes from `buildDealImpactDecision(..., mode: 'import' | 'resync')`.
5. **Primary action follows the verdict:** "Import 37 rows" normally. When the deal goes negative, it reads "Import anyway" with a warning tone. Nothing is blocked; the preview has already shown the consequence.

### D. Backend: the preview carries the deal's key dates
`DealCashRowChangesRes` (the import-preview / import response) gains `key_dates`, from the existing `key_dates_of_deal(deal)` (`BL/liquidity/dealCashRows/deal_cash_rows.py`), with the same fallback to the five milestones. The chart uses it for its flags; nothing else changes. MCP: the preview tool's description mentions `key_dates` (under 400 characters).

## Todo (estimates)
- [ ] Commit this plan (5 min)
- [ ] D: `key_dates` on the preview response + pytest; regenerate the OpenAPI snapshot in a `Golden update:` commit (25 min)
- [ ] B: `buildDealImpactDecision` + unit tests (60 min)
- [ ] A: `dealImpactGeometry.ts` + `DealImpactChart.vue` (lines, gap, zones, annotations, range chips, hover/tap/keys) + unit tests (150 min)
- [ ] C: `DealImpactView.vue` (frame, top bar, verdict, rail cards, details, sticky phone action); `DealImportPreviewModal.vue` renders it (90 min)
- [ ] MCP support: the import-preview description mentions `key_dates` (5 min)
- [ ] Tests (below) (75 min)
- [ ] Security task, from `.claude/security.md`: "Please check through all the code you just wrote and make sure it follows security best practices. make sure there are no sensitive information in the frontend and there are no vulnerabilities that can be exploited throughout all the code in this repo". Concretely (15 min):
  - addresses, descriptions and labels are text only, no `v-html`;
  - inline colors only from the palette;
  - `key_dates` exposes nothing the deal endpoints don't already;
  - then `/security-review` on the diff.
- [ ] Build, vitest, pytest; Playwright on Chromium and Mobile Chrome (re-record `liquidity-deal-import` in a `Golden update:` commit, since the preview response gains `key_dates`); screenshots; push; PR (30 min)

## Tests
**Unit (vitest)**
- `dealImpactDecision.test.ts`:
  - each risk level, worded for an import and for a re-sync (including "improves" and "barely moves");
  - a timeline already below the reserve without the deal;
  - the cash to keep the reserve / stay above zero and their needed-by dates;
  - the peak cash tied up;
  - the longest stretch below the reserve;
  - recovery after the refi vs "doesn't recover";
  - the next-30-days coverage.
- `dealImpactGeometry.test.ts`:
  - the x scale over the range chips;
  - the y range includes 0 and the reserve;
  - the gap polygon;
  - zone runs split at the reserve and at 0;
  - colliding labels are stacked.
- `DealImpactChart.test.ts`:
  - both lines and the gap;
  - the danger zones only where breached;
  - the low-point pin, the key-date flags and the recovery point;
  - the tooltip shows both balances and the delta;
  - a range chip changes the window;
  - a touch tap shows the tooltip.
- `DealImpactView.test.ts` (through `DealImportPreviewModal`):
  - the verdict text and tone per risk level;
  - the crunch card's numbers;
  - the rows list collapsed for an import and open for a re-sync;
  - the primary label ("Import N rows" / "Import anyway" / "Re-sync N rows");
  - in re-sync mode: "Now / After these changes" labels and the "Applying these changes…" verdict wording;
  - Esc and × close it;
  - confirming emits `imported`.

**Integration (pytest)**
- The import preview returns `key_dates` (the schedule's markers, the Nov 30 bill inside the hold).

**E2E (Playwright)**
- `liquidity-deal-import.spec.ts`: the preview opens full screen from the My Deals modal; the verdict and the crunch card are shown; the chart has both lines; the rows list expands; Import imports. It replaces the old insight-text assertions.
- `axe` on the open view; Chromium and Mobile Chrome.
- The `liquidity-deal-import` network golden is re-recorded (`key_dates`) in a `Golden update:` commit.

## Critical files
- **New:**
  - `frontend/src/components/liquidity/dealImpact/{DealImpactView,DealImpactChart}.vue`
  - `frontend/src/components/liquidity/dealImpact/dealImpactGeometry.ts`
  - `frontend/src/utils/dealImpactDecision.ts` (+ tests)
- **Edited:**
  - `frontend/src/components/liquidity/DealImportPreviewModal.vue` (renders the view)
  - `frontend/src/types/liquidity.ts`
  - `BackEnd/ReqRes/common/liquidity_deal_schemas.py`
  - `BackEnd/BL/liquidity/dealCashRows/liquidity_deals.py`
  - `BackEnd/mcp_server.py`
- **Reused:**
  - `store.previewDealImport` / `importDeal` / `seriesWithAndWithoutDealChanges`
  - `buildDealImportInsights` and `transactionsAfterDealChanges` (`utils/dealCashRowsPreview.ts`)
  - `DealCashRowChangesList`
  - `dealColors.ts`
  - `key_dates_of_deal`
  - the theater's chip and glass styling

## Verification
- `cd BackEnd && pytest`
- `cd frontend && npm run build && npm test`
- `npx playwright test e2e/flows/liquidity-deal-import.spec.ts e2e/flows/liquidity*.spec.ts --project=chromium --project="Mobile Chrome"`
- Screenshots at desktop and phone width, light and dark, of three seeded deals: safe, below the reserve, and negative (like your example).
