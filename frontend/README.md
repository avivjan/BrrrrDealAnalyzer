# BrrrrDealAnalyzer Frontend

Vue 3 + Vite + TypeScript frontend, styled with Tailwind CSS and unstyled PrimeVue components.

## Getting started

```
npm run dev
```

Starts the Vite dev server.

## Testing

```
npm test
```

Runs the Vitest suite once (see also `npm run test:watch` for watch mode).

## Building

```
npm run build
```

Type-checks with `vue-tsc` and produces a production build via Vite.

## Backend API URL

The frontend talks to the backend over `VITE_API_URL`, which defaults to `http://localhost:8000` when unset. See `src/api/index.ts` for how the API client is configured.

## Supported platforms

The build targets iOS/Safari >= 15.4 and Chrome >= 100 (see the `browserslist` field in `package.json` and `build.target` in `vite.config.ts`).

## Design tokens

`src/assets/tokens.css` is the single source of truth for colour, space, radius,
shadow and motion; `src/assets/main.css` imports it first and then sets the base
layer. Colour tokens are space-separated RGB triplets (`--color-fg: 15 23 42`)
rather than colour strings, so `tailwind.config.js` can wrap each one as
`rgb(var(--color-fg) / <alpha-value>)` and Tailwind's alpha modifiers keep
working (`bg-surface/70`). The exception is `--chart-*`: a `<canvas>` needs a
resolved colour string, so those are literals.

The semantic names are `page`, `surface`, `surface-muted`, `line`, `fg`,
`fg-muted`, `primary`, `primary-hover`, `primary-fg`, `positive`, `negative`,
`warning`, `ring` and `chart-1`..`chart-6`, each available as a Tailwind colour.
`--shadow-1/2/3`, `--dur-fast/base/slow` and `--ease-standard/emphasized/exit`
are wired to `shadow-*`, `duration-*` and `ease-*` in the same config, which also
adds `p-safe-b`-style spacing from `env(safe-area-inset-*)`, a `touch:` variant
and the `shimmer` / `float` animations. The radii are reachable as
`rounded-ctl` (6 px, controls), `rounded-card` (10 px) and `rounded-panel`
(16 px) rather than through `rounded-sm/md/lg`: those are Tailwind defaults the
templates already use in about 150 places, and overriding them would restyle
every existing corner. The values come from
`design-system/brrrr-deal-analyzer/MASTER.md` ("Approved overrides").

`future.hoverOnlyWhenSupported` is deliberately **not** enabled yet. It wraps
every `hover:` utility in `@media (hover: hover)`, which would hide the 14
controls this app reveals only on hover from every touch device (`DealCard` x4,
`BoughtDealCard` x2, `MyDeals` x3, `BoughtDeals` x3, `DayDetail` x1,
`LiquiditySidebar` x1). It is enabled at the end of Phase 3, once every
`group-hover:opacity-100` reveal has a `touch:opacity-100` counterpart.

A `.dark` block redefines every `--color-*` as a desaturated tonal variant. It
is complete, but no theme toggle ships.

`src/motion/tokens.ts` mirrors the duration and ease tokens for GSAP (seconds
and ease names instead of milliseconds and cubic-béziers); its test fails if the
two ever drift.

The presentational primitives in `src/components/ui/` (`UiButton`, `UiCard`,
`UiField`, …) are registered globally — by `main.ts` for the app and by
`src/test/setup.ts` for the Vitest suite, both from the one map in
`src/components/ui/register.ts` — so a template writes `<UiButton>` with no
import line, and `src/components.d.ts` mirrors the names into Vue's
`GlobalComponents` so `vue-tsc` still checks the props they are passed.

```
npm run audit:contrast
```

Measures WCAG 2.x contrast for every foreground/background pair the UI renders,
in both themes, and exits non-zero below 4.5:1 for text or 3:1 for the focus
ring. When a pair fails, move the token one step within its own colour family —
never lower the threshold.

## End-to-end suite

`e2e/` holds the Phase 0 **functional characterization suite**: a Playwright
run that freezes what the app *does* — every user-visible flow, and the exact
sequence of HTTP requests each one makes — so a visual overhaul can be proven
not to have changed any of it.

```
npm run e2e            # run the suite against the committed goldens
npm run e2e:record     # re-record the goldens (chromium only)
npm run e2e:report     # open the last HTML report
```

