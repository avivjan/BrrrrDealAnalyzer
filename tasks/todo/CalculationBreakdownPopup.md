# CalculationBreakdownPopup: press any result tile to see the formula with the numbers

Branch `claude/epic-hamilton-c1p0rs` (harness-designated). Plan file on the branch:
`tasks/todo/CalculationBreakdownPopup.md`.

## Context

The owner suspects bugs in the analyze engine and wants to audit it from the UI instead of the code:
every result tile in the deal modal (My Deals and Bought Deals) should be pressable and open a popup
that shows the exact formula, with the concrete numbers, that produced the number on the tile.

The data already exists. Since `CalcExplainSplit`, the backend explain layer
(`BackEnd/BL/analyze/explain/brrr.py`, `explain/flip.py`) emits `breakdowns: Record<sectionKey, CalcStep[]>` on
every analyze and deal response. Each `CalcStep` is `{label, value, unit, formula, terms?, note?}` with the numbers
substituted (e.g. `ARV ($200,000) × LTV 75% = $150,000`), and every stated equation is guarded at runtime against
the engine (`CalcExplainMismatch`), so the text cannot drift from the math. `GET /active-deals`, `GET /bought-deals`
and `POST /analyze/*` all carry it (`BL/common/deal_response.py` merges `calculate_*_results(deal).model_dump()`),
and `frontend/src/types/index.ts:127-154` already types it (`CalcStep`, `CalcTerm`, `CalcBreakdowns`,
`breakdowns?` on `BrrrAnalyzeRes` and `FlipAnalyzeRes`). Only the PDF renders it; no Vue component reads it.

Every tile key in both modals matches a breakdown section key one-to-one:

| Deal type | Tile keys (= section keys in `BRRR_SECTIONS` / `FLIP_SECTIONS`) |
| --- | --- |
| BRRRR (12) | cash_flow, cash_out, cash_out_routi, cash_on_cash, dscr, equity, roi, net_profit, total_cash_needed_for_deal, cash_to_close_buy, cash_out_routi_conservative, stolen_money |
| Flip (7) | net_profit, roi, annualized_roi, total_cash_needed, total_cash_needed_with_buffer, total_holding_costs, total_hml_interest |

So this is a frontend-only feature: no new math in TypeScript, no new endpoint.

**Owner decisions (asked and answered):** scope = the modal result tiles only (not the board cards); the engine
mismatches found while reading (§ "Noticed, not changed") are listed for a follow-up, not fixed here.

## Design

### 1. `frontend/src/components/deal/CalculationBreakdownPopup.vue` (new)

