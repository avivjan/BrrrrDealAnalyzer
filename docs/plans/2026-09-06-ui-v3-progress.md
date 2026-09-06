# UI v3 progress

Plan: `docs/plans/2026-09-06-ui-v3-plan.md`. One row per finished task: task · commit · gate result. Resume from here and `git log` after any context loss. Branch `claude/ui-ux-overhaul-plan-xmblf4` (from `main` @ `08fdd2c`, tag `ui-v3-baseline`).

| Task | Commit | Gates | Notes |
|---|---|---|---|
| 1.0 plan + progress file | (this commit) | — | tag `ui-v3-baseline` = 08fdd2c |
| 1.1 Aurora dark glass | 971e2d8 | contrast PASS 340/10 | `looks.data.mjs` dark glass `#111a3a` |
| 1.2 scrollbar track | 572eed9 | — | transparent |
| 1.3 Golden update A | 4a31d8c | — | `liquidity.back` out of the header-width annotation |
| 1.4 back/home buttons + cross-links removed | 20b8503 | hooks 33 tests | liquidity, reps, analyze, both boards |
| main merged (aefec58: CLAUDE.md) | 65af94b | — | tag `ui-v3-baseline` → aefec58; `tasks/todo.md` per CLAUDE.md |
| 1.6 deal-modal fields | 3784ff2 | views 28 | raw fields on the primitives' anatomy (simpler than UiField wrapping) |
| 1.5 one field anatomy (‖A) | f9090ad | ui 367 / full 1288 | worktree agent; asterisk fix (decisions item 19) |
| 1.8 alignment spec (‖A) | 547bc9f | `--list` 16 tests | `e2e/checks/alignment.spec.ts` |
| 1.7 liquidity forms (‖A) | (cherry-pick of 282d46e) | liquidity 102 | UiSegmented was already registered in v2; three segmented groups share one size |
| **Phase 1 exit** | (this commit) | `verify:ui --fast` PASS: G1 G2 G-HOVER G8 G6 (84 files / 1288 tests) GOLDEN-POLICY (20); ADVISORY G3 884 / G4 76 / G4b 47 | clone was shallow → `git fetch --unshallow` so `ui-p0`/`ui-baseline` sit in HEAD's lineage; Aurora dark screenshots in `docs/ui-overhaul/screenshots/v3/phase1-*` |
| 2.1 hero preset (‖B) | 3596f04 | motion 261 | worktree agent |
| 2.2 v-tilt (‖B) | cf30023 | motion+test 249 | worktree agent; no directive typings exist in `components.d.ts` (never did) |
| 2.6 motion guard + perf spec (‖B) | 96a572f | `--list` 55 tests | worktree agent |
| 2.4 four primitives registered | 47a2a01 | ui 717 | UiSegmented was already registered in v2 |
| 2.3 surfaces attached | 273a9f8 | ui/liquidity/views/motion 717 | v-press on every UiButton (a template comment before the root made it a fragment — moved to the script) |
| 2.5 drag polish | ea5900b | — | ghost/chosen/drag classes, CSS only |
| **Full gate 1** | (this commit) | Playwright chromium + Mobile Chrome + chromium-motion: **148 passed, 3 failed, 61 skipped (4.8 min)**; every network golden, axe, no-live-tweens, alignment and modal-scroll check green | The 3 failures are the new perf spec's CLS budget on the *old* boards and REPS: `/my-deals` 0.60, `/bought-deals` 0.07, `/reps` > 0.05 — the pages Phases 4, 5 and 7 rebuild (columns reserve height; cards fill inside). Re-checked at gate 2/3. **webkit and Mobile Safari did not run**: no WebKit build in this sandbox and the download is blocked; `playwright.config.ts` gained an env-gated `PW_CHROMIUM_PATH` so the pinned Chromium can be used. Backend proofs (`verify_regression.py verify` + `pytest`) run at gate 2 with the `--phase` wrapper. |
| 3.1 DealCard verdict card (‖C) | (cherry-pick of 00d34ab) | DealCard+MyDeals.settle+hooks 53 | worktree agent; `UiProgressRing` takes 0–1, not 0–100 |
| 3.2 BoughtDealCard progress card (‖C) | (cherry-pick of d7162f1) | BoughtDealCard+hooks 29 | worktree agent; rail + all-stage accordion + `advance` emit; new hooks `boughtcard.stage.<id>`, `boughtcard.advance` |
| 4.0 stage moves keep ticks | 2e2bfd4 | stagemove contract 6 + hooks | view helper over `updateBoughtDeal`; no golden change (drag records none; stage-select PUT already carried the map) |
| 4.1–4.3 Bought header, flow strip, stage rail | 8d144f8 | views+components 677; vue-tsc clean | `components/board/StageColumn.vue`; connectors are CSS (no SVG draw-on: a horizontally scrolling rail has no single path to draw); pipeline-editor visual pass deferred to 8.x if time |
| 4.4 modal: rail + every stage's checklist | a29e2d3 | stagemove 6 + hooks | stage select behind an "Override stage" disclosure, hook and v-model unchanged |
| 5.1–5.3 My Deals on the rail | 5bae854 | views 39; vue-tsc clean | live figures from the columns; compact rail in the modal header |
| 4.5 card hook on the inert header block | 6550b6f | card 35 + stagemove + hooks | gate 2 found the modal no longer opened from the specs: the taller card's centre is a stage row that stops propagation |
| 6.3 liquidity page hero, counting KPIs, Upcoming sidebar (‖D) | c6302d9 | liquidity 92 | worktree agent; Mercury status lives in the balance KPI footer; sidebar keeps Next Outflow/Inflow, Recurring, Low (90d), Reserve |
| 7.1–7.2 REPS + Analyze (‖D) | ec83303 | reps+analyze+hooks 65 | worktree agent; People panel uses `slideUp` (the `drawer` preset is built for the fixed side drawer) |
| 6.1–6.2 liquidity chart: line + area, reserve floor, flow markers (‖D) | (cherry-pick of 2741590) + reserve prop wired | liquidity+chartTokens 112 | worktree agent; all 32 chart tokens still read once |
| **Full gate 2** (tree at 5bae854, before 4.5) | — | Playwright chromium + Mobile Chrome + chromium-motion: **132 passed, 19 failed, 61 skipped (9.5 min)**; backend proofs: pytest 115 passed, `verify_regression` schema/calculations/endpoints identical (`openapi`/`models` differ only by Pydantic 2.13's Decimal `pattern` key) | 18 of the 19 failures are one defect — the Bought modal did not open from a centre click on the taller card (fixed in 4.5, `6550b6f`); the 19th is `/reps` CLS, rebuilt in 7.1. `/my-deals` and `/bought-deals` CLS now pass on the column boards. Gate 3 re-runs on the final tree. |
| **Full gate 3** (tree at cd522c7) | — | Playwright chromium + Mobile Chrome + chromium-motion: **148 passed, 3 failed, 61 skipped (7.6 min)** | 2 failures = the stage select hidden in a closed disclosure (4.4) broke the recorded stage-select flow; 1 = `/reps` CLS 0.073 (the config banner arriving after the status fetch). Both fixed below. |
| review fixes (read-only diff review, 7 findings) | (see `git log`: "review fixes after gate 3", "count-up test") | motion+components+views+hooks 953; count-up case 67 | stage select visible again; count-up no longer latches mid-tween; no v-flash / v-press inside Sortable children; StageColumn header not sticky; REPS banner fixed-position; modal reopens on the current stage |
