# UI v2 progress

Plan: `docs/plans/2026-09-05-ui-v2-plan.md` (inline execution). One line per finished task: task · commit · gate result. Resume from here and `git log` after any context loss.

| Task | Commit | Gates | Notes |
|---|---|---|---|
| 0.0 plan + progress file | (this commit) | — | branch `v2` off `origin/main` f21bfc9, tag `ui-v2-baseline` |
| 0.1 gates: G3/G4/G4b advisory, e2e flows+fixtures → golden policy, `--fast` | (next commit) | `verify:ui --fast` PASS, ADVISORY ×3 no drift; 22 unit tests | G1/G2 still diff against `ui-baseline` on purpose |
