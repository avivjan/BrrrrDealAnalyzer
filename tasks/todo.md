# UI v3 todo

Approved plan: `docs/plans/2026-09-06-ui-v3-plan.md`. Estimates are agent wall-clock minutes (see the plan for how the ~10 h total is reached). Checked = committed and its targeted tests green.


## Phase 1 — Fixes (items 4, 5, 6) · **≈ 1 h 35 wall-clock** (2 h 30 sequential)

- [x] **1.0** (10 min) — Tag `ui-v3-baseline` on the branch base; overwrite `docs/plans/2026-09-06-ui-v3-plan.md` with this plan (keep 
- [x] **1.1** (10 min) — Aurora dark glass → `glass
- [x] **1.2** (5 min) — Scrollbar track → transparent (global + `.custom-scrollbar`).
- [x] **1.3** (5 min) — Golden update A
- [x] **1.4** (10 min) — Remove `liquidity.back`, `reps.back` (+ unused `useRouter`), `analyze.home`, and toolbar cross-links `mydeals.
- [x] **1.5 ‖A** (40 min) — One field anatomy — label row `h-5 items-center`, control row `min-h-[42px]` — in `MoneyInput`, `NumberInput`,
- [x] **1.6** (25 min) — Deal modals
- [x] **1.7 ‖A** (30 min) — Liquidity `TransactionForm`/`SettingsPanel`
- [x] **1.8 ‖A** (20 min) — `e2e/checks/alignment.spec.ts`
- [ ] **exit** (5 min) — `verify:ui --fast`; Aurora dark screenshots of all routes.

## Phase 2 — Motion foundation (item 2) · **≈ 1 h 40 wall-clock** (2 h 35 sequential)

- [ ] **2.1 ‖B** (25 min) — `hero` preset (eyebrow → title → figures, ≤ 450 ms, enter-only) + tests.
- [ ] **2.2 ‖B** (30 min) — `v-tilt` directive (≤ 6°, `(hover:hover)` only, `gsap.set` per rAF, reset tween on leave, released on unmount,
- [ ] **2.6 ‖B** (30 min) — Extend `no-live-tweens.spec.ts` (hero, hover, column scroll, list reflow); add `e2e/checks/perf.spec.ts` (CLS 
- [ ] **2.4** (15 min) — Promote `UiTimelineRail`, `UiProgressRing`, `UiSparkline`, `UiTooltip`, `UiSegmented` into `UI_COMPONENTS` (+ 
- [ ] **2.3** (35 min) — Attach existing surfaces
- [ ] **2.5** (20 min) — Drag polish
- [ ] **exit** (15 min) — Full gate 1

## Phase 3 — Two cards (item 1, 7) · **≈ 1 h wall-clock** (1 h 45 sequential)

- [ ] **3.1 ‖C** (40 min) — `DealCard` → verdict card
- [ ] **3.2 ‖C** (65 min) — `BoughtDealCard` → progress card

## Phase 4 — Bought Deals flow tracker (items 1, 7) · **≈ 3 h sequential**

- [ ] **4.0** (25 min) — Stage moves keep ticks. View helper `moveDealToStage(deal, stageId)`
- [ ] **4.1** (20 min) — Header with `hero`
- [ ] **4.2** (20 min) — Flow strip
- [ ] **4.3** (70 min) — Stage-rail board on `lg+`
- [ ] **4.4** (45 min) — Modal

## Phase 5 — My Deals board (item 1) · **≈ 1 h 25 sequential**

- [ ] **5.1** (20 min) — Header with `hero`
- [ ] **5.2** (35 min) — Five stage columns on `lg+` via `StageColumn.vue` (rows below `lg`, touch fallback list kept); same `VueDragga
- [ ] **5.3** (15 min) — Modal header
- [ ] **exit** (15 min) — Full gate 2

## Phases 6 + 7 — Liquidity line, REPS, Analyze (items 2, 3) · **≈ 1 h 50 wall-clock** (2 h 30 sequential)

- [ ] **6.1 ‖D** (20 min) — Pure `linePath`/`areaPath` + tests.
- [ ] **6.2 ‖D** (50 min) — Remove bars; area fill under the line with the 8 inflow/outflow tokens as gradient stops (keeps the 32×once ru
- [ ] **6.3 ‖D** (35 min) — Page
- [ ] **7.1 ‖D** (25 min) — REPS
- [ ] **7.2 ‖D** (15 min) — Analyze
- [ ] **exit** (15 min) — Full gate 3

## Phase 8 — Closure · **≈ 45 min**

- [ ] **8.1** (25 min) — Full gate 4 on the final tree; `e2e:compare` vs `v2-final.json`; screenshots archived; Golden update B (`axe-b
- [ ] **8.2** (20 min) — Docs

## Review

_(filled in at Phase 8)_
