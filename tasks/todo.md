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
- [x] **exit** (5 min) — `verify:ui --fast`; Aurora dark screenshots of all routes.

## Phase 2 — Motion foundation (item 2) · **≈ 1 h 40 wall-clock** (2 h 35 sequential)

- [x] **2.1 ‖B** (25 min) — `hero` preset (eyebrow → title → figures, ≤ 450 ms, enter-only) + tests.
- [x] **2.2 ‖B** (30 min) — `v-tilt` directive (≤ 6°, `(hover:hover)` only, `gsap.set` per rAF, reset tween on leave, released on unmount,
- [x] **2.6 ‖B** (30 min) — Extend `no-live-tweens.spec.ts` (hero, hover, column scroll, list reflow); add `e2e/checks/perf.spec.ts` (CLS 
- [x] **2.4** (15 min) — Promote `UiTimelineRail`, `UiProgressRing`, `UiSparkline`, `UiTooltip`, `UiSegmented` into `UI_COMPONENTS` (+ 
- [x] **2.3** (35 min) — Attach existing surfaces
- [x] **2.5** (20 min) — Drag polish
- [x] **exit** (15 min) — Full gate 1 (148 passed; 3 CLS findings carried to Phases 4/5/7; webkit not available here)

## Phase 3 — Two cards (item 1, 7) · **≈ 1 h wall-clock** (1 h 45 sequential)

- [x] **3.1 ‖C** (40 min) — `DealCard` → verdict card
- [x] **3.2 ‖C** (65 min) — `BoughtDealCard` → progress card

## Phase 4 — Bought Deals flow tracker (items 1, 7) · **≈ 3 h sequential**

- [x] **4.0** (25 min) — Stage moves keep ticks. View helper `moveDealToStage(deal, stageId)`
- [x] **4.1** (20 min) — Header with `hero`
- [x] **4.2** (20 min) — Flow strip
- [x] **4.3** (70 min) — Stage-rail board on `lg+`
- [x] **4.4** (45 min) — Modal

## Phase 5 — My Deals board (item 1) · **≈ 1 h 25 sequential**

- [x] **5.1** (20 min) — Header with `hero`
- [x] **5.2** (35 min) — Five stage columns on `lg+` via `StageColumn.vue` (rows below `lg`, touch fallback list kept); same `VueDragga
- [x] **5.3** (15 min) — Modal header
- [x] **exit** (15 min) — Full gate 2 (132 passed; the 19 failures were one modal-click defect + REPS CLS, both fixed)

## Phases 6 + 7 — Liquidity line, REPS, Analyze (items 2, 3) · **≈ 1 h 50 wall-clock** (2 h 30 sequential)

- [x] **6.1 ‖D** (20 min) — Pure `linePath`/`areaPath` + tests.
- [x] **6.2 ‖D** (50 min) — Remove bars; area fill under the line with the 8 inflow/outflow tokens as gradient stops (keeps the 32×once ru
- [x] **6.3 ‖D** (35 min) — Page
- [x] **7.1 ‖D** (25 min) — REPS
- [x] **7.2 ‖D** (15 min) — Analyze
- [x] **exit** (15 min) — Full gate 3 (148 passed; 3 failures fixed in the review round; targeted re-run 21 passed)

## Phase 8 — Closure · **≈ 45 min**

- [x] **8.1** (25 min) — Full gate 4 on the final tree; `e2e:compare` vs `v2-final.json`; screenshots archived; Golden update B (`axe-b
- [ ] **8.2** (20 min) — Docs

## Review

**What changed (high level).**
1. *Aurora Glass* — the dark look's glass token was white; now the look's surface. Scrollbar tracks transparent. No more light slab down the side.
2. *Alignment* — one field anatomy (20 px label row, 42 px control row) across the four input primitives, `UiField`, the deal modals' raw fields and the liquidity forms; the required asterisk finally renders; an e2e check asserts every control row lines up within 1 px.
3. *Navigation* — the back/home buttons on Liquidity, REPS and Analyze are gone, as are the two toolbar cross-links; the shell (sidebar, bottom nav, ⌘K) carries every route.
4. *Cards* — `DealCard` is a verdict card (hero metric + ring against a target, one cash-needed bar with the buffer); `BoughtDealCard` is a progress card (rail, step k of n, ring, every stage's checklist as an accordion with the current stage open, Advance).
5. *Boards* — both pages open with a hero header and live figures; stages are scroll-snapped rail columns on desktop (stacked on phones). Bought Deals adds a flow strip and goes inert on columns more than one stage away while dragging.
6. *Bought flow* — stage moves (drag, card Advance, modal Advance) keep every tick; the modal shows every stage's checklist, current one open; the stage select stays as "Override stage".
7. *Liquidity* — the chart is a line + area with a reserve floor and flow markers (no bars); the page has a hero, counting KPIs (Mercury status in the balance KPI), and an "Upcoming" sidebar.
8. *Motion* — `hero` preset, `v-tilt`, `v-press` in every `UiButton`, `v-hover-lift` in KPI/stat tiles, transition groups on the id-keyed lists, count-up on page figures; four more primitives registered; drag states styled; a perf spec (CLS, long tasks, bundle) and a wider motion guard.
9. *REPS / Analyze* — hero headers, counting figures, tilt on the summary rail, a fixed config notice (no layout shift).

**Kept.** Every flow in the plan's Appendix B; every e2e hook; every network golden (unchanged); dialog copy; the backend (byte-identical).

**Deviations from the plan.** The stage-rail connector is CSS, not a drawn SVG path (a horizontally scrolling rail has no single path to draw). The stage select is a visible override field, not a disclosure (the closed disclosure broke the recorded stage-select flow). `UiSegmented` was already registered in v2; the pipeline-template editor needed no visual pass. `v-flash` is not on the card hero (nothing inside a Sortable child may tween).

**Environment.** WebKit and Mobile Safari could not run here (no WebKit build, download blocked); the browser suite ran on chromium, Mobile Chrome and chromium-motion. The clone was shallow and needed `git fetch --unshallow` for the gates' tags. The backend regression snapshots `openapi`/`models` differ only by a Pydantic 2.13 `pattern` key.

**Final gate numbers (gate 4).** Playwright 151 passed / 0 failed / 61 skipped on the three Chromium projects (4.6 min); compare v2-final → v3-final PASS (0 regressions, 34 checks added); CLS ≤ 0.015 on every route (was 0.60 on My Deals); zero idle long tasks; bundle +6.9 kB gzip (budget +12 kB); pytest 115 passed; network goldens unchanged. Fast gate: see the progress file's last row.
