# Quality snapshot — UI overhaul v1

**Measured, not fixed.** This page records where the finished v1 UI stands on accessibility,
layout across widths, bundle weight and Lighthouse. Nothing here was repaired while it was being
measured: every defect found is listed in [§7 Follow-ups for v2](#7-follow-ups-for-v2) instead.

| | |
| --- | --- |
| Branch | `refactor/ui-overhaul` |
| Tags in range | `ui-baseline` → `ui-p0` … `ui-p4` |
| Build measured | `VITE_API_URL=… npm run build` from `frontend/` |
| App under test | the production bundle behind `vite preview` on port 5173 |
| Backend | `frontend/e2e/backend/serve_throwaway.py` on port 8011 (throwaway SQLite) |
| Date | 2026-09-05 |

Everything below was produced with throwaway scripts outside the repo, driving the same two
servers `frontend/playwright.config.ts` starts. No file under `frontend/` was added or changed to
take these numbers — see [§8](#8-reproducing-this) for how to retake them.

---

## 1. Accessibility — axe-core

### 1.1 The six routes: baseline vs now

Same conditions as `frontend/e2e/flows/a11y.spec.ts`, so that the two columns are comparable:
chromium at 1280 × 720, `reducedMotion: 'reduce'`, and an **empty database** (the seed fixture
resets one before every test). The baseline column is `frontend/e2e/golden/axe-baseline.json`,
recorded at Phase 0 and untouched since. Counts are **elements failing**, not rules.

| Route | Rule | Impact | `ui-baseline` | now | |
| --- | --- | --- | --: | --: | --- |
| `/` | `landmark-one-main` | moderate | 1 | 1 | — |
| | `region` | moderate | 8 | 8 | — |
| | **total** | | **9** | **9** | |
| `/analyze` | `aria-input-field-name` | serious | 2 | 2 | — |
| | `button-name` | critical | 1 | **0** | fixed |
| | `label` | critical | 24 | **0** | fixed |
| | `landmark-one-main` | moderate | 1 | 1 | — |
| | `region` | moderate | 13 | 13 | — |
| | **total** | | **41** | **16** | |
| `/my-deals` | `button-name` | critical | 1 | **0** | fixed |
| | `color-contrast` | serious | 2 | **0** | fixed |
| | `heading-order` | moderate | 1 | 1 | — |
| | `landmark-one-main` | moderate | 1 | 1 | — |
| | `region` | moderate | 1 | 1 | — |
| | `scrollable-region-focusable` | serious | 1 | 1 | — |
| | **total** | | **7** | **4** | |
| `/bought-deals` | `button-name` | critical | 1 | **0** | fixed |
| | `color-contrast` | serious | 1 | **0** | fixed |
| | `heading-order` | moderate | 1 | 1 | — |
| | `landmark-one-main` | moderate | 1 | 1 | — |
| | `region` | moderate | 1 | 1 | — |
| | `scrollable-region-focusable` | serious | 1 | 1 | — |
| | **total** | | **6** | **4** | |
| `/liquidity` | `color-contrast` | serious | 1 | **0** | fixed |
| | `landmark-one-main` | moderate | 1 | 1 | — |
| | `region` | moderate | 3 | 3 | — |
| | **total** | | **5** | **4** | |
| `/reps` | `color-contrast` | serious | 3 | **0** | fixed |
| | `heading-order` | moderate | 1 | 1 | — |
| | `select-name` | critical | 1 | **0** | fixed |
| | **total** | | **5** | **1** | |
| **All routes** | | | **73** | **38** | **−48%** |

**Every `critical` violation is gone** (`button-name` ×3, `label` ×24, `select-name` ×1) and so is
every `color-contrast` failure (×7). Nothing new appeared on any route: this is the same verdict
`npm run verify:ui` reaches through gate G5, stated as counts rather than as a pass/fail.

### 1.2 What is left, and why

The 38 remaining elements are four rules and one localised pair.

| Rule | Where | Reading |
| --- | --- | --- |
| `region` (26) | every route | Content that sits outside a `<main>`/`<nav>`/`<header>` landmark. On `/analyze` (13) these are the field wrappers; on `/` (8) the feature cards. A landmark structure is an information-architecture decision, not a restyle. |
| `landmark-one-main` (5) | all but `/reps` | The page has no `<main>` at all. Same root cause as `region`; `/reps` is the one view that already has one, which is why it scores 1. |
| `heading-order` (3) | `/my-deals`, `/bought-deals`, `/reps` | The only `h1` is the page title and the section headings are `h3`, so `h1 → h3` skips a level. `/liquidity` has the same defect one level down — `UiSectionHeader as="h4"` under an `h3` in the sidebar cards — but it is not in the 38: those cards only render once the page has data, so it shows up in §1.4's seeded column instead. |
| `scrollable-region-focusable` (2) | `/my-deals`, `/bought-deals` | The kanban column body scrolls but has no `tabindex`, so a keyboard user cannot scroll it. Genuinely a bug — see §7. |
| `aria-input-field-name` (2) | `/analyze` | PrimeVue's `Slider` (the LTV control) renders a handle with `role="slider"` and no accessible name. |

### 1.3 The three modals (informational)

Not part of any baseline — axe has never been pointed at an open overlay before. Chromium at
1280 × 720, one deal seeded.

| Modal | Rule | Impact | Elements |
| --- | --- | --- | --: |
| Deal modal (`/my-deals`) | `color-contrast` | serious | **5** |
| | `region` | moderate | 9 |
| | `aria-input-field-name` | serious | 2 |
| | `heading-order` | moderate | 2 |
| | `landmark-no-duplicate-banner` | moderate | 1 |
| | `landmark-unique` | moderate | 1 |
| | **total** | | **20** |
| Save modal (`/analyze`) | `region` | moderate | 13 |
| | `aria-input-field-name` | serious | 2 |
| | `landmark-no-duplicate-banner` | moderate | 1 |
| | `landmark-unique` | moderate | 1 |
| | **total** | | **17** |
| Settings modal (`/liquidity`) | `region` | moderate | 3 |
| | `landmark-no-duplicate-banner` | moderate | 1 |
| | `landmark-unique` | moderate | 1 |
| | **total** | | **5** |

Two findings here are new information rather than more of the same:

- **`color-contrast` ×5 in the deal modal.** The analysis tiles colour a good number with the raw
  Tailwind class `text-emerald-600` (#059669) instead of the `positive` token — **3.77:1** on
  `surface`, below AA. `MyDeals.vue:339,346,348,355` and `BoughtDeals.vue:382,389,391,398`. The
  token itself is emerald-700 and measures 5.48:1, so this is four `return` strings, not a palette
  problem.
- **`landmark-no-duplicate-banner` / `landmark-unique` on all three.** An open modal renders its own
  `<header>` while the page's `<header>` is still in the tree, so two banner landmarks coexist. The
  page behind a modal should be `aria-hidden` / `inert` anyway.

### 1.4 Width × data matrix (informational)

The baseline is one width on an empty database, which hides two whole classes of defect. This
sweep crosses 1280 px and 390 px with an empty and a seeded database, so each extra violation can
be attributed to one cause or the other. Totals are elements.

| Route | 1280 empty | 390 empty | 1280 seeded | 390 seeded |
| --- | --: | --: | --: | --: |
| `/` | 9 | 9 | 10 | 13 |
| `/analyze` | 16 | 16 | 17 | 20 |
| `/my-deals` | 4 | 5 | 20 | 24 |
| `/bought-deals` | 4 | 4 | 21 | 24 |
| `/liquidity` | 4 | 4 | 5 | 8 |
| `/reps` | 1 | 1 | 2 | 5 |

What the two axes each expose:

- **Narrowing to 390 px** adds `button-name` on `/my-deals` — the *Add Deal* button is
  `<i class="pi pi-plus" aria-hidden>` plus `<span class="hidden md:inline">Add Deal</span>`
  (`MyDeals.vue:564-571`), so below `md` it is an icon with no accessible name at all. It also adds
  `page-has-heading-one` on both boards (the `h1` is hidden at that width, which is also why
  `heading-order` stops firing there — the level it skipped is gone).
- **Seeding data** adds `label` ×5 on `/bought-deals`: the substage checkboxes in
  `BoughtDealCard.vue:220-231` are bare `<input type="checkbox">` with an adjacent `<span>` that is
  neither a `<label>` nor referenced by `aria-labelledby`. **critical**, and invisible to the
  baseline purely because the baseline runs on an empty board. Every remaining rise is `region`
  tracking the number of cards on screen.

### 1.5 Lighthouse accessibility

Lighthouse runs its own subset of axe at a 412 px mobile viewport.

| Route | Score | Failing audits |
| --- | --: | --- |
| `/` | **100** | none |
| `/my-deals` | **94** | `button-name` — the same *Add Deal* button as §1.4 |

---

## 2. Screenshots

36 PNGs under `docs/ui-overhaul/screenshots/`, all with `reducedMotion: 'reduce'` so each is a
settled frame rather than a mid-animation one, and all on a seeded database (4 active deals,
2 bought deals, liquidity settings + 5 one-off flows + 1 recurring series, 2 REPS people).

Every shot was checked for horizontal overflow in the page
(`documentElement.scrollWidth − clientWidth`) at the moment it was taken. **Result: 0 px on all
36.** The Phase 0 "liquidity header wider than any phone" defect is gone at every width.

### 2.1 Chromium, viewport screenshots

| File | 390 | 768 | 1024 | 1440 |
| --- | --: | --: | --: | --: |
| `landing-<w>.png` | 63 kB | 93 kB | 77 kB | 90 kB |
| `analyze-<w>.png` | 27 kB | 39 kB | 46 kB | 54 kB |
| `my-deals-<w>.png` | 28 kB | 38 kB | 38 kB | 46 kB |
| `bought-deals-<w>.png` | 28 kB | 36 kB | 35 kB | 43 kB |
| `liquidity-<w>.png` | 27 kB | 34 kB | 40 kB | 45 kB |
| `reps-<w>.png` | 31 kB | 45 kB | 44 kB | 53 kB |
| `deal-modal-<w>.png` | 24 kB | 31 kB | 28 kB | 49 kB |

Viewports are 390 × 844, 768 × 1024, 1024 × 768 and 1440 × 900 at `deviceScaleFactor: 1`.

### 2.2 iPhone 14 (WebKit)

| File | Pixels | Size |
| --- | --- | --: |
| `iphone14-landing-390.png` | 780 × 1328 | 141 kB |
| `iphone14-analyze-390.png` | 780 × 1328 | 78 kB |
| `iphone14-my-deals-390.png` | 780 × 1328 | 80 kB |
| `iphone14-bought-deals-390.png` | 780 × 1328 | 77 kB |
| `iphone14-liquidity-390.png` | 780 × 1328 | 81 kB |
| `iphone14-reps-390.png` | 780 × 1328 | 87 kB |
| `iphone14-deal-modal-390.png` | 780 × 1328 | 52 kB |
| `iphone14-my-deals-landscape.png` | 1500 × 680 | 83 kB |

Playwright's `iPhone 14` at `deviceScaleFactor: 2` rather than its native 3, to hold every file
under the 200 kB budget without downscaling. **Largest file: 141 kB. Total: 1.87 MB.** Each PNG is
quantised to a 256-colour adaptive palette with Floyd–Steinberg dithering; nothing was resized, so
every image is still pixel-for-pixel the captured layout.

### 2.3 Notable observations

None of these is a regression against `ui-baseline`; they are what the finished v1 looks like.

1. **The liquidity chart's y-axis labels overprint the leading column, at every width.** The canvas
   is measured as flush with its container — `getBoundingClientRect().left === 0` at 390, 768 and
   1024 — so the plot area begins where the axis gutter should be and the first (partial) column
   renders underneath `450.0k`…`0.0k`. Worst at 390, where the labels cover a full-width bar
   (`iphone14-liquidity-390.png`); still visible at 768 (`liquidity-768.png`); at 1440 the interior
   bars clear the labels but the leading partial column and the reserve-threshold marker do not
   (`liquidity-1440.png`).
2. **The deal modal opened by deep link starts scrolled two-thirds down.** `?openDeal=…` leaves the
   modal body at `scrollTop: 1650` of `scrollHeight: 2490`, so the address and the input sections
   have been scrolled out of view above the visible area; opening the same deal by clicking its
   card lands at `scrollTop: 0`. Both measured — `deal-modal-1440.png` shows the deep-link state.
3. **`Cash Out Routi` is a truncated label, and it is truncated in the data.** Not CSS: the string
   is literally that in `frontend/src/utils/dealUtils.ts:260`, `DealCard.vue:254`,
   `MyDeals.vue:970` and `BoughtDeals.vue:985`, mirroring the backend's `cash_out_routi` field
   (`BackEnd/tests/_regression_snapshots/openapi.json`). Renaming it is a backend change or a
   display map, which is why the restyle left it alone.
4. **`/reps` prints its README hint twice.** The banner renders `store.configStatus.detail`, which
   already ends "See REPS_README.md for setup instructions.", and then adds a formatted copy of the
   same sentence (`RepsTracker.vue:139-141`). Present at `ui-baseline` too.
5. **Empty kanban columns reserve 243 px each on a phone.** Measured on `/bought-deals` at 390 ×
   664: six of the seven BRRRR stages were empty and each still occupied **243 CSS px** — 37 % of
   the viewport — to say "No deals in this stage". The one populated stage was 512 px. Reaching a
   deal that sits late in the pipeline therefore costs well over a screen of scrolling past nothing.
6. **iPhone 14 landscape leaves ~195 px for content.** The portfolio bar plus the tab row take
   ~145 px of a 340 px viewport on `/my-deals`. Nothing is clipped and nothing overflows, but only
   one partial card row is visible.
7. **The Mercury toast in `iphone14-liquidity-390.png` is a harness artefact,** not a defect: the
   throwaway backend deliberately has no Mercury credentials, so the sync reports "not configured".
   The same is true of the REPS config banner.
8. **Safe-area insets are 0 under Playwright.** `env(safe-area-inset-*)` resolves to zero in an
   emulated context, so the landscape shot proves the *layout* survives rotation but proves nothing
   about the notch or the home indicator. That closure is the real-device checklist's job —
   `docs/ui-overhaul/device-checklist.md`.

---

## 3. Bundle

`ui-baseline` was rebuilt for this, rather than quoted: the tag was checked out into a temporary
worktree, `npm ci` run against its own lockfile, then `npx vite build`. "Now" is `npm run build` on
this branch's HEAD.

Rebuilding rather than quoting mattered. The Phase 0 report records `index-*.js` at
580.78 kB / 169.91 kB gz, but two independent builds of the tag itself — one with the current
`node_modules` symlinked in, one after a clean `npm ci` — both produce **562.91 kB / 166.73 kB gz**,
with the CSS matching the report to the byte. The 580.78 figure therefore belongs to a slightly
later Phase 0 commit, not to `ui-baseline`. Using the measured number makes the reported growth
*larger* (+48.75 kB gz rather than +45.57), which is the direction to err in.

| | `ui-baseline` raw | `ui-baseline` gz | now raw | now gz | Δ raw | Δ gz |
| --- | --: | --: | --: | --: | --: | --: |
| JS | 562.91 kB | 166.73 kB | **704.16 kB** | **215.48 kB** | +141.25 kB | **+48.75 kB** |
| CSS | 75.76 kB | 14.19 kB | **88.27 kB** | **16.75 kB** | +12.51 kB | **+2.56 kB** |
| **Total** | **638.67 kB** | **180.92 kB** | **792.43 kB** | **232.23 kB** | +153.76 kB | **+51.31 kB (+28%)** |

Where the gzipped JS went, using the numbers the phase reports already measured:

| Milestone | JS gz | Δ gz | What it bought |
| --- | --: | --: | --- |
| `ui-baseline` | 166.73 kB | — | |
| `ui-p3` | 184.64 kB | +17.91 kB | tokens, primitives, the six restyled views |
| now (`ui-p4`+) | 215.48 kB | +30.84 kB | GSAP core (27.71 kB gz standalone) + `src/motion` |

**Fonts are the uncounted half.** `ui-baseline` shipped no webfont; this build adds seven
`@fontsource-variable/inter` `.woff2` subsets totalling **218.5 kB**. An English page fetches the
`latin` subset only (48.26 kB) and `latin-ext` (85.07 kB) if the text calls for it — real but
lazy, cached, and not in the table above.

Vite's "chunks larger than 500 kB" warning fires on both builds. It is a single-chunk-app warning
and predates the overhaul; the app has no route-level code splitting at either end.

---

## 4. Lighthouse

`npx lighthouse@12 <url> --preset=perf --form-factor=mobile --output=json --quiet
--chrome-flags="--headless=new --no-sandbox"`, pointed at `vite preview`, with `CHROME_PATH` set to
Playwright's bundled Chrome for Testing (no system Chrome is installed on this machine). Accessibility
was taken in a second pass with `--only-categories=accessibility`.

Three runs per route; every figure below is the **median of the three**, per metric. Reporting a
single run would have been wrong here: the very first run of `/` came in at perf 52 / LCP 8.5 s
against ~4.0 s and 76-77 on the two that followed — a cold-cache outlier, which the median absorbs.

| Route | Performance | Accessibility | FCP | LCP | CLS | TBT | Speed Index |
| --- | --: | --: | --: | --: | --: | --: | --: |
| `/` | **76** | **100** | 3.2 s | 4.0 s | **0.138** | 0 ms | 2.7 s |
| `/my-deals` | **80** | **94** | 3.0 s | 3.0 s | **0.178** | 100 ms | 2.5 s |

Spread across the three runs, `/` then `/my-deals`: performance 52-77 / 77-80, LCP 3.9-8.5 s /
3.0-3.4 s, CLS 0.131-0.139 / 0.178 (identical all three times). Everything except that one cold
first run is tight.

**Both routes fail the Core Web Vitals CLS threshold of 0.1,** and Lighthouse names one culprit for
almost all of it: a single shift worth **0.131** on `/` and **0.178** on `/my-deals`, on the app
shell's content block. The cause is `PortfolioStatsBar.vue:65` — `v-if="hasDeals"`, so the stats bar
does not exist until `GET /active-deals` resolves and then pushes the entire page down. Present at
`ui-baseline` (same `v-if`, same line), so the overhaul neither caused it nor fixed it. TBT is
near-zero, which says the 704 kB bundle parses cheaply; LCP is transfer-bound, and route-level code
splitting is the lever.

---

## 5. Contrast — `npm run audit:contrast`

```
PASS light fg on page                         17.06:1 (min 4.5:1)
PASS light fg on surface                      17.85:1 (min 4.5:1)
PASS light fg on surface-muted                16.30:1 (min 4.5:1)
PASS light fg-muted on page                   7.24:1 (min 4.5:1)
PASS light fg-muted on surface                7.58:1 (min 4.5:1)
PASS light fg-muted on surface-muted          6.92:1 (min 4.5:1)
PASS light primary-fg on primary              6.29:1 (min 4.5:1)
PASS light primary-fg on primary-hover        7.90:1 (min 4.5:1)
PASS light positive on surface                5.48:1 (min 4.5:1)
PASS light negative on surface                4.83:1 (min 4.5:1)
PASS light warning on surface                 5.02:1 (min 4.5:1)
PASS light positive on page                   5.24:1 (min 4.5:1)
PASS light negative on page                   4.62:1 (min 4.5:1)
PASS light warning on page                    4.80:1 (min 4.5:1)
PASS light ring on page                       4.27:1 (min 3:1)
PASS light ring on surface                    4.47:1 (min 3:1)
PASS dark  fg on page                         16.30:1 (min 4.5:1)
PASS dark  fg on surface                      13.35:1 (min 4.5:1)
PASS dark  fg on surface-muted                9.45:1 (min 4.5:1)
PASS dark  fg-muted on page                   12.02:1 (min 4.5:1)
PASS dark  fg-muted on surface                9.85:1 (min 4.5:1)
PASS dark  fg-muted on surface-muted          6.97:1 (min 4.5:1)
PASS dark  primary-fg on primary              5.98:1 (min 4.5:1)
PASS dark  primary-fg on primary-hover        8.96:1 (min 4.5:1)
PASS dark  positive on surface                7.61:1 (min 4.5:1)
PASS dark  negative on surface                5.29:1 (min 4.5:1)
PASS dark  warning on surface                 8.76:1 (min 4.5:1)
PASS dark  positive on page                   9.29:1 (min 4.5:1)
PASS dark  negative on page                   6.45:1 (min 4.5:1)
PASS dark  warning on page                    10.69:1 (min 4.5:1)
PASS dark  ring on page                       5.98:1 (min 3:1)
PASS dark  ring on surface                    4.90:1 (min 3:1)

CONTRAST PASS 32 pairs, WCAG AA (4.5:1 text, 3:1 ring)
```

The script audits **token pairs**. Two failing combinations exist in the app that it cannot see,
because neither is a pair of tokens on its declared background:

| Combination | Ratio | Where | Why the script misses it |
| --- | --: | --- | --- |
| `text-negative` on `bg-negative/10` | **4.14:1** | **ten call sites** — see below | The background is a 10 % tint of the foreground's own token, which is not one of the 16 declared pairs. |
| `text-emerald-600` on `surface` | **3.77:1** | analysis tiles: `MyDeals.vue:339,346,348,355`, `BoughtDeals.vue:382,389,391,398` | A raw Tailwind palette class, not a token at all. The `positive` token in the same position measures 5.48:1. |

Task 3.10 recorded the first of these as two error banners. It is wider than that: `bg-negative/10`
under `text-negative` appears at **ten** sites in the tree.

| Site | Kind |
| --- | --- |
| `PipelineTemplateEditor.vue:305` and `:327` | rendered, error banners |
| `SendOfferModal.vue:112` | rendered, the error branch |
| `RepsEntryModal.vue:461` | rendered, error banner |
| `RepsPeopleManager.vue:77` | rendered, error banner |
| `TransactionForm.vue:289` | rendered, the outflow toggle when selected |
| `UiIconButton.vue:52` (`danger`), `MyDeals.vue:1299`, `BoughtDeals.vue:1257` | on `:hover` only |
| `UiBadge.vue:50` (`tone="negative"`) | **latent** — the tone is defined but no call site passes it today |

Six rendered, three hover-only, one latent. That makes it a token decision rather than a call-site
one, exactly as Task 3.10 argued; the point of the list is that changing `--color-negative` now has
a visual review across six components rather than the two banners the deferral assumed.

---

## 6. Gate lines

`npm run verify:ui` with this page, its 36 screenshots and the device-checklist additions staged.
This is a docs-only change, so the interesting line is **G8**: it accepts every path written here
because all of them are repo-relative.

```
PASS G1 backend and root files unchanged since ui-baseline
PASS G2 stores/api/utils/router/types/config unchanged since ui-baseline
PASS G3 no behaviour drift
PASS G4 no behaviour drift
PASS G4b no behaviour drift
PASS G-HOVER every hover reveal pairs with its touch: counterpart
PASS G8 no absolute filesystem paths in 463 tracked files, 3 warning(s)
PASS G6 npm test and npm run build both succeeded
PASS G5 playwright, default projects
PASS G7 playwright, default projects
PASS GOLDEN-POLICY every golden change in ui-p0..HEAD is a "Golden update:" commit

verify:ui PASS
```

Playwright: **149 passed, 53 skipped, 0 failed** across the four default projects plus
`chromium-motion` (5.4 min). G8's three warnings are the pre-existing `process.cwd()` reads in
`frontend/e2e/fixtures/axe.ts` and `recorder.ts`, which live in a G2-frozen directory.

---

## 7. Follow-ups for v2

Ordered by severity. Nothing here was fixed; each is a v2 candidate.

### Accessibility

1. **Substage checkboxes have no accessible name** (`BoughtDealCard.vue:220-231`) — axe `label`,
   **critical**, ×5 per populated bought deal. `<input type="checkbox">` with a sibling `<span>`;
   needs a `<label>` wrapper or `aria-labelledby`. Hidden from the baseline because the baseline
   scans an empty board (§1.4).
2. **`mydeals.add-deal` is an unnamed icon button below 768 px** (`MyDeals.vue:564-571`) — axe
   `button-name`, **critical**, and the one thing costing `/my-deals` its Lighthouse 100. The label
   is `hidden md:inline`; an `aria-label` on the button fixes it without touching the layout.
3. **`text-emerald-600` bypasses the `positive` token** — 3.77:1, below AA, in the analysis tiles
   (`MyDeals.vue:339,346,348,355`; `BoughtDeals.vue:382,389,391,398`). Four `return` strings.
4. **`text-negative` on `bg-negative/10` is 4.14:1, at ten sites** — deferred here from Task 3.10,
   which recorded two of them. Six are rendered, three are `:hover` states and one is a latent
   `UiBadge` tone; the list is in §5. The honest fix is a token: `--color-negative` → red-700, or a
   separate `negative-ink`, applied everywhere at once and re-run through `npm run audit:contrast`.
5. **Kanban columns scroll but cannot be focused** — axe `scrollable-region-focusable`, serious, on
   `/my-deals` and `/bought-deals`. A keyboard user cannot scroll a column. Needs `tabindex="0"`
   plus an accessible name on the scroller.
6. **No `<main>` landmark on five of six routes** — 5 × `landmark-one-main` and most of the 26
   `region` findings collapse into this one change. `/reps` already has one and shows what it buys.
7. **`h1 → h3` skips a level** on `/my-deals`, `/bought-deals` and `/reps`; `/liquidity`'s sidebar
   adds an `h4` under an `h3` (`UiSectionHeader as="h4"`, noted in Task 3.9). Deferred here from
   Task 3.10.
8. **An open modal leaves the page's `<header>` in the accessibility tree** —
   `landmark-no-duplicate-banner` + `landmark-unique` on all three modals. The page behind a modal
   should be `inert`.
9. **PrimeVue's LTV slider has no accessible name** — `aria-input-field-name` ×2 on `/analyze`,
   also present inside the deal and save modals.
10. **The `role="combobox"` on the REPS property input advertises keyboard behaviour the script does
    not implement** (arrow keys, `aria-activedescendant`). Ratified as acceptable in Phase 3
    because the roles are still an improvement on nothing; the gap is real.

### Layout and interaction

11. **CLS 0.138 / 0.178, both above the 0.1 threshold** — `PortfolioStatsBar.vue:65`'s
    `v-if="hasDeals"` inserts the bar after the deals request resolves and pushes the page down.
    Reserving its height (or rendering a skeleton) is the single highest-value performance fix here.
12. **The deep-linked deal modal opens scrolled two-thirds down** (§2.3.2). Users arriving from
    *Analyze → Save* land in the middle of the form.
13. **The liquidity chart's plot area is flush with its container at every width**, so the y-axis
    labels overprint the leading column (§2.3.1). Worst at 390 px, where they cover a full bar.
14. **Empty kanban columns reserve 243 px each on a phone** (§2.3.5) — six empty stages on a
    664 px viewport put a late-pipeline deal more than a screen of empty scrolling away.
15. **`reps.refresh` is still a 36 px target** — under the 44 px touch minimum. Ratified in Phase
    3.11b as out of that sweep's scope; unchanged since.
16. **The PDF preview panel may bottom out in the iOS home-indicator band** — flagged in Phase 3.11b
    for `pb-safe-b`; not applied. Related: the preview `iframe` shows only the first page on iOS
    Safari, which no emulated run can reproduce.
17. **`TransactionForm`'s Enter shortcut is `metaKey`-only** — no `ctrlKey`, so it is a no-op for
    every Windows and Linux keyboard.

### Cosmetic / content

18. **The required-asterisk class never renders, in all four input primitives** — the
    `after:content-['*']` quoting bug found in Task 3.8, and it is not only `MoneyInput.vue:131`:
    `NumberInput.vue:62`, `SliderField.vue:63` and `DaysUntilRefiField.vue:84` carry the same line.
    Confirmed in the built CSS, which contains
    `after\:content-\[\\\'\*\\\']:after{--tw-content: \'*\'}` — Tailwind scanned the *source* text,
    backslashes and all, so the generated selector cannot match the class Vue actually emits
    (`after:content-['*']`), and the declaration it guards would set a literal `\'*\'` anyway. The
    fix is to write the class with double quotes outside and single inside.
19. **`Cash Out Routi` is a truncated label in the data** (§2.3.3) — needs a backend rename or a
    display map.
20. **`/reps` prints "See REPS_README.md for setup instructions." twice** (§2.3.4) — the backend's
    `detail` string already contains it.

---

## 8. Reproducing this

Kill any leftover `vite preview` / `serve_throwaway.py` first, then from `frontend/`:

```sh
python3 e2e/backend/serve_throwaway.py &
VITE_API_URL=http://localhost:8011 npm run build && npx vite preview --port 5173 --strictPort &
```

- **axe** — `@axe-core/playwright` against each route, one entry per rule with its element count,
  compared against `frontend/e2e/golden/axe-baseline.json`. The same comparison runs as gate G5 via
  `frontend/e2e/flows/a11y.spec.ts`.
- **Screenshots** — Playwright viewport (not full-page) captures, `reducedMotion: 'reduce'`, plus a
  `documentElement.scrollWidth − clientWidth` reading per shot.
- **Bundle** — `git worktree add <scratch>/bw-baseline ui-baseline`, then `npm ci && npx vite build`
  in its `frontend/`.
- **Lighthouse** — the command in §4, with `CHROME_PATH` pointed at a Chrome binary.
- **Contrast** — `npm run audit:contrast`, which needs no server.

The driver scripts lived outside the repo on purpose: `frontend/e2e/flows` and
`frontend/e2e/fixtures` are frozen by gate G2, and a snapshot should not need to touch them.

**Kill the hand-started servers before running `npm run verify:ui`.** Gate G6 runs a plain
`npm run build` with no `VITE_API_URL`, which rewrites `dist/` so the bundle points at the default
`http://localhost:8000`; a `vite preview` you left running then serves *that* bundle, because
playwright reuses an existing server instead of doing its own `VITE_API_URL=…` build. The suite
then tests an app with no reachable backend, and it fails somewhere unhelpful — a save round-trip —
while every render-only assertion still passes.