The popup. Copies the house overlay pattern from `components/ui/UiDrawer.vue:57-165`: `<Teleport to="body">`,
`<UiTransition preset="modalEnterOnly">` (the PDF preview at `MyDeals.vue:1406-1463` uses the same preset),
scrim `fixed inset-0 z-[60] bg-fg/60` with `@click.self` close (`z-[60]` sits above the deal modal's `z-50`),
`UiModalPanel size="md"` inside, a `document` keydown listener registered only while open
(`Escape && !defaultPrevented` → `preventDefault()` + `emit("close")`), focus moved into the panel on open and
restored to the pressed tile on close, `inertOutside(overlayRoot)` from `components/ui/inertOutside.ts` while open.
Neither view handles Escape today, so nothing below can collide.

```ts
props: { open: boolean; metricLabel: string; metricKey: string; steps?: CalcStep[] }
emits: { close: [] }
```

- Header: `<h2>` "How {metricLabel} is calculated" + the headline value (the headline step, formatted by its unit)
  + `UiIconButton label="Close"` (`pi pi-times`).
- Body: `<ol>` of the steps in order. Per step: `label`; `formula` in `font-mono text-sm tabular` (the string
  with the concrete numbers); the value formatted by unit; `terms` (when present) stacked one `<li>` per operand as
  `sign label … value` with the total under them; `note` in `text-xs text-fg-muted`. The last step is the headline
  (`data-part="headline"`, stronger border) so the final result reads as the answer.
- Empty state (`data-part="empty"`): "No breakdown available for this result." (a response without `breakdowns`).
- Footer, one line: money in dollars, percentages as shown, ratios as a multiple (1.20x); "∞" / "-∞" mean the
  divisor was zero; a note under a step explains a convention.
- Formatter `formatCalculationStepValueByUnit(unit, value)` in a sibling `calculationStepFormat.ts` (unit-tested):
  `money` → `Intl.NumberFormat` USD, 0 decimals when whole else 2 (mirrors `_money` in `deal_pdf.py`);
  `pct` → `-1 → "∞%"`, `-2 → "-∞%"`, else `toFixed(2) + "%"`; `ratio` → `toFixed(2) + "x"`; missing unit → money.
- All text through `{{ }}` interpolation, no `v-html`.

### 2. `frontend/src/components/deal/ResultTileWithCalculationButton.vue` (new)

Wraps the existing `UiStatTile` so the 19 tiles per view change only their open/close tags.

```ts
props: { metricLabel: string; metricKey: string }
emits: { showCalculation: [{ metricKey: string; metricLabel: string }] }
slot: default — the existing value element, untouched
```

```vue
<div class="group relative">
  <UiStatTile tone="neutral" class="bg-surface">
    <template #label>{{ metricLabel }} <i class="pi pi-calculator ml-1 text-[0.7em] opacity-60 group-hover:opacity-100 touch:opacity-100" aria-hidden="true" /></template>
    <slot />
  </UiStatTile>
  <button type="button" :data-testid="`result-tile.${metricKey}.show-calculation`"
          :aria-label="`Show how ${metricLabel} is calculated`"
          class="absolute inset-0 rounded-card hover:bg-primary/5 focus-visible:ring-2 focus-visible:ring-primary"
          @click="emit('showCalculation', { metricKey, metricLabel })" />
</div>
```

The button is a sibling laid over the tile (a `<div>` inside a `<button>` is non-conforming). `group-hover` is paired
with `touch:` for the G-HOVER gate. Trade-off: the value text is no longer selectable (a readout; acceptable).

### 3. View wiring (`MyDeals.vue`, `BoughtDeals.vue`)

- Import both components (deal-specific, imported explicitly like `DealInputsForm`; not added to `ui/index.ts`).
- One ref per view next to `currentAnalysis` (`MyDeals.vue:308`, `BoughtDeals.vue:247`):
  `const pressedResultTileForCalculationBreakdown = ref<{ metricKey: string; metricLabel: string } | null>(null)`.
- Tiles (`MyDeals.vue:1021-1099`, `BoughtDeals.vue:1060-1216`): each
  `<UiStatTile tone="neutral" class="bg-surface"><template #label>Cash Flow</template>` becomes
  `<ResultTileWithCalculationButton metric-label="Cash Flow" metric-key="cash_flow" @show-calculation="pressedResultTileForCalculationBreakdown = $event">`;
  the inner `<div v-flash data-testid="mydeals.modal.result.cash_flow">…</div>` stays byte-for-byte, so the existing
  test ids, `v-flash`, colours and the settle/E2E assertions keep working.
- One popup instance per view, after the PDF preview transition (outside the `v-reveal` grid; teleported anyway):
  ```vue
  <CalculationBreakdownPopup
    :open="pressedResultTileForCalculationBreakdown !== null"
    :metric-key="pressedResultTileForCalculationBreakdown?.metricKey ?? ''"
    :metric-label="pressedResultTileForCalculationBreakdown?.metricLabel ?? ''"
    :steps="pressedResultTileForCalculationBreakdown ? currentAnalysis?.breakdowns?.[pressedResultTileForCalculationBreakdown.metricKey] : undefined"
    @close="pressedResultTileForCalculationBreakdown = null" />
  ```
  Bound to `currentAnalysis`, so after the debounced re-analyze the popup shows the fresh numbers.
- `closeModal` (`MyDeals.vue:346`, `BoughtDeals.vue:284`) also clears the ref so a popup never outlives its modal.

### 4. Backend: one contract test, no code change

`BackEnd/tests/test_explain.py` gains `TestEverySectionKeyHasBreakdownSteps` (BRRRR + Flip, over the existing
scenario matrix): every key in `BRRR_SECTIONS` / `FLIP_SECTIONS` is present in `breakdowns` with a non-empty list,
and contains a step whose value is the headline result itself, of the section's unit (the popup's headline relies
on this); plus
`TestFrontendResultTileKeysAreSections` with the hard-coded 12 + 7 tile keys asserted to be a subset of the sections.

## Files

Create: `frontend/src/components/deal/CalculationBreakdownPopup.vue`, `CalculationBreakdownPopup.test.ts`,
`calculationStepFormat.ts`, `calculationStepFormat.test.ts`, `ResultTileWithCalculationButton.vue`,
`ResultTileWithCalculationButton.test.ts`, `frontend/src/views/MyDeals.calculationBreakdown.contract.test.ts`,
`frontend/src/views/BoughtDeals.calculationBreakdown.contract.test.ts`, `tasks/todo/CalculationBreakdownPopup.md`.
Modify: `frontend/src/views/MyDeals.vue`, `frontend/src/views/BoughtDeals.vue`, `BackEnd/tests/test_explain.py`,
`frontend/README.md` (one paragraph on the two components).
Untouched: engine, schemas, `mcp_server.py`, `frontend/e2e/` (owner's standing instruction; an optional spec is
listed below), audit goldens (`npm run audit` is advisory and already drifting; not rebaselined here).

## Tests (rule 3)

