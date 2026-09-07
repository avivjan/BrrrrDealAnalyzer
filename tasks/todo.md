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
- [x] **8.2** (20 min) — Docs

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

**Final gate numbers (gate 4).** Playwright 151 passed / 0 failed / 61 skipped on the three Chromium projects (4.6 min); compare v2-final → v3-final PASS (0 regressions, 34 checks added); CLS ≤ 0.015 on every route (was 0.60 on My Deals); zero idle long tasks; bundle +6.9 kB gzip (budget +12 kB); pytest 115 passed; network goldens unchanged. Fast gate: `verify:ui --fast` PASS (G6 unit + build green, golden policy 21 commits clean).

---

# CI: GitHub Actions for backend + frontend tests

Approved plan: run both suites on every PR into `main` and push to `main`, with no change to app or test logic. The backend suite stays on its throwaway SQLite harness; a separate step boots the app against an ephemeral Postgres to exercise the migrations.

- [x] **C1** (15 min) — Create `.github/workflows/ci.yml`: two parallel jobs, `Backend tests` (Python 3.11, `postgres:16` service with `pg_isready` health check, migration smoke, `pytest -ra`) and `Frontend tests + build` (Node 22, `npm ci`, `npm test`, `npm run build`).
- [x] **C2** (5 min) — Add `':!.github'` to `G1_PATHSPEC` in `frontend/scripts/audit/verify-ui.mjs` and to the matching `toEqual` array in `verify-ui.test.mjs`, so the local `verify:ui` gate keeps passing once `.github/` exists.
- [x] **C3** (20 min) — Local sanity: `cd BackEnd && pytest -ra`; `cd frontend && npm ci && npm test && npm run build`; Postgres smoke via Docker if available.
- [x] **C4** (5 min) — README paragraph under "Tests" describing the workflow and the branch-protection step.
- [x] **C5** (10 min + CI) — Commit, push `ci/github-actions`, open a PR into `main`; confirm both jobs green.
- [x] **C6** (5 min) — Review section below.
- [ ] **C7** (manual, repo owner, after first merge) — Settings → Branches → `main` → require status checks `Backend tests` and `Frontend tests + build`.

## CI review

**What changed.** One new file, `.github/workflows/ci.yml`, plus three small edits: the `.github` exclusion in `G1_PATHSPEC` (`frontend/scripts/audit/verify-ui.mjs`) and its exact-match assertion (`verify-ui.test.mjs`), a CI paragraph in the root README, and this checklist. No application or test logic changed; every existing test runs exactly as before.

**Test database.** There was nothing to tear down. `BackEnd/tests/conftest.py` already builds a throwaway SQLite file per run and aborts on any Postgres URL, so pytest in CI runs with no `DATABASE_URL` at all. The only Postgres in the workflow is a `postgres:16` service container used by one step that imports the app twice, proving `create_all` + `migrations/` + seeding work and are idempotent on real Postgres. Its credentials are literals pointing at `localhost` on the runner.

