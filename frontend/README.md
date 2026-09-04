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