- **Unit** — `calculationStepFormat.test.ts` (money whole/decimal/negative, pct incl. the -1/-2 sentinels, ratio,
  missing unit); `CalculationBreakdownPopup.test.ts` (mount `attachTo: document.body`: nothing rendered and no
  listener when closed; heading + headline value; every step in order with label, formula text and formatted value;
  terms stacked with sign; note rendered muted; empty state; close on X, on Escape at document level
  (with `preventDefault`, and ignored when already prevented), on scrim click but not on panel click; focus in on
  open, restored on close); `ResultTileWithCalculationButton.test.ts` (label + calculator hint, slotted value and its
  `data-testid` untouched, accessible name "Show how Cash Flow is calculated", emits `showCalculation` payload).
- **Integration** — `MyDeals.calculationBreakdown.contract.test.ts` (same scaffolding as
  `MyDeals.settle.contract.test.ts:1-80`, fixture with `breakdowns.cash_flow`): pressing the Cash Flow tile opens the
  popup with that section's formula text while `mydeals.modal` and `mydeals.modal.result.cash_flow` stay intact;
  Escape closes only the popup; opening triggers no analyze/save call; a response without `breakdowns` shows the
  empty state; after a re-analyze (the `editTask` + 500 ms pattern) the popup reads the fresh breakdown.
  `BoughtDeals.calculationBreakdown.contract.test.ts`: the first two cases on the bought modal.
  Backend: the two `test_explain.py` classes above. Existing suites unchanged.