**Local results before pushing.**
- `cd BackEnd && pytest -ra`: 115 passed. Tracked `.pyc` files untouched (`PYTHONDONTWRITEBYTECODE=1`).
- Postgres smoke against a scratch Postgres 16 cluster: both boots exit 0; 11 tables created; 2 pipeline templates seeded.
- `cd frontend && npm ci && npm test`: 85 files, 1368 tests passed (includes the updated pathspec assertion).
- `npm run build`: `vue-tsc -b` clean, Vite build succeeded.
- `npm run verify:ui -- --fast`: G6 PASS, G1 FAIL. G1 is failing on `main` already: 88 files under `BackEnd/` changed since the `ui-baseline` tag (the PR #26 layering refactor), which the gate freezes. Not caused by this change and not fixed here; the `ui-baseline` tag needs moving or the gate needs a backend-aware baseline. Flagged for the repo owner.

**Not covered, on purpose.** Playwright e2e, `verify:ui` and `verify_regression.py verify` stay local (browsers, git tags and a golden-drift artifact respectively). The smoke exercises the fresh-database path, not the legacy upgrade branches in the migrations; that needs a legacy-schema fixture as a follow-up.

**Still manual.** C7: make `Backend tests` and `Frontend tests + build` required checks on `main` after the workflow has run once.

---

# Postgres everywhere: golden harness + Playwright backend

The pytest suite already runs on the throwaway Postgres (`BackEnd/docker-compose.test.yml`). Two harnesses still built their own temp SQLite file: `BackEnd/verify_regression.py` (golden snapshots) and, through it, `frontend/e2e/backend/serve_throwaway.py` (the FastAPI server Playwright talks to). Move both to the same Postgres, with the same guard.

- [x] **P1** (10 min) — Extract the guard from `tests/conftest.py` into `BackEnd/tests/db_isolation_guard.py` (URL resolution, loopback + `_test` + marker checks, `current_database()` check, schema reset); `conftest.py` imports it.
- [x] **P2** (10 min) — `verify_regression.py`: replace the temp-SQLite block and the UUID shim with the shared guard; docstring.
- [x] **P3** (5 min) — `serve_throwaway.py`: docstring says Postgres; nothing else changes (it imports `verify_regression` for the side effects).
- [x] **P4** (10 min) — Nightly `playwright` job gets the same `postgres:16` service and passes `TEST_DATABASE_URL` to `npm run e2e` (the webServer inherits it).
- [x] **P5** (5 min) — Docs: root README, BackEnd README (regression harness), frontend README (e2e needs the container).
- [x] **P6** (15 min) — Validate on a local Postgres 16: pytest; `verify_regression.py verify` (re-snapshot if the only drift is the known Pydantic one / DB representation, and say so); Playwright chromium on two specs through `serve_throwaway.py`.
- [ ] **P7** (5 min) — Commit to `ci/nightly-e2e`, push, update PR #32; review below.

## Postgres-everywhere review

**What changed.** One new module, `BackEnd/tests/db_isolation_guard.py`, now holds the isolation rules (URL from `TEST_DATABASE_URL` only, loopback host, `_test` database name, no hosted-provider marker, `current_database()` check, schema reset). `tests/conftest.py` and `verify_regression.py` both use it; the Playwright backend server (`frontend/e2e/backend/serve_throwaway.py`) inherits it by importing `verify_regression`. The temp-SQLite setup and the SQLite UUID bind shim are gone from both harnesses. The nightly Playwright job gets the same `postgres:16` service and passes `TEST_DATABASE_URL` to `npm run e2e`.

**Goldens re-recorded on Postgres** (`verify_regression.py snapshot`). The diff is exactly two things: (1) `endpoints.json`, one entry, the `detail` string of `POST /reps/people` on a duplicate name, which echoes the raw driver error and now reads psycopg2's `UniqueViolation` instead of SQLite's `IntegrityError`; (2) `openapi.json` and `models.json`, the Pydantic 2.13 `pattern` keys on Decimal fields that PR #26 already documented as drift. `schema.json` and `calculations.json` are byte-identical. `verify` is clean after the re-record.

**Validated on a local PostgreSQL 16.** pytest: 118 passed. `verify_regression.py verify`: all five snapshots identical. Playwright, two flows on chromium through `serve_throwaway.py`: 4 passed, backend log shows `DATABASE_URL=postgresql+psycopg2://brrrr_test:...@127.0.0.1:55432/brrrr_test`.

**Worth knowing.** The duplicate-name endpoint leaks the database driver's error text to the client; unchanged here, but it is now visible in the golden.

---

# Nightly report email v2

Plan approved in plan mode. Additive only: every existing metric stays.

- [x] **N1** (5 min) — Branch `feature/nightly-report-enhancements` from `main`; this checklist.
- [x] **N2** (45 min) — Split `nightly_e2e_email.py` into `.github/scripts/nightly/` (shim keeps the CLI); text output identical for the same input.
- [x] **N3** (30 min) — `playwright_report.py`: annotations, skip reasons, repo-relative keys (port of `compare-reports.mjs`), spec-file totals.
- [x] **N4** (45 min) — `known_skips.json` allow-list + `skips.py` (grouping, expected vs observed, rules S1–S6).
- [x] **N5** (30 min) — `junit.py`: pytest + vitest JUnit XML → counts, durations, slowest, failed.
- [x] **N6** (25 min) — `coverage.py`: pytest-cov JSON + vitest json-summary → lowest-covered modules; not-wired steps.
- [x] **N7** (40 min) — `history.py`: record v1, tail read, append, same-matrix, previous / week-ago.
- [x] **N8** (45 min) — `anomalies.py`: deltas, first-seen vs recurring, flaky, slow regressions, wall-clock, spec-file trend, coverage drop.
- [x] **N9** (60 min) — `charts.py`: three matplotlib PNGs (CID) + table fallback.
- [x] **N10** (90 min) — `theme.py`, `render_html.py`, `render_text.py`: luxury tokens, new sections, size budget.
- [x] **N11** (40 min) — `ci.yml` (junit + coverage + uploads + unit-test step), `e2e-nightly.yml` (downloads, history branch, push), coverage deps.
- [x] **N12** (60 min) — Fixtures + stdlib unit tests.
- [x] **N13** (45 min) — Local validation: unit tests, pytest/vitest with the new flags, previews + screenshots.
- [x] **N14** (30 min) — README, review below, commit, push, PR with screenshots and follow-ups.

## Nightly v2 review

**What changed.** The nightly email script became a package, `.github/scripts/nightly/`
(the old `nightly_e2e_email.py` is a six-line shim, so the workflow command and the
`report.json out.html` preview form still work). Every line and metric of the previous
email is still produced, in the same order; a unit test renders the plain-text body and
checks the legacy lines. On top of that:

- **Skipped by reason.** Playwright's `skip` annotations are grouped by reason and matched
  against `.github/nightly/known_skips.json` (12 reasons, 6 categories, expected counts per
  project summing to the 181 we see today). Unknown reasons, skips with no annotation
  (fixture failure signature), "should never fire" reasons and counts above the expected
  are flagged as anomalies at the top of the mail; routine skips are listed in ink with a
  one-line explanation and expected vs observed.
- **Suites.** pytest and vitest now write JUnit XML (and coverage) into `$RUNNER_TEMP`; the
  nightly uploads them as artifacts and the email shows counts, wall time, failing and five
  slowest cases per suite. PR/push CI behaviour is unchanged apart from those extra flags.
- **History and trends.** One JSON record per run (`history.jsonl`) on the orphan branch
  `nightly-history`, appended and pushed by the notify job (`contents: write` on that job
  only, `HEAD:nightly-history`, three retries). Three matplotlib PNGs (pass/fail, skips by
  category, tonight's five slowest tests) are embedded as CID images; a compact table takes
  over when matplotlib or history is missing.
- **Low-effort analytics implemented.** Tile deltas vs last run and vs 7 days ago;
  first-seen vs recurring failures; flaky list; slower-than-usual tests (>1.5× the 7-run
  median); wall-clock drift; spec-file trend arrows; coverage-drop check; lowest-covered
  modules per side.
- **Restyle.** `theme.py` carries the site's "quiet luxury" light tokens; status is a 10 %
  wash pill, KPI numbers stay in ink, strong colour only in Anomalies. HTML body is ~66 KB
  (pass) / ~79 KB (fail), under the 95 KB budget enforced by a test.

**Verified.** 19 stdlib unit tests pass; pytest (118) with `--junitxml --cov` against a
scratch Postgres and vitest (1368) with junit + coverage reporters both produced parsable
files; PASS and FAIL previews rendered with 22 synthetic history records and screenshotted
(`docs/nightly/preview-*.png`); FAIL fixture triggers every anomaly rule.

**Not done (listed as follow-ups in the PR).** Quarantine list / summary issue for tests
flaky in ≥3 of 14 runs; history rotation past ~365 records; bootstrapping history from the
four archived reports; trends for the custom perf annotations already in the Playwright
report; a repository ruleset keeping the Actions token off `main`.

# Nightly headline counts every suite

Problem: the mail's subject, headline and the four tiles count Playwright only
(239 + 181 = 420 "test calls"), while pytest (118) and vitest (1368) appear only
in the suites section further down. Fix: the headline numbers add all three suites;
the Playwright-only lines stay where they are, labelled as Playwright's.

- [x] **H1** (15 min) — `anomalies.suite_totals(record)`: passed / failed / skipped / total across Playwright + backend + frontend from a history record, with per-suite parts; `tile_deltas` compares those, so deltas keep working across runs.
- [x] **H2** (10 min) — `main.py`: headline (and so the subject) from the combined totals; `ctx["totals"]`.
- [x] **H3** (15 min) — `render_html.py` / `render_text.py`: tiles show the combined numbers with a "Playwright · Backend · Frontend" line under them; the Playwright session section is titled as Playwright's, its "Total test calls (run)" line unchanged.
- [x] **H4** (10 min) — Unit test for `suite_totals` (missing suite, totals add up); previews re-rendered.
- [x] **H5** (10 min) — Commit, push, PR for review.

## Nightly headline review

`anomalies.suite_totals(record)` adds Playwright (stats; a flaky test counts as passed), pytest and
vitest (JUnit) into passed / failed / skipped / total with per-suite parts, and `tile_deltas` now
compares those combined numbers, so deltas keep working across runs (old records have the same
fields). The subject, headline and four tiles use the combined totals; a "Tests by suite" line under
the tiles shows the split; the Playwright-only section is titled "Playwright session report" and its
"Total test calls (run)" line is unchanged. 20 unit tests pass; previews and `docs/nightly` screenshots
re-rendered (fixtures: 440 passed / 181 skipped / 621 total on the PASS mail).

- [x] **H6** (20 min) — First line in words: `anomalies.plain_verdict` gives "All good tonight." / "All tests passed, a few things are worth a look." / "Something failed tonight." with a one-sentence detail; it heads the HTML, the text body and the subject. Numbers moved to the line under it.

---


---

# Audit fixes F1–F10 (2026-09-07) — branch `claude/audit-fixes-f1-f10` from `main@17fcd33`

Scope is strictly the ten audit findings; BRRRR ROI definition (N1) untouched. Estimates are agent wall-clock minutes.

- [x] **X.1** (15 min) — F2: `get_total_cash_needed_for_deal` takes a `refi_shortfall` (= `max(0, −cash_out_routi)`), added to both totals; BRRRR step adds the breakdown line when a shortfall exists. Flip passes 0.
- [x] **X.2** (5 min) — F3: Flip ROI / annualized ROI on zero cash invested → `-1` (profit), `-2` (loss), `0` (break-even).
- [x] **X.3** (5 min) — F4: 0 % long-term rate → `loan / n` instead of HTTP 400.
- [x] **X.4** (10 min) — F6: Flip validator (backend + `validateDealInputs`) mirrors the BRRRR non-negative and 0–100 checks.
- [x] **X.5** (10 min) — F1: "Rehab float buffer (10% of rehab)" breakdown line in both models; fix the "rehab × 1.5" comment.
- [x] **X.6** (10 min) — F9: PDF breakdown table formats ROI / Annualized ROI / Cash on Cash as %, DSCR as ratio, everything else as money.
- [x] **X.7** (20 min) — F5: sentinel decoding restricted to percent formatters in `DealCard.vue`, `dealUtils.ts`, `MyDeals.vue`, `BoughtDeals.vue`; hero ring treats −1 as ∞ (full, positive); 0 renders "0.0%"; currency −$1/−$2 never decoded.
- [x] **X.8** (5 min) — F8: portfolio equity adds `cashReserve × 1000` per deal.
- [x] **X.9** (5 min) — F10: reserve wording → "escrowed at refi, returned at exit" in form label, Pydantic description, TS doc, step comment.
- [x] **X.10** (20 min) — Tests: refi shortfall raises Total Cash Needed; 0 % amortization; zero-invested flip ±∞; Flip validator rejects bad input. Run `pytest BackEnd/tests`, `vitest`, `vue-tsc -b`.

## Review — audit fixes F1–F10

**What changed (backend).** `get_total_cash_needed_for_deal` takes a `refi_shortfall` that is added to both totals; the BRRRR step computes it as `max(0, −cash_out_routi)` and registers a "Refi Shortfall (cash to refi table)" breakdown line only when it is positive (F2). Flip ROI / annualized ROI on zero cash invested return the engine's `-1` / `-2` sentinels by profit sign, `0` at break-even (F3). `calc_mortgage_payment` returns `loan / n` at 0 % (F4). The Flip validator now rejects negative buy closing, taxes, insurance, HOA, utilities and out-of-range HML rate / capital-gains rate (F6). Both buffered breakdowns list the "Rehab float buffer (10% of rehab)" line and the misleading "rehab × 1.5" / "doubling" comments are corrected (F1). The PDF breakdown table formats ROI / Annualized ROI / Cash on Cash as percentages and DSCR as a ratio (`1.36x`) by step label (F9). Cash-reserve wording now says escrowed at refi and returned at exit, not a principal paydown (F10).

**What changed (frontend).** `DealCard.vue` decodes −1 / −2 to "∞%" / "-∞%" in `formatPercent`, renders a genuine 0 as "0.0%", and maps the sentinels to ±Infinity in `heroPercent` so ∞ fills the ring with the positive tone (F5). `MyDeals.vue` / `BoughtDeals.vue` no longer decode sentinels inside `formatCurrency`; a new `getPercentColor` carries the sentinel tone for the CoC / ROI / Annualized ROI tiles only (F5). `dealUtils.ts` clipboard `formatPercent` decodes sentinels; `validateDealInputs` mirrors the new bounds (F5, F6). Portfolio equity adds `cashReserve × 1000` per deal (F8). Form label is "Cash Reserve (escrowed at refi)" (F10).

**Tests.** `BackEnd/tests/test_analyze.py::TestAuditFixes` (16 cases): refi shortfall raises both totals and equals `−cash_out`; buffered breakdown components sum to the total for both models; 0 % amortization at unit and endpoint level; zero-invested flip → −1 / −2; nine Flip validator rejections. `frontend/src/utils/dealUtils.test.ts`: sentinel decode on percent only, "0.00%" rendering, Flip validation. `DealInputsForm.test.ts` updated for the new label. `tests/_regression_snapshots/openapi.json` refreshed: the only change is the `cashReserve` description.

**Verification.** `pytest` (local Postgres 16): 264 passed. `vitest run`: 85 files / 1372 tests passed. `npm run build` (`vue-tsc -b && vite build`): clean.

**Not done / notes.** `verify_regression.py` calculation snapshots (`tests/_regression_snapshots/calculations.json`) are not run in CI and were left untouched; the `zero_interest_refi` and zero-invested flip cases there now differ by design. The refi shortfall is added unbuffered to the buffered total (open question N2). Nightly e2e goldens do not reference the old label or the "∞" text. N1 (BRRRR ROI definition) untouched as instructed.
