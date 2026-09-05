# BrrrrDealAnalyzer Frontend

Vue 3 + Vite + TypeScript, styled with Tailwind CSS and unstyled PrimeVue, with a
GSAP motion layer. What you see is the result of the **UI v1 overhaul** (branch
`refactor/ui-overhaul`, tags `ui-baseline`, `ui-p0`…`ui-p4`): every view was
restyled without changing one behaviour. The gates under **Verifying a change**
are how that was proved and how it stays true.

Paths starting `src/`, `e2e/` or `scripts/` are relative to this directory; the
rest are relative to the repository root.

| Where | What it holds |
| --- | --- |
| `docs/ui-overhaul/decisions.md` | every design and execution decision, and the follow-ups v1 deliberately did **not** fix |
| `docs/ui-overhaul/primitives.md` | the contract of each `Ui*` primitive |
| `docs/ui-overhaul/device-checklist.md` | the manual iPhone / desktop pass emulation cannot replace |
| `docs/ui-overhaul/quality-snapshot.md` | axe, screenshots, bundle, Lighthouse and contrast at the end of v1 |
| `docs/ui-overhaul/golden-update-log.md` | every `Golden update:` commit and what it changed |
| `design-system/brrrr-deal-analyzer/MASTER.md` | the generated design system the tokens come from |

## Getting started

```
npm run dev      # Vite dev server
npm test         # Vitest once (npm run test:watch to watch)
npm run build    # vue-tsc type-check + production build
```

The app talks to the backend over `VITE_API_URL`, which defaults to
`http://localhost:8000` when unset (`src/api/index.ts`). The build targets
iOS/Safari >= 15.4 and Chrome >= 100 (`browserslist` in `package.json`,
`build.target` in `vite.config.ts`).

---

## Design system

### Tokens

`src/assets/tokens.css` is the single source of truth for colour, space, radius,
shadow and motion; `src/assets/main.css` imports it first and then sets the base
layer. Colour tokens are space-separated RGB triplets (`--color-fg: 15 23 42`)
rather than colour strings, so `tailwind.config.js` can wrap each one as
`rgb(var(--color-fg) / <alpha-value>)` and Tailwind's alpha modifiers keep
working (`bg-surface/70`). The exception is `--chart-*`: a `<canvas>` needs a
resolved colour string, so those are literals, read through
`src/design/chartTokens.ts`.

The semantic names are `page`, `surface`, `surface-muted`, `line`, `fg`,
`fg-muted`, `primary`, `primary-hover`, `primary-fg`, `positive`, `negative`,
`warning`, `ring` and `chart-1`..`chart-6`, each available as a Tailwind colour.
`--shadow-1/2/3`, `--dur-fast/base/slow` and `--ease-standard/emphasized/exit`
are wired to `shadow-*`, `duration-*` and `ease-*` in the same config, which also
adds `p-safe-b`-style spacing from `env(safe-area-inset-*)`, a `touch:` variant
and the `shimmer` / `float` animations. The radii are reachable as `rounded-ctl`
(6 px, controls), `rounded-card` (10 px) and `rounded-panel` (16 px) rather than
through `rounded-sm/md/lg`: those are Tailwind defaults the templates already use
in about 150 places, and overriding them would restyle every existing corner.
`src/design/cn.ts` extends `tailwind-merge` with all four custom scales, so a
primitive's default class and a caller's override merge instead of stacking.

A `.dark` block redefines every `--color-*` as a desaturated tonal variant. It is
complete, and **no theme toggle ships** — the app is light everywhere, Liquidity
included.

```
npm run audit:contrast
```

Measures WCAG 2.x contrast for every foreground/background pair the UI renders,
in both themes, and exits non-zero below 4.5:1 for text or 3:1 for the focus
ring. When a pair fails, move the token one step within its own colour family —
never lower the threshold. It audits declared *pairs*, so a foreground on a tint
of its own token is out of its reach; `docs/ui-overhaul/quality-snapshot.md` §5
lists the two combinations that are known to fail that way.

### Primitives

The presentational primitives in `src/components/ui/` (`UiButton`, `UiCard`,
`UiField`, `UiModalPanel`, …) are registered **globally** — by `main.ts` for the
app and by `src/test/setup.ts` for the Vitest suite, both from the one map in
`src/components/ui/register.ts` — so a template writes `<UiButton>` with no
import line, and `src/components.d.ts` mirrors the names into Vue's
`GlobalComponents` so `vue-tsc` still checks the props they are passed. That
indirection exists because gate G3 forbids a view's `<script>` from gaining an
import. Full contracts: `docs/ui-overhaul/primitives.md`.

