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