Both servers start themselves. `playwright.config.ts` boots
`e2e/backend/serve_throwaway.py` — the real FastAPI app on a fresh temporary
SQLite database, with every Google / Mercury / SMTP credential scrubbed — on
`:8011`, and serves a production build through `vite preview` on `:5173`
(the backend's CORS allowlist only accepts that port). Nothing under `BackEnd/`
is modified; the launcher only imports it.

### The projects

| Project | Browser | Why |
| --- | --- | --- |
| `chromium` | Desktop Chrome | the reference; goldens are recorded here |
| `webkit` | Desktop Safari | the engine every iPhone actually runs |
| `Mobile Safari` | iPhone 14 | coarse pointer — the boards render their non-draggable branch |
| `Mobile Chrome` | Pixel 7 | coarse pointer, different viewport |
| `chromium-motion` | Desktop Chrome | animations **on**, `@motion` specs only |

The first four run with `prefers-reduced-motion: reduce`. That is deliberate: a
characterization suite should assert what the app does, not race what it
animates, and an assertion that only passes because a transition happened to
finish in time is not an assertion. The one genuinely motion-sensitive
concern — a full-screen overlay must cover the viewport from the moment it
appears, or a tap lands on the board behind it — is covered by
`chromium-motion`, which runs the `@motion`-tagged specs with animation
enabled.

`workers: 1` and `fullyParallel: false`, because all five projects share one
backend database.

### What is committed

- `e2e/golden/*.json` — one network contract per flow: the ordered list of
  requests, with volatile values (ids, timestamps) redacted by key.
- `e2e/golden/axe-baseline.json` — today's accessibility violations per route,
  keyed by **rule id**, each with its impact and the number of elements
  currently failing it. A run fails when a route reports a rule it has never
  reported, or when a known rule's count goes up. It deliberately does *not*
  compare axe's element selectors: those are Tailwind class chains and
  generated PrimeVue ids, so a restyle would re-report every pre-existing
  violation as new. Sample selectors are kept under `examples` for a human to
  start from, and are never compared. Nothing here is fixed in Phase 0; the
  file exists so a later phase can be held to "no new ones".
- `e2e/reports/phase0-baseline.json` — the JSON reporter output from the run
  that recorded the above.

Goldens change only with an agreed behaviour change, in their own commit with a
`Golden update:` subject — the same rule as the audit manifests below.

Real devices are not simulated. `docs/ui-overhaul/device-checklist.md` is the
manual pass that covers what emulation cannot: input zoom, safe areas, the iOS
toolbar, and the OS-level Reduce Motion setting.

## How to verify a change

Before committing, run:

```
npm test
npm run build
```

Both must complete successfully.

For UI work there is one more command, which runs the whole behaviour-freeze gate
set (the two above plus the audits below) and exits non-zero if any gate fails:

```
npm run verify:ui
```

The audits on their own:

- `npm run audit` — checks the working tree against the committed baseline manifests in
  `scripts/audit/golden/`: script blocks frozen (G3), template bindings frozen (G4), on-screen
  copy frozen (G4b). Accepted, reasoned deviations are declared in `scripts/audit/allowlist.json`.
- `npm run audit:contrast` — re-measures the token contrast pairs described under **Design
  tokens** above.
- `npm run audit:baseline` — regenerates those manifests. Only run it when a change to behaviour
  has been agreed, and commit the result on its own with a `Golden update:` subject.

G4 knows about the primitives. On an element whose tag is one of them it ignores
a presentational prop (`variant`, `size`, `tone`, `status`, `loading`, … — the
full list is `PRESENTATIONAL_PROPS` in `scripts/audit/bindings.mjs`) as long as
the expression neither calls nor assigns nor mutates: no `(`, no `=>`, no `++`
or `--`, no backtick, and no `=` beyond `===`, `!==`, `>=`, `<=`. It also
ignores the `v-slot` / `#name` bindings that carry the copy — on the primitive
itself, and on a `<template>` **whose parent element is a primitive**. So
`<button :class="c ? a : b" @click="f">` becoming `<UiButton :variant="v"
:active="c" @click="f">` is no drift, and neither is moving copy into
`<UiModalPanel><template #header>`.

Recorded on every tag, primitive or not, and still to be justified: `:disabled`,
`:type`, `:href`, `:value`, `:is`, `:to`, `as`, any `@event`, `v-model`,
`v-for`, `v-show`, a `v-if` chain, and a presentational prop that calls
something, such as `:tone="toneFor(deal)"`. `as` is in that list because
`<UiCard as="section">` renders `<component :is="as">` — it picks the element,
which changes the accessibility tree — so an added element whose only binding is
`as` needs an `allowlist.json` row naming the tag and the exact binding:

```json
{ "file": "src/views/MyDeals.vue", "tag": "UiCard", "bindings": ["attr:as=section"], "reason": "keeps the landmark the div had" }
```

A slot on a `RouterView`, on a `VueDraggable`, or on a `<template>` under either
of them stays recorded.

For UI work, also run the end-to-end suite described above:

```
npm run e2e
```
