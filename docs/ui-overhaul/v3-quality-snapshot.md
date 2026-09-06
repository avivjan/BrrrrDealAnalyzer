# UI v3 — quality snapshot (2026-09-06)

The state of the frontend at the end of UI v3 (branch
`claude/ui-ux-overhaul-plan-xmblf4`, from `main` @ `aefec58`, tag
`ui-v3-baseline`), measured the way v2's snapshot measured its exit tree. Numbers
come from the gate runs recorded in `docs/plans/2026-09-06-ui-v3-progress.md`.

## 1. Gates

| Gate | Result |
| --- | --- |
| G1 backend + root files vs `ui-baseline` | PASS (`.claude/` and `tasks/` excluded as notes) |
| G2 `src/{stores,api,utils,router,types,config}` vs `ui-baseline` | PASS (byte-identical) |
| G3 / G4 / G4b | ADVISORY — see the final fast-gate line in the progress file |
| G-HOVER | PASS |
| G8 absolute paths | PASS |
| G6 unit + build | PASS — see the final fast-gate line in the progress file |
| G5 / G7 Playwright | Run on the **three Chromium projects** (`chromium`, `Mobile Chrome`, `chromium-motion`); WebKit and Mobile Safari **did not run** — no WebKit build in the sandbox and the download is blocked. Final numbers in §2. |
| GOLDEN-POLICY | PASS — every golden change is a `Golden update:` commit; network goldens unchanged |
| BACKEND | pytest PASS (115 tests). `verify_regression.py verify`: `schema`, `calculations`, `endpoints` identical; `openapi` and `models` differ only by a `pattern` key Pydantic 2.13 emits for Decimal fields — an installed-package artefact, `BackEnd/` is byte-identical |

## 2. Behaviour proof

- Network contracts (`e2e/golden/*.json`): **unchanged**. The one agreed behaviour change (stage moves keep ticks) sends the same PUT autosave already sent, with the map untouched; no recorded body differs.
- Dialog copy (`alert`/`confirm`): unchanged.
- Hooks: every `data-testid` the suite references exists (`src/test/hooks-inventory.test.ts`); `boughtdeals.card.<id>` moved onto the card's inert header block.
- Two `Golden update:` commits: A dropped `liquidity.back` from a width annotation; B archived the final run.
- Final Playwright run (gate 4, tree at 7449551): **151 passed, 0 failed, 61 skipped** across chromium, Mobile Chrome and chromium-motion in 4.6 min. `compare-reports v2-final → v3-final`: 131 passed → passed, 47 skipped → skipped, 34 added (alignment, perf, wider motion guard), 176 out of matrix (the two WebKit projects that did not run), 0 regressions — PASS.

## 3. Accessibility

- Axe baseline: unchanged — every axe scan (routes, modals, seeded boards, 390 px, look × mode sets) passed against the v2 baseline, so no rule count rose; none fell far enough to warrant re-recording.
- The alignment check (`e2e/checks/alignment.spec.ts`) is green on Analyze, both deal modals and the liquidity forms: every control row shares its top and height within 1 px.

## 4. Performance

Budget (plan §Guardrails): main chunk ≤ +12 kB gzip over `ui-v3-baseline`; CLS ≤ 0.05 per route; zero long tasks > 50 ms idle on the boards with 20 cards and during a chart pan; `backdrop-filter` only on the four shell surfaces.

| Measure | Baseline (gate 1, old boards) | Final |
| --- | --- | --- |
| CLS `/` `/analyze` `/liquidity` | ≤ 0.05 | 0.0010 · 0.0019 · 0.0012 |
| CLS `/my-deals` | 0.60 (rows filling) | 0.0019 |
| CLS `/bought-deals` | 0.07 | 0.0058 |
| CLS `/reps` | 0.073 (config banner arriving in flow) | 0.0145 |
| Long tasks, boards idle / chart pan | 0 | 0 (load-phase bundle evaluation of ~140 ms is annotated, not counted) |
| Bundle gzip (all `dist/assets/*.js`) | 227,746 B at `ui-v3-baseline` | 234,621 B (+6,875 B ≈ +6.9 kB, budget +12 kB) |

## 5. What is not measured here

- WebKit / iPhone Safari: not run in this environment; the real-device pass in `device-checklist.md` still applies.
- Lighthouse: no launcher in the sandbox; CLS is measured with a `PerformanceObserver` in the perf spec instead.
- The pipeline-template editor received no visual pass in v3 (it already sits on tabs and surface tiers).