### PrimeVue

PrimeVue runs **unstyled**. Every class it wears comes from the one global
pass-through preset in `src/design/primevue-pt.ts`, installed in `main.ts` with
`ptOptions: { mergeSections: true, mergeProps: true }` so a call site can still
add something genuinely local. No PrimeVue theme preset is used and no new
PrimeVue component was introduced.

---

## Motion

`src/motion/` holds the whole layer: `gsap.ts` (core only, pinned 3.15.0, no
plugins), `tokens.ts` (the CSS duration/ease tokens as GSAP seconds and ease
names — a test fails if the two drift), `reducedMotion.ts`, `presets.ts`,
`directives.ts`, `UiTransition.vue`, `UiTransitionGroup.vue`. `main.ts` calls
`registerMotion(app)` once, which is why a frozen template can write
`<UiTransition preset="modal" appear>` or `v-reveal` with no import and no script
change.

| Surface | Registered | Attached in v1 |
| --- | --- | --- |
| `<UiTransition>` presets | `page`, `modal`, `modalEnterOnly`, `fade`, `slideUp`, `listItem` | `page` (the `App.vue` `RouterView` slot), `modal` ×5, `modalEnterOnly` ×2 |
| Directives | `v-reveal` (`.stagger`), `v-press`, `v-hover-lift`, `v-flash`, `v-count-up` | `v-reveal` only, in 7 files |
| `<UiTransitionGroup>` | yes | nowhere |

Everything in the right-hand gap is built, unit-tested and inert: Plan B skipped
Tasks 4.4–4.6 for UI v2 to redo in its own templates (see the decisions log).

**Reduced motion.** `motionEnabled()` is false under Vitest, when `matchMedia` is
missing, when `prefers-reduced-motion: reduce` matches, and when
`window.__BW_MOTION_OFF__` is set (the e2e suite uses that). Every preset and
directive then sets the final state and calls `done()` synchronously, and a
global `@media (prefers-reduced-motion: reduce)` rule neutralises the remaining
CSS animations.

**The rules a change must not break** — each one protects a behaviour, not a
look:

- **Mount is never delayed.** Modal panels tween the already-mounted panel, so
  the deal form's inputs mount on the same tick as before and the 250 ms autosave
  settle window is untouched. Modal enter stays ≤ 300 ms, inside the 500 ms
  debounced analyze.
- **Every leave sets `pointer-events: none` first**, so a second click on a
  fading overlay cannot reach `@click.self="closeModal"`.
- **Regions whose close path reads or revokes DOM state get enter-only presets**:
  the PDF preview (its close revokes the blob URL), `SendOfferModal` (it resets
  the form right after closing), the REPS property dropdown (150 ms blur
  timeout).
- **The page preset is opacity-only.** A residual `transform`/`filter` on an
  ancestor turns a `position: fixed` descendant into a container-relative box, and
  `MyDeals` opens a fixed modal from `?openDeal` possibly mid-enter. `clearProps`
  is always `transform,opacity,filter,willChange` — never `all`, which would wipe
  the app's own inline styles.
- **SortableJS is never touched**: no transition group inside `<VueDraggable>`,
  no `v-press` on its children, no key that would remount it. Board *rows* are
  revealed, cards never are.
- **The chart container gets opacity only.** `TimelineChart`'s `ResizeObserver`
  redraws on any size change and `getBoundingClientRect` runs per `pointermove`.
- **`v-flash` never touches text** (background tint only) and `v-count-up` ends
  on the exact string Vue rendered, no-opping when either side fails to parse.

---

## Verifying a change

```
npm run verify:ui            # every gate below, one PASS/FAIL line each
npm run verify:ui -- --phase # the same, plus the backend proofs — at a phase end
```

Eleven gates, in order. `--phase` adds a twelfth, `BACKEND`
(`verify_regression.py verify` + `pytest -q`, restoring the `__pycache__` churn
those leave behind), and names the five Playwright projects explicitly, so a
project added to the config without a decision shows up as a difference rather
than silently joining the run.

