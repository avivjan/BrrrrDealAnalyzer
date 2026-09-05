# Golden update log

Goldens — the G3/G4/G4b baseline manifests, the e2e network contracts and axe
baseline, `scripts/audit/allowlist.json`, and the archived Playwright runs —
change only in a commit whose subject starts `Golden update:`, containing
nothing else, reviewed line by line. The `GOLDEN-POLICY` gate in
`npm run verify:ui` fails the build otherwise — on both halves of that rule
since Step 5.7, so a `Golden update:` commit that also carried a source file
now fails too. That is why each row below is written in the *next* commit: this
log is documentation, not a golden, and may not travel inside the commit it
describes.

This is every such commit on `refactor/ui-overhaul`, oldest first. Regenerate the
list with:

```
git log --reverse --format='%h%x09%s' ui-baseline..HEAD | grep '	Golden update:'
```

(`git log --grep` matches the body too, and two `Step 3.x` commits mention the
phrase there — filter on the subject.)

| # | Commit | What changed, and why it was allowed |
| --- | --- | --- |
| 1 | `4b3885e` | **Phase 0 baseline manifests.** The starting point, not a change: `audit:baseline` over the `ui-baseline` behaviour of all 28 SFCs — frozen script text per SFC, 527 behavioural elements plus watch sources and lifecycle hooks, 696 on-screen copy strings. |
| 2 | `a2aa6e8` | **`attr:to` joins the bindings manifest.** `to` became a behavioural static attribute — a moved `<Teleport to>` is behaviour. Three new entries, for the Teleports in `SettingsPanel`, `SimulationWarning` and `TransactionForm`. The script-block and text manifests are byte-identical. |
| 3 | `89bfe91` | **Phase 0 network-contract and axe goldens.** 23 flows, one ordered request sequence each with ids and timestamps redacted by key; the axe violations on all six routes; and `e2e/reports/phase0-baseline.json`, the run that verified them. Nothing was fixed here — the axe file exists so later phases can be held to "no new ones". |
| 4 | `45e11de` | **Axe baseline re-keyed by rule.** From `<rule> :: <selector>` pairs to one entry per rule per route, carrying impact and element count. Same rules, same routes, same counts — only the key and the comparison changed. Selectors are Tailwind class chains and generated PrimeVue ids, so a restyle would have re-reported every pre-existing violation as new. The 23 network goldens are byte-identical across the re-record. |
| 5 | `ee2b889` | **Allow `UiSectionHeader as="h1"` in `AnalyzeDeal`.** `UiSectionHeader` defaults to `h2`; that title is the only `h1` on `/analyze`, and the route's axe baseline has no `page-has-heading-one` entry, so dropping to `h2` would have introduced a rule the route had never reported. The row named the exact binding, so any other `as` still failed. |
| 6 | `76fc90c` | **Row 5 removed again.** Task 3.0b exempted a *static* `as` naming a presentational tag (`h1` included) from the manifest, so the row was no longer needed. |
| 7 | `6db3146` | **Four `useId` script rows.** One per SFC whose frozen `<script>` gains the two whitelisted shapes — a separate `import { useId } from "vue";` and `const <name>Id = useId();` after the last baseline line. Needed because a `<label for>` needs an id and a PrimeVue wrapper hides the `<input>` that must carry it: `DealInputsForm`, `NumberInput`, `SliderField`, `DaysUntilRefiField`. Landed **before** the code so `npm run audit` passes at every commit — an allowlist row with no diff yet is a WARN, an unlisted script diff is a FAIL. |
| 8 | `1a594da` | **A fifth `useId` row, for `MoneyInput`.** Review round 1 moved it off an implicit label wrap onto an explicit `for`/`id` pair, so the live "= $50,000" hint stopped joining the field's accessible name while the user typed. |
| 9 | `cea8ba8` | **`MyDeals` empty-column state.** One new purely presentational element — a `<UiEmptyState v-if>` beside (never inside) each stage's draggable list, so a column with no deals says so instead of showing a blank 100 px well. Two rows: the `v-if` expression `!columns[stage.id]?.length` (the same read the row's counter already does) and the one line it renders. No script row. |
| 10 | `b74b28d` | **`BoughtDeals` empty-column state** — the same element, the same expression, the same copy word for word. |
| 11 | `bfd43a7` | **E1 chart-token substitution in `TimelineChart`.** The one script change Phase 3 permits: an import of `chartToken`, and inside `draw()` each `'#…'` / `'rgba(…)'` literal becomes `chartToken('<name>')` on the same line. A `<canvas>` takes a resolved colour string and silently ignores a class name, so the chart cannot reach the tokens any other way. G3's E1 rule already encoded the shape; the row is what lets the paired diff count as reviewed. |
| 12 | `eac946e` | **`App.vue` `RouterView` transition slot.** The one allowlist row Phase 4 needs, and the only approved structural delta in the plan: an exact-match whitelist of the two manifest entries the rewrite adds (`RouterView` with `v-slot="{ Component }"`, and `component` with `:is="Component"`), turned on for `src/App.vue` and nothing else. |
| 13 | `0bbbaa4` | **`phase5-final.json` archived.** The Phase 5 characterization run — the same four functional projects Phase 0 ran, 147 passed / 53 skipped / 0 failed / 0 flaky — as the "after" half of the behaviour-freeze proof. `npm run e2e:compare` against Phase 0: 145 passed → passed, 1 skipped → passed, 46 skipped → skipped, 8 additions, 0 failures. |
| 14 | `094bbdf` | **Both archives re-archived through `normalize-report.mjs`.** Neither suite was re-run; 107 paths in `phase0-baseline.json` and 119 in `phase5-final.json` became repo-relative and nothing else changed (226 lines, all of them a path). Required by gate G8. `e2e:compare` prints exactly what it printed before — it keys on `(project, normalised file, title path)`. |
| 15 | `0715506` | **`phase5-final.json` re-archived from the five-project run.** The Phase 5 gate run at `70bce90` had already run the full matrix — Task 5.6 added `chromium-motion` to `PHASE_PLAYWRIGHT_PROJECTS` — but row 13's archive predated that, so `e2e:compare` had one row it could not compare (`[chromium-motion] deep-link-open`, "out of matrix: 1"). Same run, no re-run: 149 expected / 53 skipped / 0 unexpected / 0 flaky. The comparison now reports **zero** out-of-matrix rows: 146 passed → passed, 1 skipped → passed, 46 skipped → skipped, 9 additions, 0 failures. |

## Reading the list

Rows 5–12 are the whole of what a full visual overhaul had to declare against a
frozen baseline: two structural additions (an empty state, on two boards), one
approved script substitution, one router slot rewrite, five id-generator lines,
and one heading level that was later withdrawn. Nothing else in the 28 baseline
SFCs needed a golden to move.

Rows 1–4 and 13–15 are baseline capture and archival rather than permission to
change something.
