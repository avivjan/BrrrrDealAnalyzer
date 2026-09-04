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
- `e2e/golden/axe-baseline.json` — today's accessibility violations per route.
  Nothing here is fixed in Phase 0; the file exists so a later phase can be
  held to "no new ones".
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
- `npm run audit:baseline` — regenerates those manifests. Only run it when a change to behaviour
  has been agreed, and commit the result on its own with a `Golden update:` subject.

For UI work, also run the end-to-end suite described above:

```
npm run e2e
```
