# UI v2 progress

Plan: `docs/plans/2026-09-05-ui-v2-plan.md` (inline execution). One line per finished task: task · commit · gate result. Resume from here and `git log` after any context loss.

| Task | Commit | Gates | Notes |
|---|---|---|---|
| 0.0 plan + progress file | (this commit) | — | branch `v2` off `origin/main` f21bfc9, tag `ui-v2-baseline` |
| 0.1 gates: G3/G4/G4b advisory, e2e flows+fixtures → golden policy, `--fast` | (next commit) | `verify:ui --fast` PASS, ADVISORY ×3 no drift; 22 unit tests | G1/G2 still diff against `ui-baseline` on purpose |
| 0.2 hook inventory test | (next commit) | 5 tests green; 618 static + dynamic hooks vs 100+ references | generic: every hook-shaped literal in e2e counts as a reference |
| 0.3 axe gap-fill: modals, seeded boards, 390px | (next 2 commits) | 11 scans recorded on chromium, replay green | criticals now visible: `label`×2 (bought-deals@seeded/@modal), `button-name`×1 (my-deals@390) — must be 0 after Phase 3 |
| **Phase 0 exit** | 3fce989 | `verify:ui --phase` PASS: G1 G2 G-HOVER G8 G6 (57 files / 1097 tests) G5/G7 (188 passed, 90 skipped, 5 projects, 6.5 min) GOLDEN-POLICY (16 golden commits) BACKEND; ADVISORY G3/G4/G4b no drift | user review #1 |
| 1.1 token vocabulary v2 + Tailwind keys + cn groups + contrast matrix (27 pairs, look sheets) | (next commit) | contrast PASS 54 pairs / 2 sets; 59 unit tests; vite build | base negative→red-700, warning→amber-800 (fixes v1 4.14:1 defect) |
| 1.1b four look sheets (generated) + looks.ts + fonts installed | (next commit) | contrast PASS 270 pairs / 10 sets; looks.test 9; chartTokens fallbacks = luxury dark | generator `scripts/design/build-looks.mjs` from `looks.data.mjs`; `npm run check:looks` guards staleness |
| 1.2 fonts + base CSS (color-scheme handoff, .numeric, .glass, cross-fade, in-app reduced motion) | (next commit) | fast gate PASS; 1128 unit tests | fonts lazy per look via `looks.ts` |
| 1.3 theme engine: look + mode + motion, pre-paint script, look-aware GSAP tokens | (next commit) | theme.test 15, tokens.test 10; fast gate PASS | keys `bw.look`/`bw.theme`/`bw.motion`; default luxury dark |
| 1.4 twelve new primitives (Surface, GlassPanel, Chip, Tooltip, KpiCard, Sparkline, ProgressRing, TimelineRail, DataTable, Drawer, CommandItem, Segmented) | (next commit) | ui suite 30 files / 301 tests; vue-tsc clean; registry = 25 | documented in docs/ui-overhaul/primitives.md |
