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
| G6 unit + build | PASS — _(final count in the progress file)_ |
| G5 / G7 Playwright | Run on the **three Chromium projects** (`chromium`, `Mobile Chrome`, `chromium-motion`); WebKit and Mobile Safari **did not run** — no WebKit build in the sandbox and the download is blocked. Final numbers in §2. |
| GOLDEN-POLICY | PASS — every golden change is a `Golden update:` commit; network goldens unchanged |
| BACKEND | pytest PASS (115 tests). `verify_regression.py verify`: `schema`, `calculations`, `endpoints` identical; `openapi` and `models` differ only by a `pattern` key Pydantic 2.13 emits for Decimal fields — an installed-package artefact, `BackEnd/` is byte-identical |

## 2. Behaviour proof

- Network contracts (`e2e/golden/*.json`): **unchanged**. The one agreed behaviour change (stage moves keep ticks) sends the same PUT autosave already sent, with the map untouched; no recorded body differs.
- Dialog copy (`alert`/`confirm`): unchanged.
- Hooks: every `data-testid` the suite references exists (`src/test/hooks-inventory.test.ts`); `boughtdeals.card.<id>` moved onto the card's inert header block.
- Two `Golden update:` commits: A dropped `liquidity.back` from a width annotation; B archived the final run.
- Final Playwright run: _(filled at gate 4)_.

## 3. Accessibility

- Axe baseline: _(filled at gate 4 — rule counts per route may only fall)_.
- The alignment check (`e2e/checks/alignment.spec.ts`) is green on Analyze, both deal modals and the liquidity forms: every control row shares its top and height within 1 px.

## 4. Performance

Budget (plan §Guardrails): main chunk ≤ +12 kB gzip over `ui-v3-baseline`; CLS ≤ 0.05 per route; zero long tasks > 50 ms idle on the boards with 20 cards and during a chart pan; `backdrop-filter` only on the four shell surfaces.

| Measure | Baseline (gate 1, old boards) | Final |
| --- | --- | --- |
| CLS `/` `/analyze` `/liquidity` | ≤ 0.05 | _(gate 4)_ |
| CLS `/my-deals` | 0.60 (rows filling) | _(gate 4)_ |
| CLS `/bought-deals` | 0.07 | _(gate 4)_ |
| CLS `/reps` | > 0.05 | _(gate 4)_ |
| Long tasks, boards idle / chart pan | 0 | _(gate 4)_ |
| Bundle gzip (all `dist/assets/*.js`) | _(gate 4)_ | _(gate 4)_ |

## 5. What is not measured here

- WebKit / iPhone Safari: not run in this environment; the real-device pass in `device-checklist.md` still applies.
- Lighthouse: no launcher in the sandbox; CLS is measured with a `PerformanceObserver` in the perf spec instead.
- The pipeline-template editor received no visual pass in v3 (it already sits on tabs and surface tiers).