| Gate | What it proves |
| --- | --- |
| `G1` | nothing outside `frontend/` has moved since `ui-baseline` (`docs/`, `design-system/`, `.superpowers/` and the two root READMEs are documentation and are excluded; `BackEnd/`, `runtime.txt` and `.gitignore` are not) |
| `G2` | `src/{stores,api,utils,router,types,config}` are byte-identical to `ui-baseline`, and `e2e/{flows,fixtures}` to `ui-p0` |
| `G3` | every `.vue` `<script>` block is unchanged but for the whitelisted additive shapes |
| `G4` | every behavioural template binding is unchanged, in document order |
| `G4b` | every on-screen copy string is unchanged |
| `G-HOVER` | every `hover:`/`group-hover:opacity-100` reveal has a `touch:opacity-100` counterpart |
| `G8` | no tracked file contains an absolute filesystem path |
| `G6` | `npm test` and `npm run build` both succeed |
| `G5` / `G7` | the Playwright suite: network contracts, axe baseline, no live tweens |
| `GOLDEN-POLICY` | since `ui-p0`, `scripts/audit/golden`, `e2e/golden`, `scripts/audit/allowlist.json` and `e2e/reports` changed only in `Golden update:` commits |

The static audits also run on their own: `npm run audit` (G3, G4, G4b),
`node scripts/audit/hover-pairs.mjs`, `node scripts/audit/paths.mjs`,
`npm run audit:contrast`. `npm run audit:baseline` regenerates the G3/G4/G4b
manifests — only after a behaviour change has been agreed, and its result is
committed **alone**, with a `Golden update:` subject, and added to
`docs/ui-overhaul/golden-update-log.md`.

Accepted, reasoned deviations live in `scripts/audit/allowlist.json`.
`docs/ui-overhaul/decisions.md` explains what G4 records and what it ignores —
the presentational-prop rule, the `as` rule, and the slot rule — which is the
part of the gate set that most often surprises someone restyling a template.

`G8` is the one gate a documentation change can trip. An absolute path is a fact
about one laptop, so anything that genuinely has to name one builds it from
fragments or writes a `<path-to>/…` placeholder. There is no suppression comment,
so a plain `git grep` keeps answering the same question the gate does.

---

## End-to-end suite

`e2e/` holds the **functional characterization suite**: a Playwright run that
freezes what the app *does* — every user-visible flow, and the exact sequence of
HTTP requests each one makes.

```
npm run e2e                     # run against the committed goldens
npm run e2e:record              # re-record them (chromium only)
npm run e2e:report              # open the last HTML report
npm run e2e:archive -- <name>   # keep the last run as e2e/reports/<name>.json
npm run e2e:compare             # phase0-baseline vs phase5-final, test by test
```

Both servers start themselves: `playwright.config.ts` boots
`e2e/backend/serve_throwaway.py` — the real FastAPI app on a fresh temporary
SQLite database, with every Google / Mercury / SMTP credential scrubbed — on
`:8011`, and serves a production build through `vite preview` on `:5173` (the
backend's CORS allowlist only accepts that port). Nothing under `BackEnd/` is
modified; the launcher only imports it. `workers: 1` and `fullyParallel: false`,
because all five projects share one backend database.

| Project | Browser | Why |
| --- | --- | --- |
| `chromium` | Desktop Chrome | the reference; goldens are recorded here |
| `webkit` | Desktop Safari | the engine every iPhone actually runs |
| `Mobile Safari` | iPhone 14 | coarse pointer — the boards render their non-draggable branch |
| `Mobile Chrome` | Pixel 7 | coarse pointer, different viewport |
| `chromium-motion` | Desktop Chrome | animations **on**, `@motion` specs only |

The first four run with `prefers-reduced-motion: reduce`. That is deliberate: a
characterization suite should assert what the app does, not race what it
animates. The one genuinely motion-sensitive concern — a full-screen overlay must
cover the viewport from the moment it appears, or a tap lands on the board behind
it — is covered by `chromium-motion`.

Committed: `e2e/golden/*.json`, one network contract per flow with volatile
values redacted by key; `e2e/golden/axe-baseline.json`, today's accessibility
violations per route keyed by **rule id** (a run fails when a route reports a new
rule or a known rule's count rises — axe's element selectors are Tailwind class
chains, so they are kept as `examples` and never compared); and
`e2e/reports/phase0-baseline.json` / `phase5-final.json`, the before and after
runs `npm run e2e:compare` matches test by test.

An archive is never copied out of `e2e/reports/last-run.json` by hand: the JSON
reporter records where the run happened, so an archive goes through
`npm run e2e:archive -- <name>`, which rewrites every path under the repository
root to a repo-relative POSIX one (`e2e/scripts/normalize-report.mjs`). G8 fails
the build if a raw report is ever committed, and GOLDEN-POLICY fails it if an
archive changes outside a `Golden update:` commit.

Real devices are not simulated. `docs/ui-overhaul/device-checklist.md` is the
manual pass that covers what emulation cannot: input zoom, safe areas, the iOS
toolbar, and the OS-level Reduce Motion setting. Run it at every phase gate.