- **E2E** — optional and not run (owner's standing instruction on Playwright): `e2e/flows/calculation-breakdown.spec.ts`
  would open a deal, click `result-tile.cash_flow.show-calculation`, assert the formula, press Escape, assert the modal
  is still visible.

## Todo (≈ 2 h 45)

- [x] **B1** (10 min) — Plan file `tasks/todo/CalculationBreakdownPopup.md` on the branch.
- [x] **B2** (15 min) — `calculationStepFormat.ts` + its test.
- [x] **B3** (35 min) — `CalculationBreakdownPopup.vue` (Teleport, transition, Escape, focus, inert, steps/terms/notes, empty state, footer) + test.
- [x] **B4** (15 min) — `ResultTileWithCalculationButton.vue` + test.
- [x] **B5** (25 min) — Wire both views: imports, ref, 19 tiles each, popup instance, `closeModal` reset. `npm run build` green.
- [x] **B6** (25 min) — The two view contract tests; backend `test_explain.py` section-coverage tests.
- [x] **B7** (5 min) — MCP (rule 4): no new endpoint or field; `breakdowns` already reaches `get_deal` / full dumps; run `pytest tests/test_mcp*.py` to confirm OpenAPI goldens unchanged.
- [x] **B8** (10 min) — Security (`.claude/security.md`): "Please check through all the code you just wrote and make sure it follows security best practices. make sure there are no sensitive information in the frontend and there are no vulnerabilities that can be exploited throughout all the code in this repo." Expected: labels/formulas/notes render via interpolation only (no `v-html`); `metricKey` used only as a record lookup and a test id; no new network calls, dependencies or secrets; `npm audit` unchanged.
- [x] **B9** (10 min) — `frontend/README.md` paragraph; `cd frontend && npm test && npm run build`; `cd BackEnd && pytest tests/test_explain.py tests/test_mcp*.py`; smoke both modals by hand (BRRRR and Flip tiles, Escape, scrim, focus return).
- [x] **B10** (10 min) — Commit, push `-u origin claude/epic-hamilton-c1p0rs`, open the PR with the "Noticed, not changed" list.

## Verification

1. `cd frontend && npm test` — new unit + contract tests green, existing settle/contract tests untouched.
2. `cd frontend && npm run build` — `vue-tsc` accepts `currentAnalysis?.breakdowns?.[key]` on both response unions.
3. `cd BackEnd && pytest tests/test_explain.py tests/test_mcp*.py` (needs the throwaway Postgres from
   `docker-compose.test.yml`; if Docker is unavailable in the sandbox, report which ran).
4. Manual: open a BRRRR deal in My Deals, press each of the 12 tiles and read the chain (e.g. Cash Flow → Operating
   Expenses, NOI, Mortgage, Cash Flow); same for a Flip deal and for Bought Deals; Escape closes only the popup;
   edit an input, wait for the re-analyze, reopen the popup and see the new numbers.
5. `npm run audit` is advisory: expect G3/bindings/text drift on the two views (the same pre-existing situation the
   last three tasks reported); not rebaselined.

## Noticed, not changed (owner: list for a follow-up)

Found while mapping the engine for this task; the popup will make each one visible from the UI.

1. **CoC / ROI sentinels** (`deal_math.py:106-114`): whenever `cash_out >= 0` they return -1 ("∞") even when
   cash flow is negative; `cash_out == 0` also counts as infinite. `DealCard.vue:120` then draws a full green ring
   for a money-losing deal.
2. **ROI definition**: code is `(12 × cash_flow + net_profit) ÷ |cash_out|`, and `net_profit` already includes
   `cash_out`; the field description says "net profit divided by the cash invested".
3. **DSCR description** (`analyze_results.py:30-32`) says "NOI ÷ annual mortgage"; code is `rent ÷ PITIA`.
4. **Flip descriptions**: `total_holding_costs` omits that HML interest is included; `total_cash_needed_with_buffer`
   says "rehab contingency buffer" but the code applies ×1.1 / ×1.5 multipliers plus a 10% rehab float.
5. **My Deals header average CoC** (`MyDeals.vue:60-66`) averages the -1/-2 sentinels as real numbers.
6. **Card `formatMoney`** (`DealCard.vue:92`, `BoughtDealCard.vue:119`): `$0` renders as "-", negatives as
   `$-1,234`; Cash Flow turns red at exactly 0.
7. **Bought card labels**: "Cash in" is Cash Needed (includes cushion and the stress-test cash to the refi table);
   "Refi target" is the gross loan (ARV × LTV), not the wire.
8. **`compact.py:129`** `bought_total_cash_invested` sums `total_cash_needed`.
9. **Stale comment** `types/index.ts:81` still describes recording/transfer as 0.55% × purchase loan.
10. **`analyze_brrr` MCP description** promises warning messages; BRRRR always returns `messages=None`.

## Review

**What changed.** Frontend only. `components/deal/ResultTileWithCalculationButton.vue` wraps each of the 19
result tiles per modal (12 BRRRR, 7 Flip) in My Deals and Bought Deals: the same `UiStatTile` readout, a
calculator glyph in the caption and a transparent button laid over it ("Show how Cash Flow is calculated"); the
value element with its `*.modal.result.<key>` test id is untouched. Pressing it opens
`components/deal/CalculationBreakdownPopup.vue`, teleported above the modal, which renders
`currentAnalysis.breakdowns[<key>]`: every step's label, the formula with the concrete numbers, the value read by
its unit (`calculationStepFormat.ts`, mirroring the PDF's formatters incl. the ∞ / -∞ sentinels), a sum step's
operands stacked with their sign, and the note; the step carrying the tile's own value is marked as the headline
and shown in the header. It closes on Escape (claimed with `preventDefault`), the scrim and ×, moves focus in and
back, and makes the page behind it inert. The popup is bound to `currentAnalysis`, so after the debounced
re-analyze it shows the fresh numbers. `closeModal` clears it.

**Found while smoke-testing.** The lowest-ARV wire section does not end on the wire: its last step is "Cash to
Refi Table (Lowest ARV)". The first cut showed that as the headline. The popup now takes the tile's value
(`metricValue`) and marks the step carrying it; the backend contract test requires every section to contain a
step whose value equals the headline result (`TestEverySectionKeyHasBreakdownSteps`), not merely to end on one.

**Tests (rule 3).** Unit: `calculationStepFormat.test.ts` (4), `ResultTileWithCalculationButton.test.ts` (3),
`CalculationBreakdownPopup.test.ts` (13: closed, heading + headline, steps in order, terms stacked, notes, units and
sentinels, headline by value with fallback, empty state, close paths, Escape claimed / ignored when claimed, listener
only while open, focus + inert). Integration: `MyDeals.calculationBreakdown.contract.test.ts` (6: opens with the
section's formulas above the modal, every BRRRR tile pressable, Escape closes only the popup, no analyze or save
from a press, empty state without breakdowns, fresh breakdown after a re-analyze) and
`BoughtDeals.calculationBreakdown.contract.test.ts` (2). Backend: section coverage over the scenario matrix and
the frontend tile keys pinned as sections (+25). E2E: none added (Playwright untouched per the standing
instruction); a Playwright smoke against the real app (throwaway Postgres, backend, Vite) was run by hand and the
two popups screenshotted. Frontend 1476 passed, `vue-tsc` + `vite build` clean; backend 737 passed.

**MCP (rule 4).** No new endpoint or field; `breakdowns` already reaches `get_deal` and the full dumps.
`test_mcp*.py` green, OpenAPI goldens unchanged.

**Security (rule: `.claude/security.md`).** Labels, formulas, notes and terms render through interpolation only
(no `v-html`, no `innerHTML`); `metricKey` is used only as a record lookup and in a test id; no new network calls,
dependencies or secrets; `npm audit` reports 0 vulnerabilities.

**Not done here (owner's choice): the engine mismatches** listed under "Noticed, not changed" stay for a follow-up.

**Trade-off to know.** The overlay button covers the tile, so the value text is no longer selectable with the mouse.
