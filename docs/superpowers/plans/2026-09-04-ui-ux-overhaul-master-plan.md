# UI/UX Overhaul Master Plan — BrrrrDealAnalyzer Frontend

> **For agentic workers:** REQUIRED SUB-SKILL: use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to execute phase-by-phase. Every task ends with the mechanical regression gates in §3 passing. Skills to invoke are named per task in §4.

**Goal:** Replace the ad-hoc Tailwind styling of the Vue 3 frontend with a token-driven design system and GSAP-powered motion layer, while leaving every backend contract and every frontend behaviour (handlers, stores, watchers, fetch triggers, routes, submission lifecycles) byte-for-byte intact.

**Architecture:** Tokens (CSS custom properties) → Tailwind semantic utilities → shared UI primitives → PrimeVue pass-through presets → views. Motion lives in a new `src/motion/` layer attached through Vue directives and `<Transition>` JS hooks so component `<script>` blocks stay frozen. Behaviour is protected by six mechanical gates (§3), not by review alone.

**Tech Stack (existing):** Vue 3.5, Vite 7, TypeScript 5.9 strict, Pinia 3, vue-router 4, PrimeVue 4.5 (unstyled mode), Tailwind 3.4, `vue-draggable-plus`, `@vueuse/core`, Vitest 4 + `@vue/test-utils`. **Added:** runtime `gsap` (3.13.x pinned; core + ScrollTrigger only) and `@fontsource-variable/inter`; dev-only `@playwright/test`, `@axe-core/playwright`, `@vue/compiler-sfc` (made explicit for the audit scripts).

**Spec:** this document (§1–§2 are the design brief; §3 the invariant contract; §4–§5 the skill and motion strategy; §6–§8 the execution plan, risks and rollback).

## Global Constraints

- **No backend changes:** nothing under `BackEnd/`, `ReqRes/`, `routers/`, `runtime.txt` may change (gate G1).
- **No behavioural drift:** every handler, store action, watcher, lifecycle hook, route flow, fetch trigger, debounce and submission lifecycle is byte-identical (gates G2–G5). Native `alert()`/`confirm()` stay.
- **Functional tests first, then again at the end:** the Functional Characterization Suite (§3.6) is written and green against the *untouched* app in Phase 0, frozen, and re-run unchanged at every phase gate and in Phase 5. Any failure blocks the phase.
- **Platform support is a release criterion:** iOS Safari and Chrome on iPhone, and desktop Chrome, must remain fully functional (§3.7). Every phase gate runs the suite on the Chromium, WebKit and iPhone-emulation projects and ends with a real-iPhone smoke pass.
- **Frozen files:** `frontend/src/{stores,api,utils,router,types,config}/**` byte-identical; `<script setup>` blocks unchanged except the §3.2 whitelist.
- **Tooling:** Vue 3.5 / Vite 7 / Tailwind 3.4 / PrimeVue 4.5 unstyled stay at current versions; add only `gsap`, `@playwright/test`, `@axe-core/playwright`, `@vue/compiler-sfc` (explicit), `@fontsource-variable/inter`.
- **Accessibility floor:** WCAG 2.2 AA — 4.5:1 text contrast, visible focus, 24×24 CSS px minimum pointer targets (44 px for primary touch actions), `prefers-reduced-motion` honoured, no new axe violations.
- **Portable paths (user-added 2026-09-04):** no absolute filesystem paths (user-home paths, Windows drive paths, system temp paths) in any committed file — code, config, docs, or archived reports. Paths derive from `import.meta.url` / `__dirname` / `__file__` / `process.cwd()` or are repo-relative. Task 5.6 sweeps what exists; every task from now on is reviewed against this rule.

---

## 0. Context

**Why now.** The backend was just re-architected (PRs #21–#25, "Step 1…9") behind a golden-snapshot harness (`BackEnd/verify_regression.py`) that proved zero observable change. The frontend never received the same treatment: ~10k lines of `.vue` templates carry all visual decisions inline, with no tokens, no primitives layer, a barely-used PrimeVue install (`unstyled: true`, empty `pt`, only `InputNumber`/`Slider`/`ToggleSwitch` used), a dead `src/style.css`, Tailwind configured for an `Inter` font that is never loaded, and two visual dialects living side by side: a light `bg-gray-50` app and a hand-rolled dark `#1e2030/#2a2f45` island (the seven Liquidity files). Motion is a handful of CSS transitions, three `@keyframes`, and `animate-pulse`.

**What this delivers.** A modern, accessible, consistent interface (design system + motion polish) with a regression apparatus that makes "visual-only" a verifiable property of every commit, mirroring the discipline the backend refactor established.

**What this must not do.** Touch `BackEnd/**`, change any request/response shape, alter any store/API/util/router/type file, or change what any handler, watcher, or lifecycle hook does.

---

## 1. Frontend surface (audit results)

### 1.1 Stack facts that shape the plan

| Fact | Evidence | Consequence |
|---|---|---|
| PrimeVue is **unstyled** with empty global `pt` | `frontend/src/main.ts:15-21` | Design system is delivered as tokens + Tailwind + a global `pt` preset; no theme preset swap (the installed `@primevue/themes` stays unused). Only 3 PrimeVue components exist (`InputNumber` ×2 files, `Slider`, `ToggleSwitch`) |
| Tailwind `darkMode: 'class'`, `fontFamily.sans = Inter` never loaded | `frontend/tailwind.config.js:3,11`; no `<link>`/`@font-face` anywhere | Phase 1 loads Inter (self-hosted or Google Fonts with `font-display: swap`) and adds tokens; dark mode is token-ready but ships off by default (§2.4) |
| Two stylesheets, one dead | `src/assets/main.css` (imported); `src/style.css` (Vite scaffold, **not imported**) | Delete `style.css`; `main.css` becomes the token root |
| Global chrome in `App.vue` | `App.vue:48-70`: connection dot, `PortfolioStatsBar`, `RouterView`; interceptors + initial fetches in `onMounted` | App.vue **script** is frozen; its template becomes the flex shell (§6 Phase 3.1) and, in Phase 4.2, gains the one approved `RouterView` slot rewrite (`<UiTransition preset="page" appear>`, enter-only, opacity-only — §5.2/§5.3) |
| Router logs every navigation | `router/index.ts:45-53` | Frozen file; keep the `console.group` behaviour |
| Vitest env is `node`; component tests opt into jsdom per file | `vite.config.ts:9`; `// @vitest-environment jsdom` headers | New component tests follow the same header convention |
| No lint/format, no CI, Netlify runs `vue-tsc -b && vite build` only | explorer report | Every gate in §3 runs locally via one `npm run verify:ui` script; PR template lists the gate output |
| Existing `<Transition>` (6) and `@keyframes` (3) | `PortfolioStatsBar.vue:63,173`, `LandingPage.vue:312`, `AnalyzeDeal.vue:343`, liquidity modals/toast/fade | The liquidity Teleported modals, toast, chart tooltip and stats bar **keep** their CSS transitions (restyled); the `AnalyzeDeal` keyframe is replaced by a `UiTransition` preset; new GSAP motion is added only through §5's zero-script mechanisms |
| Drag-and-drop via `VueDraggable` in 3 files | `MyDeals.vue:596`, `BoughtDeals.vue:524`, `PipelineTemplateEditor.vue:312` | Drag mechanics untouched; only the SortableJS `ghost-class`/`chosen-class`/`animation` visual props change (§5.2). A keyboard/button alternative to dragging (WCAG 2.2 `dragging-alternative`) would need new handlers, which the script freeze forbids — recorded in `docs/ui-overhaul/decisions.md` as the first follow-up after the overhaul |
| Hardcoded dark hex palette in 7 Liquidity files | `#1e2030` ×31, `#2a2f45` ×31, `#1a1d2e`, `#141722`, `#0f1117` | Mapped to tokens in Phase 3 (§2.4 decides light vs scoped-dark) |

### 1.2 Component & view inventory (presentation layer)

| Unit | Lines | Styling today | Motion today | Restyle risk |
|---|---|---|---|---|
| `views/LandingPage.vue` | 722 | 494-line scoped CSS (BEM-ish), gradient utilities from data arrays; `100dvh; overflow:hidden`; `.has-bar` hardcodes a 60px stats-bar height | `float` 18s loop on blobs, hover choreography (`translateY(-4px) scale(1.015)`), shimmer sweeps | Low (no store bindings beyond `hasPortfolioBar`) |
| `views/AnalyzeDeal.vue` | 356 | Tailwind + 14-line scoped `fade-in-up` | `animate-pulse` on validation errors, `hover:scale` CTAs | Low |
| `views/MyDeals.vue` | 1254 | Tailwind only; board = 5 stage rows; `VueDraggable` branch **and** a plain-grid branch (`useMediaQuery("(pointer: fine)")`, `:27`); 550-line detail modal; PDF preview modal | `transition-*` ×14, Sortable `animation=150` | **High** — autosave deep watch, settle window, `scrollIntoView` |
| `views/BoughtDeals.vue` | 1287 | Near-verbatim fork of MyDeals modal + pipeline stepper (`:613-668`, labels at `text-[9px]` sized by inline `width: 100/n%`) + substage checklist | same | **High** — same autosave machinery |
| `views/LiquidityTimeline.vue` + 6 `components/liquidity/*` | 560 + 1641 | Hand-rolled dark hex palette, `font-mono`, input class string repeated 8×, sidebar card class repeated 7×; sidebar `hidden lg:block` | CSS `<Transition name="modal">` ×3 (inside `<Teleport to="body">`), `toast`, tooltip `fade`; canvas rAF inertia | Medium — canvas theme is JS (exemption E1); `ResizeObserver` redraw |
| `views/RepsTracker.vue` + 5 `components/reps/*` | 185 + 1526 | Tailwind `slate-*` (deal views use `gray-*`); card recipe repeated 4× | `animate-pulse` timer dot | Low–Medium — `RepsEntryModal` 150ms blur timeout |
| `App.vue` | 71 | 3×3px connection dot (title only) + `PortfolioStatsBar` + `RouterView` | `animate-pulse` | Low (template only) |
| `components/PortfolioStatsBar.vue` | 285 | 140-line scoped CSS, raw hex gradients | `<Transition name="stats-bar">`, `shimmer` 8s loop, rAF counters in script (frozen) | Low |
| `components/DealCard.vue` / `BoughtDealCard.vue` | 310 / 215 | Absolute-positioned hover-only action buttons with magic offsets (`right-9`, `right-[5.75rem]`, `right-[8.25rem]`, stage-dependent at `DealCard.vue:140`); emoji in badges | `hover:scale-[1.02]`, `group-hover:opacity-100` | Medium (touch users cannot reach actions today) |
| `components/DealInputsForm.vue` | 513 | Six computed class strings keyed on `surface` (`:138-178`) — the only variant system in the app; `ToggleSwitch :pt` | none | **High test coupling** (§1.4) |
| `components/ui/MoneyInput.vue`, `NumberInput.vue`, `SliderField.vue`, `DaysUntilRefiField.vue` | 142/72/97/146 | Inline class strings; `SliderField :pt` **is** the slider's entire look; `<label>`s unassociated | `transition-all` | High test coupling |
| `components/SendOfferModal.vue`, `PipelineTemplateEditor.vue` | 128 / 494 | Hand-rolled overlays; 15 icon-only buttons with `title` only, hit areas < 24px | inert `transition-all` | Low / Medium (drag handle) |
| `components/HelloWorld.vue`, `src/style.css`, `assets/vue.svg` | — | dead | — | Delete in Phase 0 |

Cross-cutting debt the design system resolves: four competing money formatters (frozen — restyle only), `gray` vs `slate` split, ~70 raw hex usages, `.custom-scrollbar` referenced 3× but undefined, zero `aria-label`, zero `for=` on ~40 labels, ~80 `focus:outline-none` (many without a ring), hover-only actions, `text-[9px]/[10px]` labels, no `prefers-reduced-motion` handling anywhere.

### 1.3 Behaviour/binding map (what the gates freeze)

**Frozen logic surface:** 6 Pinia setup-stores (`dealStore`, `boughtDealStore`, `liquidityStore`, `repsStore`, `pipelineTemplateStore`, `connectionStore`), `api/index.ts` (30 wrappers) + `api/liquidity.ts` (11), router (6 eager routes, console-logging `beforeEach`), utils, types, config. No composables directory; `@vueuse` `useDebounceFn`/`useMediaQuery` used only in MyDeals/BoughtDeals.

**Lifecycles that motion must not perturb** (each becomes a Playwright flow in §3.5 and a "hazard" rule in §5.3):
1. **Analyze → Save** (`AnalyzeDeal.vue:41-92`): validate → modal → `POST /active-deals` → `router.push('/my-deals?openDeal=…')`. No `/analyze` call on this page.
2. **Deal modal autosave** (`MyDeals.vue:360-420`, `BoughtDeals.vue:222-269`): open = deep clone + `settleUntilMs = now + 250`; deep `watch(editingDeal)` → debounced analyze (500 ms, `POST /analyze/*`) and, outside the settle window, `isDirty` + debounced save (2000 ms, `PUT /active-deals/{id}` or `/bought-deals/{id}`); `closeModal` flushes a pending save. Deep-link open triggers `nextTick → scrollIntoView` on `analysisResultsEl` (`MyDeals.vue:392-396`).
3. **Board drag** (`onDrop`/`onAdd`): cross-column → local `deal.stage` mutation + `updateDealStage` PUT; same-column reorder is intentionally **not** persisted; Bought board blocks >1-stage moves and incomplete substages with `alert()`. Plain-grid fallback on coarse pointers.
4. **Move-to-Bought / duplicate / delete**: `confirm()` → store action → `alert()` on failure; modal variants flush the save first (except delete).
5. **PDF**: `POST /reports/*-pdf` (blob) → object URL → `<iframe>` preview → `<a download>`; revoked on close/unmount.
6. **Liquidity**: `fetchAll` → `syncFromMercury` on mount; simulation warning gate before saves; hand-rolled toast (4000 ms).
7. **REPS**: localStorage-persisted timers/snapshots/active tab; property dropdown closes on a 150 ms blur timeout (`RepsEntryModal.vue:176`); `SendOfferModal` auto-closes 1500 ms after success.
8. **Global**: axios interceptors + `checkConnection()` + `fetchDeals()` in `App.vue onMounted`; every request toggles the connection dot.

Facts that make some template edits safe: there are **no `<form>` elements, no `type="submit"`, no `autofocus`, no `.focus()` calls, no `v-show`** anywhere; the only `@keydown` handlers are on inputs, the liquidity `TransactionForm` wrapper (Escape/⌘-Enter) and the chart container.

### 1.4 Test coverage that a visual change can break

135 Vitest cases in 6 files. 66 pure-util cases are refactor-proof. The 69 component cases include these visual couplings, which Phase 0 rewrites **once, deliberately**, before any styling changes:

- `DealInputsForm.test.ts:389-440` — asserts literal Tailwind classes (`bg-white`, `bg-gray-50`, `space-y-8`, `space-y-6`, `class="contents"`, `grid grid-cols-2 gap-2`) and per-surface heading copy. Rewrite to assert the **surface contract** via a `data-surface="card|panel"` attribute and a `data-layout="flat|paired"` attribute on the Rehab/Contingency wrapper, keeping the heading-copy assertions (copy is behaviour-visible and stays).
- `DealInputsForm.test.ts:370` — `wrapper.find("button")` = Quick Defaults must stay the **first** button. Keep by contract (documented in the component header) or switch the test to `[data-testid="quick-defaults"]`.
- `DaysUntilRefiField.test.ts:26,31-34,37-38` — first button = calendar toggle, last button = Done, date inputs indexed 0/1, `disabled` must remain a native attribute.
- `MoneyInput.test.ts:102-112` — single `<input>`, single `<label>` with exact text, hint text `= $50,000` asserted on whole-component text (no other `=` may appear).

---

## 2. Design direction (from `ui-ux-pro-max` searches, verified)

### 2.1 Product classification
`--domain product "fintech calculator analytics dashboard tool"` → **Financial Dashboard**: primary style *Data-Dense Dashboard* (+ Minimalism/Swiss secondary), palette focus "trust blue + profit green + red alerts". The generic `--design-system` run returned a marketing "Enterprise Gateway" pattern with a luxury serif (Cinzel), which is a mis-fit for a numeric tool and is **rejected**; the targeted domain queries below are the source of truth.

### 2.2 Tokens (three layers: primitive → semantic → component)

**Color (semantic, light default).** From `--domain color` "Personal Finance Tracker" (trust blue + profit green) adapted to the app's existing indigo accent for continuity:

| Token | Light | Role |
|---|---|---|
| `--color-bg` | slate-50 `#F8FAFC` | page |
| `--color-surface` | white | cards, modals |
| `--color-surface-muted` | slate-100 | panel sections inside modals (current `bg-gray-50`) |
| `--color-border` | slate-200 | dividers |
| `--color-fg` / `--color-fg-muted` | slate-900 / slate-600 | text (4.5:1 verified) |
| `--color-primary` / `-hover` / `-fg` | indigo-600 `#4F46E5` / indigo-700 / white | primary CTA (existing accent) |
| `--color-positive` / `-negative` / `-warning` | emerald-600 / red-600 / amber-600 | financial semantics, always paired with icon or sign, never color-only |
| `--color-ring` | indigo-500 | focus rings (2px, offset 2px) |
| `--color-chart-1..6` | categorical set validated for contrast | Liquidity `TimelineChart` |

Dark values are defined under `.dark` for every token (desaturated tonal variants, not inversions) so the Liquidity island and a future toggle need no rework.

**Typography.** `--domain typography` → "Modern Dark Cinema (Inter System)": single-family Inter; `font-variant-numeric: tabular-nums` on all money/percent cells (`number-tabular` rule). Scale: 12 / 14 / 16 / 18 / 24 / 32; weights 400 body, 500 labels, 600–700 headings. Body 16px minimum on mobile.

**Spacing / radius / elevation.** 4-pt scale (`--space-1..12`), `--density` 7 (standard, not dashboard-dense: this is a form-heavy tool). Radii `sm 6px / md 10px / lg 16px`. Three-step shadow scale (`elevation-consistent`).

**Motion tokens** (shared by CSS and GSAP, §5.1): `--dur-fast 150ms`, `--dur-base 250ms`, `--dur-slow 400ms`; eases `standard = power2.out`, `emphasized = power3.inOut`, `exit = power1.in`. Exit ≈ 60–70 % of enter (`exit-faster-than-enter`).

### 2.3 Component specifications (shared primitives, Phase 2)
`UiButton` (primary/secondary/ghost/danger/brrrr/flip; sm/md/lg; loading is visual only; 44 px hit area on md), `UiIconButton` (requires `aria-label`), `UiCard` (surface/muted/elevated, optional interactive), `UiBadge` (incl. deal-type variant with icon), `UiStatTile` (tabular numbers, tone with sign/icon so meaning is never colour-only), `UiField` (label + helper + error with `aria-describedby`; the control stays in the parent template), `UiModalPanel` (panel only — the overlay with `@click.self` stays in the parent), `UiSectionHeader`, `UiEmptyState`, `UiSkeleton`, `UiSaveStatus`, `UiTabs`, `UiStepper`. The liquidity toast stays inline and only gains a motion preset. Each is a **presentational** component: props in, slots out, no store access, no emits beyond DOM passthrough (full contracts in Phase 2, §6).

### 2.4 Decisions taken (override at plan review)
1. **Light theme app-wide; dark tokens defined but no toggle shipped.** The Liquidity island is migrated onto tokens and rendered in the global light theme so the app has one visual language. *Alternative:* keep Liquidity dark by wrapping its view root in `class="dark"` — a one-line switch in Phase 3, no other rework.
2. **PrimeVue stays unstyled**; styling arrives through a global `pt` preset built from tokens (`src/design/primevue-pt.ts`). No theme preset, no new PrimeVue components introduced (avoids changing the DOM the three existing tests select on).
3. **Icons:** keep `primeicons` (already loaded, consistent stroke) — `--domain icons` returned no match for a set switch, so no new icon dependency.
4. **Playwright is added as a dev dependency** to record the network-contract goldens (§3.5). It never runs in Netlify's build.
5. **Commit convention:** continue the house style `Step N: <what changed>`; one branch `refactor/ui-overhaul` with phase tags `ui-p0 … ui-p5`.

---

## 3. Zero-regression invariant, made mechanical

Every task ends with `npm run verify:ui` green. The script runs gates G1–G7 and prints a one-line PASS/FAIL per gate.

| Gate | What it proves | Mechanism |
|---|---|---|
| **G1 Backend untouched** | No file outside `frontend/**` (and `docs/**`, `design-system/**`) changed | `git diff --quiet ui-baseline -- . ':!frontend' ':!docs' ':!design-system'`; plus `cd BackEnd && python3 verify_regression.py verify` and `pytest -q` at each phase gate (cheap proof the API contract is byte-identical) |
| **G2 Logic files frozen** | Stores, API client, utils, router, types, config are byte-identical | `git diff --quiet ui-baseline -- frontend/src/stores frontend/src/api frontend/src/utils frontend/src/router frontend/src/types frontend/src/config` |
| **G3 Script-block freeze** | Every existing `.vue` file's `<script setup>` block is unchanged, except whitelisted additive edits | `frontend/scripts/audit/script-blocks.mjs` extracts each `<script …>…</script>` block, hashes it, compares to `frontend/scripts/audit/golden/script-blocks.json`. Hash equal → pass. Otherwise a line diff (`diff` package) must contain **zero removed lines** and only added lines matching the §3.2 patterns, placed either in the import block or **after the last baseline line** (Vue runs `onMounted` hooks in registration order, so an appended hook can never run before an existing one). The E1 literal substitution is the only permitted removal. Every accepted diff is listed in `frontend/scripts/audit/allowlist.json` as `{file, reason}` |
| **G4 Binding manifest** | Every template event binding, `v-model`, `v-if/v-show` condition, `watch` source, and lifecycle hook is unchanged | `frontend/scripts/audit/bindings.mjs` parses templates with `@vue/compiler-sfc` and emits, per file, the **ordered sequence** of binding-bearing elements `{tag, bindings[]}` in document order with non-binding wrappers collapsed — so inserting `<UiTransition>`, `<UiCard>` or a styling `div` changes nothing, while a moved/renamed handler, a changed or re-ordered `v-if` chain, or a changed `v-for` source fails. Behavioural static attributes are part of the manifest (`type`, `href`, `target`, `rel`, `accept`, `capture`, `multiple`, `inputmode`, `autocomplete`, `placeholder`, `title`, `tabindex`, `handle`, `group`, `animation`); visual ones are ignored (`class`, `style`, `pt`, `inputClass`, `ghost-class`, `chosen-class`, `data-*`, `aria-*`, `role`, `id`, `for`). A **G4b text manifest** (whitespace-collapsed static text per file) freezes on-screen copy too. Details in §3.4 |
| **G5 Network contract** | Each user flow issues the same HTTP calls with the same payloads, in the same order | Playwright flows (§3.5) run against the real backend on a throwaway SQLite DB; `page.on('request')` records `{method, path, json body}`; goldens under `frontend/e2e/golden/*.json` with volatile keys redacted (reuse the backend's `VOLATILE_KEYS` list). Diff must be empty |
| **G6 Unit tests + types** | Existing suite and new primitive tests pass; strict TS holds | `npm test` (135 + new) and `npm run build` (vue-tsc, `noUnusedLocals`) |
| **G7 Accessibility & motion** | No new axe violations; reduced-motion honoured; focus visible | `@axe-core/playwright` on every route (light theme) with a stored violation baseline; a Playwright run with `reducedMotion: 'reduce'` asserts no element has a running GSAP tween after mount (`gsap.globalTimeline.getChildren().length === 0`) |

### 3.1 Baseline capture (Phase 0)
Tag the current `main` as `ui-baseline`. Generate goldens for G3, G4, G5 **before** any styling change and commit them. Later phases may only change goldens through an explicit "golden update" commit that contains nothing else and is reviewed line-by-line.

### 3.2 Whitelisted script edits (the only ones G3 accepts)
Motion needs **no script edits at all**: transitions are applied with the globally registered `<UiTransition preset="…">` component and directives (§5.1), both registered once in `main.ts`. Imports, where needed, follow the codebase's relative style (there is no `@/` alias and none is added).
1. `import { useId } from "vue"` (or `{ ref, useId }`) as a **separate new import line** — duplicate `from "vue"` imports are legal; the existing `vue` import line is never edited (an edited line is a modified line and fails G3).
2. `const <name>Id = useId()` — appended after the last baseline line; only for `for`/`id` label wiring on PrimeVue inputs (`NumberInput`, `SliderField`, `ToggleSwitch` via `inputId`) where wrapping the control inside its `<label>` is impossible.
3. `const <name>Ref = ref<HTMLElement | null>(null)` — same placement; reserved, expected to be unused (directives read `el` directly).
4. **Exemption E1 — `components/liquidity/TimelineChart.vue`** (canvas colours live in JS): `import { chartToken } from "../../design/chartTokens"`, and each colour literal inside `draw()` (`TimelineChart.vue:106-308`: 17 hex strings plus the `rgba(…)` strings at `:142`, `:172`, `:178`) replaced by `chartToken('<name>')`. Verified line-by-line: a removed line is accepted only when the paired added line is identical after substituting `'#…'`/`'rgba(…)'` → `chartToken('…')`. `chartToken` resolves the `--chart-*` custom property **once per page** (`draw()` runs on every `pointermove`, `:370-390`) and falls back to **today's exact literal**, so an unresolved variable can never silently recolour the canvas (canvas ignores an invalid `fillStyle` and keeps the previous one — an invisible failure).
5. Nothing else. No change to `watch`, `computed`, handlers, `nextTick`, `useDebounceFn`, timers, `scrollIntoView`, `onMounted` bodies, or `defineProps/defineEmits`.

### 3.3 Template edits that are behaviour-neutral (allowed) vs. not (forbidden)
| Allowed | Forbidden |
|---|---|
| Changing `class`, `style`, `:pt`; adding `data-*`, `aria-*`, `title`, `id`/`for`, `ref="…"`; adding global directives (`v-reveal`, `v-press`, `v-flash`); wrapping the single root element that carries a `v-if` in `<UiTransition preset="…" appear>`; wrapping a keyed `v-for` list in `<UiTransitionGroup preset="listItem" tag="div">` **only when the list is not inside `<VueDraggable>` and not index-keyed**; replacing `button/div/span/section/h*/p/label` with presentational primitives (`UiButton`, `UiCard`, …) that forward `$attrs` and slots; moving the `VueDraggable` `ghost-class`/`chosen-class`/`animation` values to token classes; adding a `v-if` on a **new, purely presentational** element that only reads existing state (e.g. an empty-column state on `!columns[stage.id]?.length`) — such additions appear as new manifest rows and must be listed in the golden-update commit | Renaming/moving `@click`/`v-model`/`@update:*`/`@change`/`@add`; changing `v-if`/`v-else-if` conditions or their order; `mode="out-in"` anywhere (delays mount → delays `onMounted` fetches and pushes form-input emits past the 250 ms settle window); adding/removing `.prevent/.stop/.self` modifiers; changing native `disabled` to `aria-disabled`; giving buttons a `type` other than `button` (no forms exist, so `type="button"` is inert); swapping `input/select/textarea/a/RouterLink/iframe/canvas/VueDraggable/Teleport` for anything else; putting `<TransitionGroup>` or extra wrappers between `<VueDraggable>` and its `v-for` children (SortableJS owns that DOM); changing the element that carries `@click.self` (overlay stays a raw `div`); deduplicating the MyDeals/BoughtDeals modal into a shared component (moves handlers) |

### 3.4 Static audit script design (`frontend/scripts/audit/`)
- `sfc.mjs`: `parse()` from `@vue/compiler-sfc` (already a transitive dep of `@vitejs/plugin-vue`; add as explicit devDependency).
- `script-blocks.mjs` → `{ "src/views/MyDeals.vue": { "sha256": "…", "lines": 612 } }`.
- `bindings.mjs` walks `descriptor.template.ast` — the parsed, untransformed `RootNode`, so `v-if`/`v-for`/`v-model` are still `DirectiveNode` props (type 7: `name`, `rawName`, `arg`, `exp`, `modifiers`) on `ElementNode`s (type 1); static attributes are type 6. For every element carrying at least one behavioural prop it appends `{ tag, bindings: [{kind, arg, modifiers, expression}] }` to an **ordered list** in document order; elements with no behavioural props are skipped, which collapses wrappers. `kind` ∈ `on | model | if | else-if | else | show | for | slot | bind:<arg> | attr:<name>`; expressions are whitespace-collapsed (`DealInputsForm.vue:398-400` and `MyDeals.vue:975-985` are multi-line today). Compared as a list diff with source line numbers in the report.
- **Allowed structural deltas** (comparator allowlist; anything else fails): (1) tag alias table `button → UiButton | UiIconButton` only — `input/select/textarea/a/RouterLink/iframe/canvas/VueDraggable/Teleport` never change tag; (2) new `UiTransition`/`UiTransitionGroup` nodes whose only attributes are `preset`, `appear`, `tag`; (3) new **valueless** directives from the set `reveal`, `press`, `hover-lift`, `flash`, `count-up` (no expression, so they cannot reference component state); (4) new `v-if` on a new purely presentational element that reads existing state (§3.3), listed in the golden update; (5) the one-time `App.vue` `RouterView` slot rewrite (§6 Phase 4.2), approved by name.
- **G4b text manifest**: per file, the whitespace-collapsed static text nodes in document order. "Visual-only" means copy is frozen too; intentional copy changes (e.g. the emoji removed from the deal-type badge) go through the golden update.
- `bindings.mjs` also emits, from the frozen `<script>` text (regex, not AST), the list of `watch(` / `watchEffect(` sources and the presence of each lifecycle hook — a belt-and-braces check on top of G3.
- `verify-ui.mjs` orchestrates G1–G7 and is wired to `npm run verify:ui`; `npm run verify:ui -- --phase` additionally runs the backend proofs and the full multi-browser E2E matrix (§3.7).

### 3.5 Network-contract flows (Playwright, `frontend/e2e/`)
Backend under test: `frontend/e2e/backend/serve_throwaway.py` does `sys.path.insert(0, <BackEnd>)`, `import verify_regression` (its module-level code already redirects `DATABASE_URL` to a temp SQLite file, stubs `load_dotenv`, scrubs the Google/Mercury/SMTP credentials and installs the SQLite UUID shim — `verify_regression.py:60-121`; its CLI is guarded by `if __name__ == "__main__"`), then `import main; uvicorn.run(main.app, port=8011)`. Zero backend changes, identical isolation. Once scrubbed, every credential-gated endpoint is deterministic: `/liquidity/mercury-balance` → 503, `/send-offer` → `{success:false, message:"Email password not configured"}`, `/reps/config-status` → `configured:false`, `/reps/upload*` and `/reps/log` → 503. Frontend: CORS in `BackEnd/main.py:25-29` only allows `localhost:5173`/`3000`, so build with `VITE_API_URL=http://localhost:8011 vite build` and serve `vite preview --port 5173 --strictPort`; both processes are Playwright `webServer` entries.

Determinism rules: `page.clock.install({ time: '2026-09-04T10:00:00' })` per test freezes `todayISO()` (liquidity defaults, `TransactionForm.vue:72`), `new Date().toISOString()` (`RepsEntryModal.vue:373`) and lets `clock.runFor(2500)` drive the 500 ms analyze / 2000 ms autosave debounces and the 1500 ms `SendOfferModal` auto-close exactly; `page.on('dialog')` records every `alert`/`confirm` message and accepts; the FCS runs under `page.emulateMedia({ reducedMotion: 'reduce' })` so GSAP is inert and no assertion can race a tween, plus one **motion-on smoke project** (chromium, `no-preference`) for the `done()`/pointer-events invariants of §5.3; a fresh browser context per test resets the REPS `localStorage` keys; `context.grantPermissions(['geolocation'])` + `setGeolocation` makes `captureGeoSnapshot` deterministic; `clipboard-write` is granted on chromium only (WebKit takes the existing `catch` branch).

Flows recorded (one golden each; the list is finalised from the binding audit in §1.3):
1. `landing` — load `/`, expect `GET /helloworld`, `GET /active-deals` (App.vue mount)
2. `analyze-brrr` — fill form via test-ids, submit, expect `POST /analyze/brrr` body == fixture; result values rendered (text assertions on KPI test-ids)
3. `analyze-flip` — same for FLIP
4. `save-active-deal` — from analyze → save, expect `POST /active-deals`
5. `my-deals-autosave` — open card modal, edit a field, wait > debounce, expect single `PUT /active-deals/{id}` with full body and `POST /analyze/*` re-analyze in the recorded order
6. `my-deals-duplicate-delete` — `POST …/duplicate`, `DELETE …`
7. `move-to-bought` — `POST /bought-deals/from-active/{id}`
8. `bought-deals-autosave` — stage/substage toggles → `PUT /bought-deals/{id}`
9. `pipeline-template-edit` — drag reorder + save → `PUT /pipeline-templates/{deal_type}`
10. `pdf-report` — `POST /reports/brrr-pdf` (response type + download trigger)
11. `send-offer` — modal submit → `POST /send-offer` (deterministic 500/"not configured" path)
12. `liquidity` — settings/transactions/recurring CRUD → the 8 `/liquidity/*` calls
13. `reps` — `GET /reps/config-status` → banner path; people/categories CRUD; `setInputFiles` on the hidden file inputs (`RepsEntryModal.vue:681-700`, `RepsTimer.vue:217-233`) → `POST /reps/upload-batch` (multipart field names + file count recorded) → 503 → `formError` shown
14. `modal-double-close` — click Close/backdrop twice quickly on the deal modal → exactly one `PUT`, no second `closeModal` effect (guards the leave-animation window)
15. `deep-link-open` — `/my-deals?openDeal=<id>&dealType=BRRRR&section=2` → modal opens after `fetchDeals`, `router.replace` clears the query, results `scrollIntoView` target visible; the overlay's `getBoundingClientRect()` equals the viewport at 50 ms and 500 ms (fixed-under-transform guard)
16. `mocked-success-paths` — the only two flows that need credentials to succeed use `page.route` mocks in dedicated specs: `/send-offer` → `{success:true}` (characterizes the 1500 ms close + form reset) and `/liquidity/mercury-balance` → fixture (characterizes the sidebar breakdown at `LiquiditySidebar.vue:124-159`). Everything else hits the real throwaway backend.

Hard-flow notes: the board drag (`chromium` only) uses `mouse.down` → two `mouse.move` steps → `mouse.up` (SortableJS native DnD) and pins **exactly one** `PUT /active-deals/{id}` (`onAdd` sets `deal.stage` first, then `onDrop` sees it equal and skips); if it flakes, it lives in a `@quarantine` project that must pass 3/3 locally while the main suite characterizes stage changes through the modal `<select>` (`MyDeals.vue:742`). The PDF flow asserts `POST /reports/brrr-pdf?address=`, the preview modal with `iframe[src^="blob:"]`, and `waitForEvent('download').suggestedFilename() === "BigWhales_BRRRR_<addr>.pdf"`. The liquidity chart is canvas: drive selection with `ArrowRight` on the `tabindex="0"` container (`TimelineChart.vue:434-453`) and assert `DayDetail` renders — never click computed pixels.

Each flow also snapshots the **rendered text** of result/KPI regions (not the DOM) so number formatting is proven unchanged.

### 3.6 Functional Characterization Suite (FCS) — written before, re-run after

The FCS is the user-facing answer to "prove the redesign broke nothing". It is authored in **Phase 0 against the untouched app**, must be green there, is then frozen (its spec files join the G2 byte-identical list: `frontend/e2e/flows/**`, `frontend/e2e/fixtures/**`), and is re-run **unchanged** at every phase gate and in full in Phase 5. Only test ids are added to templates before the specs are written, so no later template change requires a spec change.

| Layer | What it pins | Tooling | Count target |
|---|---|---|---|
| **L1 Unit** | Money parsing/formatting, deal defaults & validation, liquidity engine, the three input primitives' emit contracts, `DealInputsForm` field inventory per deal type | existing Vitest (135 cases; the 4 visual-lock tests rewritten once in Phase 0, §1.4) | 135 → ~135 |
| **L2 Component contracts** (new) | For every existing component: props/emit names, that `disabled` is a native attribute, that emitted payloads are unchanged when the stubbed child emits (`DealCard` delete/duplicate/moveToBought, `BoughtDealCard` substage toggle, liquidity `TransactionForm` save payload discriminant, `SimulationWarning` confirm/cancel, `RepsTimer` finish payload) | Vitest + `@vue/test-utils` (jsdom); a fresh `createPinia()` per test and `vi.mock("../api")` where the component reaches a store (no new testing package) | ~40 |
| **L3 End-to-end functional flows** | The 13 flows of §3.5, each asserting: the recorded network contract (G5), the visible outcome (result numbers, counts, badges, modal open/close, toast copy), every `alert()`/`confirm()` **message text** (captured via `page.on('dialog')` — this also freezes the confirmation copy), the resulting URL/query, and for REPS the localStorage keys written | Playwright against the real backend on a throwaway SQLite DB (§3.5) | 13 flows × 4 browser projects (§3.7) |
| **L4 Static behaviour manifests** | Script-block hashes, binding manifest, frozen-file diff | `scripts/audit/*` (G2–G4) | — |

Rules: (1) FCS specs use only `data-testid`, roles and visible text — never CSS classes; (2) a flow that cannot be made deterministic without credentials asserts the deterministic "not configured" branch instead (REPS log/upload → 503/502, Mercury → `workspace_errors`, send-offer → 500) exactly as `BackEnd/verify_regression.py` does; (3) the Phase 0 run is archived as `frontend/e2e/reports/phase0-baseline.json` and the Phase 5 run must show the identical set of passing test ids; (4) drag-and-drop flows use Playwright `page.dragAndDrop` on the fine-pointer projects only and assert the same-column reorder is **not** persisted (today's behaviour), while touch projects assert the plain-grid branch renders and opens the modal on tap.

### 3.7 Platform support invariant — iOS Safari, Chrome on iPhone, desktop Chrome

Support is a release criterion, not a nice-to-have. Targets: **iOS Safari and Chrome on iPhone** (current and previous major iOS; Chrome on iOS is WebKit, so Safari fixes cover it), **desktop Chrome** (macOS/Windows), Chrome on Android; secondary: desktop Safari, Firefox.

**Rules baked into the design system (Phase 1) and checked per view (Phase 3):**
- Viewport height: replace `h-screen`/`100vh` with `h-dvh`/`min-h-dvh` (Tailwind 3.4 ships `dvh`); the MyDeals/BoughtDeals roots (`h-screen overflow-hidden`) and the landing root are the known offenders. iOS toolbars otherwise clip the board and footer.
- Safe areas: `viewport-fit=cover` is already set, so fixed headers, modal footers and the toast get `padding-*: env(safe-area-inset-*)` via `.safe-*` utilities.
- Inputs: computed font-size ≥ 16 px on every `input/select/textarea` (prevents iOS zoom-on-focus; the current `text-sm` inputs zoom today); keep native `type="date"` pickers; `-webkit-appearance: none` on selects with an explicit chevron; `touch-action: manipulation` on buttons and cards.
- Hover: every hover-only reveal (`group-hover:opacity-100`) is wrapped in `@media (hover: hover)`; on touch the actions render always-visible at full size. Press feedback (`v-press`) uses `pointerdown/up/cancel`, never `mouseenter`.
- Fixed overlays: never transform the `position: fixed` overlay itself (iOS breaks fixed descendants under a transformed ancestor); tween the inner panel only. `backdrop-filter` gets its `-webkit-` twin (autoprefixer) plus a solid fallback colour; it is never animated.
- Motion on iOS: transforms/opacity only; `will-change` only during a tween (GSAP sets/clears it) — never sticky on many elements (iOS memory); no `filter: blur()` tweens; `scrollIntoView({behavior:'smooth'})` is existing behaviour (iOS 15.4+).
- Fonts: Inter self-hosted via `@fontsource-variable/inter` (no third-party request, no FOIT, `font-display: swap`).
- Build targets: `vite.config.ts` gets an explicit `build.target: ['es2020', 'safari15', 'ios15', 'chrome100', 'firefox100']` (Vite 7's default "baseline-widely-available" would drop iOS 15), and `package.json` gets `"browserslist": ["defaults", "iOS >= 15", "Safari >= 15", "Chrome >= 100"]` so autoprefixer emits the `-webkit-` prefixes.
- Modal heights: `max-h-[95vh]` (`MyDeals.vue:652`), `h-[92vh]` (`:1212`), `max-h-[90vh]` (`RepsEntryModal.vue:430`, `TransactionForm.vue:239`) become `svh` units so the panel fits with the iOS toolbar expanded; `overscroll-contain` on the modal scroll containers (`MyDeals.vue:713`, `BoughtDeals.vue:612`) stops scroll chaining (a body scroll lock would be script).
- Blur budget on phones: `backdrop-blur` on full-screen overlays re-blurs every frame while the overlay's opacity animates — tween the **panel**, never the blurred overlay, and use `md:backdrop-blur-sm` (solid scrim on small screens). The landing page's three `filter: blur(80px)` blobs animating forever plus seven `backdrop-filter` cards are a GPU burner on iPhone: the `float` animation is disabled under `(hover: none)`, `(max-width: 900px)` and reduced motion; `.card-inner` gets `isolation: isolate` (Safari mis-clips `backdrop-filter` + `border-radius` + `overflow:hidden` otherwise).
- Safe-area consumers today: none. Known offenders: status dot `fixed top-2 right-2` (`App.vue:53`) under the notch in landscape; toast `fixed bottom-6` (`LiquidityTimeline.vue:540`) over the home indicator; modal `p-4` bottoms. All get the `.safe-*` utilities.
- Never add `maximum-scale=1` to the viewport meta (accessibility; Chrome on iOS ignores it anyway) — zoom-on-focus is fixed by the 16 px rule, not by disabling zoom.
- Native controls keep their native appearance on iOS (`appearance: none` on date inputs hides the value); explicit `min-h` + 16 px instead.
- Support floor: iOS/Safari ≥ 15.4 (`dvh`, `svh`, smooth `scrollIntoView`), Chrome ≥ 100. Stated in `frontend/README.md`.
- Known pre-existing iOS limitations, unchanged: the PDF preview `<iframe>` of a blob renders only the first page on iOS Safari (the Download button remains the mobile path); `BoughtDeals.vue:524` always renders `VueDraggable` (no `pointer: fine` branch, unlike MyDeals), so touch drag there stays whatever SortableJS does today — documented, not "fixed", because the branch condition is script.

**Verification matrix (every phase gate):**
| Project | Engine | Covers |
|---|---|---|
| `chromium` (Desktop Chrome) | Chromium | fine-pointer flows incl. drag-and-drop |
| `webkit` (Desktop Safari) | WebKit | Safari rendering, `dvh`, backdrop |
| `Mobile Safari` = `devices['iPhone 14']` | WebKit, touch, 390×844 | plain-grid board branch, input zoom check (`document.documentElement.clientWidth` unchanged after focus), safe-area padding present, modals scroll inside panel |
| `Mobile Chrome` = `devices['Pixel 7']` | Chromium, touch | Android parity |

Playwright's WebKit is close to, but not identical with, iOS Safari. Therefore each phase gate also ends with a **real-device checklist** (`docs/ui-overhaul/device-checklist.md`, ticked in the phase PR): on an iPhone in Safari **and** Chrome — open all six routes, run the touch flows (open deal modal, edit a money field, autosave chip, Bought substage toggle, liquidity add flow, REPS timer), rotate to landscape (safe areas, no clipped footer), toggle Settings → Accessibility → Reduce Motion and confirm content is immediately visible, check no zoom on input focus; on desktop Chrome — all flows plus keyboard-only navigation. BrowserStack/Sauce real-iOS runs are optional accelerators, not substitutes.

---

## 4. Skill invocation strategy

### 4.1 `ui-ux-pro-max` — when and what
Run the search script by absolute path (no `--persist` until Phase 1 Task 1.1, and never `--force`):

| Moment | Command pattern | Use of the result |
|---|---|---|
| Phase 1 kickoff | `"financial dashboard calculator real estate" --design-system --density 7 --motion 5 --variance 4 -p "BRRRR Deal Analyzer" --persist --output-dir <repo-root>` | Creates `design-system/brrrr-deal-analyzer/MASTER.md`; then **hand-edit** MASTER.md to record the §2 overrides (Inter, indigo primary, light default) — the tool's raw pick (Cinzel/OLED) is documented as rejected |
| Any token/palette question | `"<need>" --domain color` / `--domain typography` / `--domain style` | Verify category + top result fit before applying; retry once narrower; else use §2 defaults and say so |
| Before each primitive (Phase 2) | one outcome query, e.g. `"loading buttons disable spinner" --domain ux`, `"error placement aria-describedby" --domain ux`, `"disabled states opacity" --domain ux` | Becomes the primitive's acceptance checklist |
| Before each view (Phase 3) | page override: `… --design-system --page "<view>" --persist` (creates `pages/<view>.md`), plus view-specific `--domain ux` queries (`"empty states"`, `"sortable table aria-sort"`, `"modal escape routes"`, `"dragging alternative keyboard"`) | Page file lists the view's layout grid, KPI order, and a11y musts |
| Charts (Liquidity) | `"cumulative running balance timeline" --domain chart` | Chart colors/legend/tooltip/a11y-fallback rules for `TimelineChart` |
| Motion presets (Phase 4) | `"<trigger>" --domain gsap` (`hover micro-interaction`, `stagger list`, `page transition`, `loading skeleton`) | Snippets + Do/Don't + reduced-motion note per preset; tiers: **Subtle** for hover/press, **Standard** for reveals/stagger/page, never Complex |
| Final audit (Phase 5) | read `references/quick-reference.md` §1–§3, §7, §8 as the checklist; `pro-rules.md` is mobile-native scoped and is consulted only for the responsive pass | Pre-delivery checklist ticked in the PR |

`--stack vue` has thin data (39 rows on reactivity/composition); consult it only for the `shallowRef`/performance notes when building the motion composables. Do not paste project data into queries.

### 4.2 `gsap-skills` — which skill, when
| Skill | Phase / task | Rules carried into the plan |
|---|---|---|
| `gsap-frameworks` (Vue) | 4.1 motion core | `gsap.context(fn, scopeEl)` in `onMounted`, `ctx.revert()` in `onUnmounted`; register plugins once in `src/motion/gsap.ts`; never global selectors |
| `gsap-core` | 4.1, 4.2 | transforms/opacity only (`autoAlpha` never on modals); a guarded `prefersReducedMotion()` **instead of** `gsap.matchMedia()` (jsdom has no `matchMedia`; jsdom therefore counts as "reduced"); `gsap.defaults({ duration, ease })` from motion tokens; `immediateRender:false` on stacked `from()`; `clearProps: 'transform,opacity,filter'` after every entrance so no residual transform on an ancestor can break a `position: fixed` descendant |
| `gsap-timeline` | 4.3 results reveal, modal open/close | timelines with `defaults`, labels, position params; no `delay` chaining |
| `gsap-performance` | 4.x review | `will-change` only on animating nodes; `quickTo` for hover on card grids; kill loops on unmount; no width/height/top/left tweens |
| `gsap-plugins` (Flip) | consulted, **not adopted** | Flip suits Vue-driven reorders where elements persist; here reorders are either SortableJS (owns the DOM) or full column rebuilds. Layout moves in keyed lists (comps, REPS entries, day detail) use Vue's built-in `<TransitionGroup>` FLIP via `move-class` (CSS transform transition) with GSAP only on enter/leave. Flip is not registered, keeping the bundle small |
| `gsap-scrolltrigger` | consulted, **not adopted** | The landing page does not scroll (`overflow: hidden`); the boards scroll inside inner containers where a mount-time stagger of the five static stage rows is enough; and ScrollTrigger's own resize/refresh listeners would interact with `TimelineChart`'s `ResizeObserver`. GSAP **core only** is registered |
| `gsap-utils` | as needed | `gsap.utils.clamp/mapRange` for KPI delta bars |

---

## 5. Motion architecture (zero-drift mechanisms)

### 5.1 `src/motion/` layout
```
src/motion/
  gsap.ts           // gsap core only (no plugins); gsap.defaults({duration, ease}); motionEnabled()
  tokens.ts         // export const DUR = { fast:.15, base:.25, slow:.4 }, EASE = {...}  (mirrors CSS vars)
  reducedMotion.ts  // prefersReducedMotion(): true when matchMedia is missing (jsdom) or the query matches
  presets.ts        // { page, modal, modalEnterOnly, fade, slideUp, listItem }: each { enter(el, done), leave?(el, done) }
  UiTransition.vue  // global component: <Transition :css="false" appear? @enter @leave @enter-cancelled @leave-cancelled>
                    // around <slot/>; props: preset, appear. A preset without `leave` = enter-only (Vue calls done()
                    // synchronously when no leave hook exists), so no `mode` prop is ever needed
  UiTransitionGroup.vue // same idea for keyed lists; props: preset, tag; move-class "ui-move" (Vue's own FLIP)
  directives.ts     // vReveal (mount entrance; `.stagger` animates [data-reveal] children, WeakSet-tracked so only
                    // newly mounted children animate on `updated`), vPress (pointerdown scale 0.97 → restore),
                    // vHoverLift (@media (hover:hover) only), vFlash (on `updated`, if textContent changed, a 400 ms
                    // background tint tween), vCountUp (optional: tweens parsed old→new textContent and ends on the
                    // exact Vue-rendered string; no-op when either side fails to parse, e.g. "-" or "∞")
  index.ts
```
`main.ts` registers `UiTransition`/`UiTransitionGroup` as global components and the directives with `app.directive(...)` (**allowed** edit: `main.ts` is bootstrap, not logic; its `app.use(...)` lines are untouched). No imports in views, no composables: `<UiTransition preset="modal" appear>` and valueless directives are the entire surface, which is why §3.2 contains no motion pattern.

**Hook contract.** `enter(el, done)`: `gsap.killTweensOf(el)`; if `!motionEnabled()` → `gsap.set(el, { clearProps: 'all' }); done(); return`; else `gsap.fromTo(el, from, { ...to, overwrite: 'auto', clearProps: 'transform,opacity,filter', onComplete: done })`. `leave(el, done)` first sets `el.style.pointerEvents = 'none'` (a fading modal must never accept a second click), then tweens and calls `done`. Cancelled hooks kill tweens and clear props. `clearProps` is mandatory: a residual `transform`/`filter`/`will-change` on an ancestor turns a `position: fixed` descendant into a container-relative box (§3.7).

**Guards.** `motionEnabled()` is `false` when `import.meta.env.VITEST` is set, when `window.matchMedia` is missing, when `prefers-reduced-motion: reduce` matches, or when `window.__BW_MOTION_OFF__` is set (used by the FCS). Module load is side-effect-free apart from `gsap.defaults`. `vite.config.ts` `test.setupFiles` registers `UiTransition`/`UiTransitionGroup` as pass-through stubs and the directives as no-ops via `config.global.components/directives` — a test-config addition, not an edit of any existing test. (Even unregistered, Vue's `withDirectives` skips unresolved directives with a warning, and an unresolved `<UiTransition>` renders as an inert element that none of the existing selectors — `find('button')`, `find('input[type=date]')`, `find('section')` — would match.)

### 5.2 Mechanism → use-case table
| Mechanism | Script change? | Used for |
|---|---|---|
| `<UiTransition preset="modal" appear>` wrapping the existing single root element that carries the `v-if` | none | deal/bought detail modals, Analyze save modal, `PipelineTemplateEditor`, `RepsEntryModal` (enter + leave, ≤ 200 ms, panel opacity+scale, overlay opacity, `pointer-events:none` at leave start) |
| `<UiTransition preset="modalEnterOnly" appear>` | none | PDF preview modal (`closePdfPreview` revokes the blob URL before nulling state — a leave would show a revoked iframe), `SendOfferModal` (its 1500 ms success timeout closes then resets the form synchronously — a leave would flash emptied fields), validation/error banners, save-status chip (wrap the `<template v-if>` fragments in a `<span :key="saveStatus">`; no `mode`) |
| `<UiTransition preset="page" appear>` in the `App.vue` `RouterView` slot (`<RouterView v-slot="{ Component }"><UiTransition preset="page" appear><component :is="Component" /></UiTransition></RouterView>`) | none | enter-only page transition, **opacity only on the view root** (MyDeals opens a `fixed` modal from `?openDeal` right after `fetchDeals`, possibly mid-enter; a transform on the root would reposition the overlay until `clearProps`) |
| `v-reveal` / `v-reveal.stagger` directive | none | section cards, KPI rows, landing feature grid, liquidity sidebar cards, REPS tiles, **board stage rows** (stagger the five rows, never the cards: cross-column drops remount the card vnode and Sortable reads rects on drag start); only newly mounted children animate on later updates, so autosave re-renders do not re-animate |
| `v-press` directive (built into `UiButton`; opt-in on raw elements) | none | scale 0.97 on `pointerdown`, restore on `pointerup/pointercancel/pointerleave`; listeners are `{ passive: true }` and never call `preventDefault`/`stopPropagation`, so `@click.stop` handlers on the same element are unaffected. **Never** on anything inside `<VueDraggable>` (Sortable listens on pointer/mouse down) |
| `v-flash` (default) / `v-count-up` (optional polish) on result/KPI value spans | none | `v-flash`: 400 ms background tint when the displayed value changes, never touches text. `v-count-up`: tweens parsed numbers and ends on the exact Vue string; never on `PortfolioStatsBar` (its frozen script already tweens). The FCS runs with motion off, so neither can race a text assertion |
| `<UiTransitionGroup preset="listItem" tag="div">` around **non-draggable** keyed lists | none | comps lists (sold/rent/sale), `RepsEntriesList`, `DayDetail` rows, `LiquiditySidebar` recurring rules: GSAP enter/leave + Vue FLIP move. Leave hooks call `done()` synchronously under reduced motion. **Never** inside `<VueDraggable>` and never on index-keyed lists (`AnalyzeDeal.vue:158` validation errors) |
| Existing CSS transitions kept and restyled | none | the three Teleported liquidity modals (`name="modal"`, already correct; `Teleport` + `:css="false"` is one more thing to get wrong), the liquidity toast, the chart tooltip `fade`, `PortfolioStatsBar`'s `stats-bar` (its script drives the numbers) |
| SortableJS visual props on `<VueDraggable>` (`ghost-class="ui-drag-ghost"`, `chosen-class="ui-drag-chosen"`; `:animation="150"` unchanged and kept in the G4 manifest) | none (props) | drag ghost polish; G5's drag flow proves `@change`/`@add` still fire identically |

### 5.3 Timing rules that protect behaviour
- **Enter-only page transitions**: `<UiTransition preset="page">` in the `RouterView` slot, opacity only; no leave and no `mode`, so `onMounted` fetches fire at the same moment as today.
- **Mount is never delayed**: no animation gates when an element mounts. Modal panels tween `opacity`/`scale` on the already-mounted panel, so `DealInputsForm` inputs mount and emit at exactly the same tick as today and the 250 ms settle window (`MyDeals.vue:283-284,370`, `BoughtDeals.vue:185-186,230`) is unaffected (no child input emits on mount today: `MoneyInput` commits on blur, `NumberInput`/`SliderField` on `@input`, `ToggleSwitch` on change). Modal enter ≤ 300 ms so it always finishes before the 500 ms debounced analyze + `nextTick` `scrollIntoView` (`MyDeals.vue:392-395`). Modal entrances use `opacity`, **not** `autoAlpha`.
- **Leave transitions never leave stale interactive DOM**: every leave sets `pointer-events: none` on its root first (a second click during the fade must not reach `@click.self="closeModal"`, `MyDeals.vue:649`). Regions whose close path reads or revokes DOM state get **enter-only** presets: the PDF preview (`closePdfPreview` revokes the blob URL first, `MyDeals.vue:482-487`), `SendOfferModal` (form reset right after close, `:50-60`), the REPS property dropdown (150 ms blur timeout, `RepsEntryModal.vue:175-177`, `@mousedown.prevent` options), the results panel (`ref="analysisResultsEl"` is a `scrollIntoView` target — stagger the tiles inside it, never transform the ref'd element itself). Detail modals are safe for leave (`closeModal` awaits `performSave()` **before** toggling and nothing reads the DOM afterwards).
- **Timers respected**: the REPS property dropdown (`RepsEntryModal.vue:176`, 150 ms blur timeout) gets **no** leave animation; the liquidity toast keeps its 4000 ms lifetime (`LiquidityTimeline.vue:361-362`) with a 200 ms enter / 150 ms leave inside it; `SendOfferModal`'s 1500 ms auto-close is untouched.
- **Chart container**: `TimelineChart`'s `ResizeObserver` (`:472`) redraws on any container-size change and `getBoundingClientRect` runs per `pointermove` (`:73`), so the chart wrapper and every ancestor get opacity-only reveal and no size/padding/transform transitions.
- **Sortable is never touched**: no `<UiTransitionGroup>` inside `<VueDraggable>`, no `:key="activeTab"` that would remount it (a new Sortable instance is new behaviour), no `v-press` on its children, and cards themselves are never entrance-animated — only the stage rows are.
- **Autosave paths untouched**: nothing in motion touches `watch(editingDeal, …, { deep: true })`; `v-flash` reads `textContent` and tweens a background tint only (Vue's render always owns the text).
- **Reduced motion**: every preset/directive checks `prefersReducedMotion()`; when true it sets the final state and calls `done()` synchronously; the CSS layer adds a global `@media (prefers-reduced-motion: reduce)` rule that neutralises the remaining CSS animations (blob float, shimmer, `animate-pulse`).
- **Interruptible**: `overwrite: "auto"` on hover/press tweens; state changes set final values explicitly, never depend on `onComplete` for correctness; `ctx.revert()` in every directive's `unmounted`.

---

## 6. Phased milestones

Every task: (a) invoke the skills named, (b) make only the edit kinds listed, (c) run `npm run verify:ui`, (d) commit `Step <phase>.<n>: <what changed>`. Every **phase** ends with `npm run verify:ui -- --phase` (adds backend proofs + 4-browser FCS), the real-device checklist, and a tag `ui-p<N>`. Phase order is fixed; tasks inside a phase may run in the listed order only.

### Phase 0 — Baseline, characterization suite, harness (no visual change)
Goal: freeze today's behaviour in executable form **before** a single class changes.

| # | Task | Files | Edit kind | Proof |
|---|---|---|---|---|
| 0.1 | Branch `refactor/ui-overhaul`, tag `ui-baseline` on `main`; run and archive backend proofs (`cd BackEnd && python3 verify_regression.py verify && python3 -m pytest -q`) | — | git | both green |
| 0.2 | Add `data-testid` to every interactive element and `v-for` root (`<view>.<element>` naming, e.g. `mydeals.tab.market`, `dealcard.delete`, `form.quick-defaults`); add `data-surface="card|panel"` on `DealInputsForm` sections and `data-layout="flat|paired"` on the Rehab/Contingency wrapper | all `views/**`, `components/**` | attributes only | G3 no diff; `npm test` green; `npm run build` green |
| 0.3 | Rewrite the four visual-lock tests (`DealInputsForm.test.ts:389-440`) to assert `data-surface`/`data-layout` + heading copy; switch `:370` to `[data-testid="form.quick-defaults"]`; leave every other test untouched | `DealInputsForm.test.ts` | test | 135 cases green |
| 0.4 | Audit scripts G2–G4/G4b + goldens: `frontend/scripts/audit/{sfc,script-blocks,bindings,text,verify-ui}.mjs`, `golden/{script-blocks,bindings,text}.json`, `allowlist.json` (empty); add `@vue/compiler-sfc` and `diff` devDeps; `npm run audit:baseline`, `npm run verify:ui` | new files, `package.json` | new | `verify:ui` prints PASS for every gate on the untouched tree; three negative tests recorded in the PR: a renamed `@click`, a re-ordered `v-else-if`, and an edited label each make G4/G4b FAIL |
| 0.5 | Vitest additions: `vite.config.ts` `test.setupFiles: ['src/test/setup.ts']` (jsdom-only polyfills for `matchMedia`, `ResizeObserver`, `Element.prototype.scrollIntoView`, `URL.createObjectURL/revokeObjectURL`, `HTMLCanvasElement.prototype.getContext`; `requestAnimationFrame` already exists under Vitest's `pretendToBeVisual`; `UiTransition`/directive stubs registered later in Phase 4.1; `app.use(PrimeVue)` in `global.plugins` wherever a real `InputNumber` mounts); **L2 component-contract tests** (~40) for `DealCard`, `BoughtDealCard`, `SendOfferModal`, `PipelineTemplateEditor`, `TransactionForm`, `SettingsPanel`, `SimulationWarning`, `DayDetail`, `LiquiditySidebar`, `RepsTimer`, `RepsEntriesList`, `RepsPeopleManager`, `PortfolioStatsBar` — emit names/payloads, native `disabled`, dialog copy where `confirm()` is called (`vi.spyOn(window,'confirm')`) | `src/test/setup.ts`, `src/**/*.contract.test.ts`, `vite.config.ts` | new tests | all green against untouched components |
| 0.6 | Playwright FCS (L3): `@playwright/test`, `@axe-core/playwright`; `frontend/playwright.config.ts` with projects `chromium`, `webkit`, `Mobile Safari (iPhone 14)`, `Mobile Chrome (Pixel 7)` — all with `reducedMotion: 'reduce'` — plus `chromium-motion` (`no-preference`, smoke only); `webServer` entries for `e2e/backend/serve_throwaway.py` (imports `verify_regression` for isolation, then serves `main.app` on 8011 — §3.5) and `vite preview --port 5173 --strictPort`; `e2e/fixtures/recorder.ts` (request log → `{method,path,sortedQuery,body}` with `VOLATILE_KEYS` redaction, multipart → field names + file count, PDF → status + content-type; `page.on('dialog')` capture + auto-accept with message assertions; `page.clock.install` per test); the 16 flows in `e2e/flows/*.spec.ts`; goldens in `e2e/golden/`; axe baseline in `e2e/golden/axe-baseline.json`; `npm run e2e`, `npm run e2e:record` | new files, `package.json` scripts | new | all flows green on 4 projects; archived `e2e/reports/phase0-baseline.json` |
| 0.7 | Inert cleanup + platform config: delete `src/style.css`, `components/HelloWorld.vue`, `assets/vue.svg` (zero importers); add `browserslist` to `package.json` and explicit `build.target` in `vite.config.ts` (§3.7); `frontend/README.md` gains the "How to verify" section | listed | delete/config/docs | `npm run build` green; bundle output diff limited to target-related syntax; gates green |
| 0.8 | Real-device baseline pass on an iPhone (Safari + Chrome) and desktop Chrome using `docs/ui-overhaul/device-checklist.md`; record pre-existing defects (input zoom on focus, clipped board under iOS toolbar, hover-only actions unreachable) as "baseline" so later phases can show them fixed | docs | docs | checklist committed |

**Exit criteria:** gates 7×PASS with goldens equal to the untouched tree; FCS archived; no visual change (Playwright screenshots of all routes byte-identical to `ui-baseline` except the deleted dead files).

### Phase 1 — Design tokens and base layer
Goal: one source of truth for colour, type, space, elevation and motion timing; the app should look *almost* the same afterwards (Inter loads, focus rings appear, inputs reach 16 px).

| # | Task | Files | Edit kind | Skills | Proof |
|---|---|---|---|---|---|
| 1.1 | Generate and persist the design system: `search.py "financial dashboard calculator real estate" --design-system --density 7 --motion 5 --variance 4 -p "BRRRR Deal Analyzer" --persist --output-dir <repo-root>`; hand-edit `design-system/brrrr-deal-analyzer/MASTER.md` to the §2 decisions (Inter, indigo primary, light default, rejected Cinzel/OLED noted); run the `--domain color/typography/style` queries of §2 and paste verified results into MASTER.md | `design-system/**` | new docs | `ui-ux-pro-max` | file reviewed in PR |
| 1.2 | Tokens: `src/assets/tokens.css` (`:root` light, `.dark` dark; colour as `R G B` triplets, spacing, radius, shadow, `--dur-*`, `--ease-*`, `--stats-bar-h`); `src/assets/main.css` imports it and adds base styles (body tokens, `:focus-visible` ring, `button { cursor:pointer; touch-action:manipulation }`, ≥16 px form controls, `.tabular`, `.safe-*` utilities, `.custom-scrollbar` definition, `-webkit-tap-highlight-color`, `@media (prefers-reduced-motion: reduce)` neutraliser for CSS animations); `tailwind.config.js`: `theme.extend` (semantic colours as `rgb(var(--color-x) / <alpha-value>)`, `borderRadius`, `boxShadow`, `fontFamily`, `transitionDuration`, `transitionTimingFunction`, `keyframes` for shimmer/float, `spacing['safe-b']`, `screens` unchanged), `future.hoverOnlyWhenSupported: true` (every `hover:` utility becomes `@media (hover:hover)` — fixes sticky hover on touch app-wide), and an `addVariant('touch', '@media (hover: none)')` plugin for always-visible touch affordances | `src/assets/*.css`, `tailwind.config.js` | new/config | `ui-ux-pro-max` (`"dark mode contrast semantic tokens" --domain ux`), `design-system` skill for token layering | gates; contrast script `scripts/audit/contrast.mjs` reports every fg/bg token pair ≥ 4.5:1 |
| 1.3 | Fonts & document: `@fontsource-variable/inter` import in `main.ts` (before `main.css`); `index.html` title "Big Whales Deal Analyzer", `<meta name="theme-color">`, keep `viewport-fit=cover` | `main.ts`, `index.html` | bootstrap | — | Inter visible; no FOIT (Lighthouse) |
| 1.4 | `src/design/cn.ts` (`clsx` + `twMerge`, both already installed); `src/design/primevue-pt.ts` global pass-through for `InputNumber`, `Slider`, `ToggleSwitch` built from tokens; wire `app.use(PrimeVue, { unstyled: true, pt: primevuePt, ptOptions: { mergeSections: true, mergeProps: true } })` in `main.ts`; the local `:pt` in `SliderField.vue:85-93` and `DealInputsForm.vue:267-271` migrate into the global preset (template-only removal; `pt` is ignored by G4) | new, `main.ts`, 2 templates | new/template | `ui-ux-pro-max` (`"slider handle touch target" --domain ux`) | 135 tests green (stubs unaffected); slider handle 24 px+ |
| 1.5 | `src/design/chartTokens.ts` — `chartToken(name)` resolves `--chart-<name>` once per page from `getComputedStyle(document.documentElement)` (chart tokens are **resolved colour strings** like `--chart-bg: #0f1117`, not channel triplets, because canvas needs complete colours) and falls back to a map holding **today's exact 17 hex/rgba literals** | new | new | — | unit tests: returns the literal fallback without a DOM; every fallback equals the literal at the cited `TimelineChart.vue` line |
| 1.6 | `src/motion/tokens.ts` mirrors `--dur-*`/`--ease-*` (no GSAP import yet) | new | new | `gsap-core` (ease names) | unit test: values match `tokens.css` (parsed by the test) |

**Exit criteria:** gates green; screenshots differ from Phase 0 only in font, focus rings, control sizes; device checklist shows input zoom fixed on iPhone.

### Phase 2 — Shared presentational primitives (`src/components/ui/`)
Goal: every visual pattern that is repeated ≥ 3 times becomes one component; nothing in views changes yet.

| # | Primitive | Contract | Proof |
|---|---|---|---|
| 2.0 | **Rule: no `UiInput` / `UiSelect` / `UiTextarea`** | Native `v-model` on `type="number"` casts to number (`MyDeals.vue:1024,1090,1133`), `v-model.number` (`SendOfferModal.vue:108`) and `<select>`s with numeric `:value` options (`AnalyzeDeal.vue:282-303`, `MyDeals.vue:742-768`) rely on Vue's native model directives; a wrapper component would change payload types silently. Natives are restyled with `.ui-input`/`.ui-select`/`.ui-textarea` component classes from `main.css`; G4 flags any tag change | G4 tag rule |
| 2.1 | `UiButton` | root `<button :type="type ?? 'button'">`; `variant: primary|secondary|ghost|danger|brrrr|flip`, `size: sm|md|lg`, `loading` (visual spinner; **does not** set `disabled` — parents keep passing `:disabled`), `block`; `$attrs` fall through (so `@click.stop`, `:disabled`, `title`, `data-testid` land on the button); built-in `v-press`; 44 px min height on `md`, 24 px min on `sm` | contract tests: click forwarded, `.stop` respected, `disabled` native, no `type=submit` |
| 2.2 | `UiIconButton` | as `UiButton` but square; **requires** `aria-label` (dev-time `console.warn` if missing); 32 px visual / 44 px hit area via `::before` | test warns without label |
| 2.3 | `UiCard` | `tone: surface|muted|elevated`, `interactive` (adds hover-lift under `(hover:hover)` and `v-press`), `padding` | snapshot per tone |
| 2.4 | `UiBadge` | `tone`, `dealType: BRRRR|FLIP` variant with `pi-home`/`pi-dollar` icon (replaces the emoji), `size` | text content = label only |
| 2.5 | `UiStatTile` | `label`, `value` (slot, tabular), `tone: positive|negative|neutral` **with** a sign/icon so meaning is not colour-only, `hint` | snapshot; `v-flash` applied to value |
| 2.6 | `UiField` | `label`, `helper`, `error`, `required`; generates `id` via `useId()` and exposes it to the default slot (`#default="{ id, describedBy }"`); the control is passed **by the parent** so existing `v-model`/`@update:` bindings never move | test: `aria-describedby` wiring |
| 2.7 | `UiModalPanel` | panel only (`role="dialog"`, `aria-modal`, `aria-labelledby` via `useId`, header/body/footer slots, scroll-inside body with `overscroll-contain`, safe-area footer padding). The overlay `div` with `@click.self` stays in the parent | test: no listeners on root |
| 2.8 | `UiSectionHeader`, `UiEmptyState`, `UiSkeleton`, `UiSaveStatus` (`status: idle|saving|saved|error` → chip), `UiTabs` (visual segmented control; parent owns `@click`), `UiStepper` (steps + activeIndex; responsive labels: `truncate` + `title`, wraps to two rows under `md`) | props-only | snapshots |
| 2.9 | `docs/ui-overhaul/primitives.md` — usage, do/don't, the `ui-ux-pro-max` acceptance queries used per primitive (`"loading buttons disable spinner"`, `"error placement aria-describedby"`, `"disabled states opacity"`, `"modal escape routes"`, `"empty states"`, `"touch target size"`) | docs | — |

**Exit criteria:** gates green (views untouched); every primitive has a jsdom test file; `docs/ui-overhaul/primitives.md` committed.

### Phase 3 — Views and workflows (restyle in place)
Goal: apply the system to every screen, one unit per task, lowest-risk first. For each task: run `search.py "<view>" --design-system --page "<view>" --persist` (page override), the view-specific `--domain ux` queries listed, then edit **templates/styles only** under §3.3, then gates + the view's device checklist rows.

| # | Unit | What changes (template/CSS only) | UX queries | Hazards to respect |
|---|---|---|---|---|
| 3.1 | `App.vue` template, `PortfolioStatsBar.vue` template+CSS | Root becomes `flex min-h-dvh flex-col`; stats bar `flex-none`; `RouterView` container `flex-1 min-h-0` (removes the landing `.has-bar` 60 px hack); connection dot → `role="status" aria-live="polite"` pill with visually-hidden text; stats bar CSS onto tokens (keep `<Transition name="stats-bar">` and the rAF script) | `"live status region announce" --domain ux` | script frozen |
| 3.2 | `LandingPage.vue` scoped CSS | Rewrite the 494 lines onto tokens; keep the card DOM and `component :is`; `h-dvh`; safe-area padding; blobs paused under reduced motion; hover choreography under `(hover:hover)`; resource pills 44 px | `"landing grid cards hover" --domain ux`, `"reduced motion"` | none |
| 3.3 | `AnalyzeDeal.vue` | Header, `UiTabs`-styled type switcher (buttons keep their `@click`), CTA → `UiButton variant=brrrr/flip`, validation list, save modal → overlay div (unchanged, keeps `@click.self`) + `UiModalPanel` + `UiField`s; `<select>` styled via `.ui-select` | `"inline validation error near field"`, `"modal escape routes"` | none |
| 3.4 | `DealInputsForm.vue`, `ui/MoneyInput.vue`, `NumberInput.vue`, `SliderField.vue`, `DaysUntilRefiField.vue` | Six class computeds emit token classes (`data-surface`/`data-layout` retained); `MoneyInput`/`DaysUntilRefiField` wrap their native inputs inside the `<label>` (implicit association; label text unchanged); `NumberInput`/`SliderField`/`ToggleSwitch` get `for`/`inputId` via `useId()` (§3.2 item 3); 16 px inputs; Quick Defaults stays the first button | `"form labels visible"`, `"number formatting tabular"`, `"slider keyboard"` | 135 tests must stay green untouched (0.3 rewrite aside) |
| 3.5 | `DealCard.vue`, `BoughtDealCard.vue` | Action buttons become a flex row at the top-right (no magic `right-*` offsets; `deal.stage === 3` `v-if` unchanged); visible on touch via the `touch:opacity-100` variant (hover reveal only under `(hover: hover)` thanks to `hoverOnlyWhenSupported`); `UiIconButton` with `aria-label`; `UiBadge dealType`; progress bar tokens; card → `UiCard interactive` (keeps `cursor-grab`) | `"touch target size"`, `"hover vs tap"` | `@click.stop` handlers unchanged; SortableJS drags the card root — root stays a plain element with the same classes hierarchy |
| 3.6 | `MyDeals.vue` | Header/tabs/board rows (both the `VueDraggable` and the plain-grid branches, identically); empty-column `UiEmptyState` as a **sibling** of the draggable list (new presentational `v-if` reading `columns[stage.id]?.length` — logged in the golden update); detail modal body → `UiCard`/`UiSectionHeader`/`UiField` wrappers around the existing inputs; results → `UiStatTile`; comps lists → styled rows; footer → `UiSaveStatus` + `UiButton`s; PDF modal; `h-dvh` root; modal `max-h` in `svh` + `overscroll-contain` on `modalScrollContainer`; results tiles keep `:class="getCashFlowColor(...)"` as a fallthrough class (never converted to a prop) | `"empty states"`, `"sortable board keyboard alternative"`, `"modal focus trap"` | settle window; `scrollIntoView` target keeps layout at mount; no wrappers inside `VueDraggable` |
| 3.7 | `BoughtDeals.vue` | As 3.6 plus `UiStepper` for the pipeline (labels readable at 6+ stages), substage checklist (`<input type=checkbox>` + `@change` unchanged), "Advance" → `UiButton` | `"multi-step progress indicator"`, `"checklist accessible"` | same as 3.6 |
| 3.8 | `PipelineTemplateEditor.vue` | 15 icon-only buttons → `UiIconButton` with labels, 32/44 px; drag handle 44 px; banners; `custom-scrollbar` now defined | `"icon button accessible label" --domain icons` | `handle=".stage-drag-handle"` class kept |
| 3.9 | `LiquidityTimeline.vue` + 6 liquidity components | Hex → tokens (light theme per §2.4; the alternative is `class="dark"` on the view root); repeated input class → `.ui-input`; sidebar cards → `UiCard`; sidebar shown below the chart under `lg` (CSS order, no toggle); modals keep `Teleport` + `<Transition name="modal">` permanently (restyled; the fragile `.modal-enter-from .relative` rule is replaced by a dedicated class); `TimelineChart` gets E1 (`chartToken`, with a Playwright check that every `--chart-*` resolves non-empty on `/liquidity`); `[color-scheme:dark]` removed with the light theme | `"cumulative running balance timeline" --domain chart`, `"chart keyboard focus"` | `ResizeObserver` → no size transitions on the chart wrapper; `outline-none` on the `tabindex=0` container replaced by a visible focus ring |
| 3.10 | `RepsTracker.vue` + 5 REPS components | Cards → `UiCard`; user tabs → `UiTabs` styling with `overflow-x-auto`; filters get labels (visually-hidden where space is tight); discard button gets `aria-label`; stats → `UiStatTile`; entry modal → `UiModalPanel` + `UiField`s; property dropdown gets `role="listbox"`/`option` semantics without changing its `@mousedown.prevent` handler | `"combobox accessible"`, `"file upload feedback"` | 150 ms blur timeout — no leave animation on the dropdown (Phase 4) |
| 3.11 | `SendOfferModal.vue` | `UiModalPanel` + `UiField`s; message banner tones | `"submit feedback success error"` | 1500 ms auto-close untouched |

**Exit criteria (per task and phase):** gates green; FCS green on 4 projects; axe violations ≤ baseline for the routes touched; device checklist rows for the unit ticked (iPhone Safari + Chrome, desktop Chrome); screenshots reviewed at 390 / 768 / 1024 / 1440.

### Phase 4 — Motion with GSAP
Goal: production-grade micro-interactions and transitions, attached only through the §5 mechanisms.

| # | Task | Files | Skills | Proof |
|---|---|---|---|---|
| 4.1 | Install `gsap` (pin exact 3.13.x, core only); `src/motion/{gsap,tokens,reducedMotion,presets,directives,index}.ts`, `UiTransition.vue`, `UiTransitionGroup.vue`; register the two components and the directives in `main.ts`; add their stubs to `src/test/setup.ts`; `src/components.d.ts` for `GlobalComponents` typing; unit tests: every preset calls `done()` synchronously when `!motionEnabled()`, every `leave` sets `pointer-events:none` first, the `page` preset touches opacity only, directives never call `preventDefault`/`stopPropagation`, `clearProps` runs on complete and on cancel | new, `main.ts`, `src/test/setup.ts` | `gsap-frameworks`, `gsap-core` | tests green; existing suites unchanged |
| 4.2 | Page and section reveals: `App.vue` `RouterView` slot → `<UiTransition preset="page" appear><component :is="Component" /></UiTransition>` (the one approved structural delta); `v-reveal.stagger` on the board **stage-row** containers (both branches; rows only, never cards), KPI rows, landing feature grid, liquidity sidebar cards, REPS stat tiles (Standard tier: 300–450 ms, `back.out(1.4)`, `each: 0.06`) | `App.vue` + templates (attrs) | `gsap-core`, `ui-ux-pro-max --domain gsap "stagger list"` | G3 no diff; FCS green; flow 15 overlay-rect check |
| 4.3 | Modals: `<UiTransition preset="modal" appear>` around the existing overlay root in `AnalyzeDeal` (save modal; drop its scoped `fade-in-up` keyframe), `MyDeals` detail, `BoughtDeals` detail, `PipelineTemplateEditor`, `RepsEntryModal`; `<UiTransition preset="modalEnterOnly" appear>` for the PDF preview and `SendOfferModal`. Panel tweens `opacity`+`scale`, overlay opacity only (never transform the fixed overlay; never `autoAlpha`; never animate `backdrop-blur`). Liquidity Teleported modals and toast keep their CSS transitions | 7 templates, zero imports | `gsap-timeline`, `--domain gsap "page transition"` | flows 5, 8, 14 record exactly one PUT; axe `modal-escape` |
| 4.4 | Feedback: `v-flash` on every `UiStatTile` value and the modal results; `UiSaveStatus` keyed-`<span>` enter-only fade; validation/error banner enter-only; copied-icon crossfade (CSS); optional `v-count-up` on result tiles only after the motion-on smoke project proves it ends on the exact Vue string | primitives + templates | `gsap-core`, `gsap-utils` | `v-flash` never mutates text (test); count-up parse no-ops on `-`/`∞` (test) |
| 4.5 | Lists: `<UiTransitionGroup preset="listItem" tag="div">` on comps lists (MyDeals/BoughtDeals), `RepsEntriesList`, `DayDetail`, `LiquiditySidebar` recurring rules — never inside `VueDraggable`, never on index-keyed lists | templates | `gsap-core` | duplicate/delete flows green; leave `done()` under reduced motion |
| 4.6 | Drag polish: `ghost-class="ui-drag-ghost"`, `chosen-class="ui-drag-chosen"` (token classes; `:animation="150"` unchanged); `UiCard interactive` hover-lift is disabled on cards rendered inside `VueDraggable` (no `v-press`, no pointer listeners there) | `MyDeals`, `BoughtDeals`, `PipelineTemplateEditor` | `gsap-performance` | drag flow green on `chromium`; touch projects unaffected |
| 4.7 | Performance and reduced-motion pass: `gsap-performance` checklist (transform/opacity only, `will-change` only during tweens, no loops left running after unmount — asserted by `gsap.globalTimeline.getChildren().length === 0` after navigating away in a Playwright test), Chrome DevTools recording of modal open and board scroll, iPhone visual check | — | `gsap-performance`, `gsap-utils` | G7 green; recordings attached to the PR |

**Exit criteria:** G7 reduced-motion run shows no live tweens and immediate content; FCS green on 4 projects; device checklist (Reduce Motion on iOS honoured; 60 fps board scroll on iPhone).

### Phase 5 — Regression sweep, accessibility, documentation
| # | Task | Proof |
|---|---|---|
| 5.1 | Full FCS (L1–L4) on all 4 projects + backend proofs; diff `e2e/reports/phase5-final.json` against `phase0-baseline.json`: identical passing set, zero skipped | report committed |
| 5.2 | Accessibility: axe on all routes (zero new, target fewer than baseline); keyboard-only walkthrough per view (tab order, focus visible, Escape closes modals where it did before — no new key handlers); token contrast script | checklist in PR |
| 5.3 | Platform sweep: screenshots at 390 / 768 / 1024 / 1440 (informational); real-device checklist on iPhone Safari **and** Chrome, desktop Chrome (§3.7) with the Phase 0 baseline defects now marked fixed | checklist committed |
| 5.4 | Performance: bundle delta (`vite build --report`; GSAP core + ScrollTrigger ≈ 35 KB gz budget), Lighthouse mobile on `/` and `/my-deals` (CLS < 0.1, no font FOIT) | numbers in PR |
| 5.5 | Docs: `frontend/README.md` (design system, tokens, primitives, motion rules, `verify:ui`, device checklist); `docs/ui-overhaul/decisions.md` (the §2.4 decisions + golden-update log); root `README.md` frontend section refreshed; `REPS_README.md:182-184` card description updated. **Not** the `DealInputsForm.vue` header comment (it lives in the frozen script block) | docs |
| 5.6 | **Portable-path sweep (user-added 2026-09-04):** `git grep` the tracked tree for absolute filesystem paths (user-home, Windows-drive and system-temp path prefixes — the exact patterns live in `frontend/scripts/audit/paths.mjs`); convert every code/config/doc occurrence to a repo-relative or runtime-derived path (`import.meta.url`, `__dirname`, `__file__`, `process.cwd()`); doc examples (e.g. the `REPS_README.md` credentials path) become placeholders; add `frontend/e2e/scripts/normalize-report.mjs` that rewrites `configFile`/`rootDir`/`testDir`/`outputDir`/`file` in Playwright JSON reports to repo-relative paths and re-archive `phase0-baseline.json` and `phase5-final.json` through it (the 5.1 comparison uses test ids/status only, so it is unaffected); add `scripts/audit/paths.mjs` to `verify:ui` (gate **G8**: FAIL on any absolute path in tracked files, excluding lockfiles and `node_modules`) | `npm run verify:ui` prints PASS G8; `git grep` for the patterns is empty; the e2e suite and all unit tests still green |
| 5.7 | Final PR `refactor/ui-overhaul → main` with the gate output, the golden-update log, both FCS reports, and the device checklists | merged |

---

## 7. Risk register (top 10) and the gate that catches each

| # | Silent-drift risk | Caught by | Gap / mitigation |
|---|---|---|---|
| 1 | A modal entrance delays input mount past the 250 ms settle window → spurious `PUT` on open | G5 `my-deals-autosave`/`bought-deals-autosave` flows count exactly one PUT | none — flows assert call count |
| 2 | `mode="out-in"` or leave transitions delay `onMounted` fetches / `router.replace` | G4 forbids `mode`; G5 `landing` and deep-link flow assert call order | none |
| 3 | Wrapper inserted inside `<VueDraggable>` breaks SortableJS DOM sync (cards vanish after drag) | G5 drag flow on `chromium`; §3.3 forbids | touch projects use the plain grid — covered separately |
| 4 | Handler moved/renamed while restyling a 1200-line template | G4 manifest (expression + anchor) | new presentational `v-if`s are additions and must appear in the golden-update log |
| 5 | `disabled` turned into `aria-disabled` or a `<div>` button | L1 `DaysUntilRefiField` test, L2 contract tests, G4 `bind:disabled` | none |
| 6 | `UiButton` swallowing `.stop`/`.self` modifiers or changing `type` | L2 contract tests; overlays keep raw `div` | none |
| 7 | Copy changes (badge text, dialog messages, headings) that users/flows depend on | L3 dialog capture + text snapshots; heading tests in `DealInputsForm.test.ts` | intentional copy changes (emoji removal) are logged in the golden update |
| 8 | Canvas colours changed beyond E1, or silently wrong because a `--chart-*` variable is unresolved (canvas ignores an invalid `fillStyle`) | G3 E1 line-diff rule; `chartToken` hex fallbacks equal to today's literals; Playwright check that every `--chart-*` resolves non-empty on `/liquidity` | none after the check is added (jsdom has no custom-property cascade, so only Playwright can prove it) |
| 9 | iOS regressions (100vh clipping, zoom on focus, fixed+transform, hover-only actions, backdrop-blur jank) | §3.7 Mobile Safari project + real-device checklist | Playwright WebKit ≠ Safari → real device mandatory per phase |
| 10 | A script edit sneaks in via `main.ts` or `vite.config.ts` (not covered by G3) | G1/G2 diff review: both files are diffed in every PR with the allowed lines enumerated (`app.component`, `app.directive`, `pt:`/`ptOptions:`, font import, `test.setupFiles`, `build.target`) | `verify-ui.mjs` prints both diffs for the reviewer |
| 11 | A leave animation leaves stale interactive DOM (second click on a fading overlay reaches `closeModal`; a revoked PDF blob shown; `SendOfferModal` fields flash empty; REPS dropdown stays clickable) | flow 14 (`modal-double-close`) + preset unit test that every `leave` sets `pointer-events:none` first; enter-only table in §5.2 enforced by review checklist | none after flow 14 |
| 12 | A transform/filter left on an ancestor of a `position: fixed` element (page reveal while `?openDeal` opens the modal) | flow 15 overlay-rect check at 50 ms and 500 ms; `page` preset is opacity-only by construction (unit test); `clearProps` on complete/cancel (unit test) | none |
| 13 | Goldens regenerated from the restyled tree to make a gate pass | `verify-ui.mjs` asserts `git diff --quiet ui-baseline -- frontend/scripts/audit/golden frontend/e2e/golden` outside `Golden update:` commits; regeneration only from a `git worktree` of the baseline tag (§8) | process |
| 14 | GSAP leaves tweens running after route change | G7 live-tween assertion after navigation | none |
| 15 | Backend accidentally edited while running the E2E backend | G1 + `verify_regression.py verify` | none |

---

## 8. Branching, rollback and execution handoff

- **Branch:** integration branch `refactor/ui-overhaul` off `main@c1e1ad1`; phase branches `ui/phase-0-harness`, `ui/phase-1-tokens`, `ui/phase-2-primitives`, `ui/phase-3.1-app` … `ui/phase-3.11-send-offer`, `ui/phase-4-motion`, `ui/phase-5-sweep`, each merged `--no-ff` into the integration branch and tagged (`ui-baseline`, `ui-p0`, `ui-p1`, `ui-p2`, `ui-p3.x`, `ui-p4`, `ui-p5`). Phase 0 alone (harness only, no visual change) may merge to `main` early so the FCS protects unrelated work too.
- **Revert reality:** leaves revert cleanly — any Phase 3.x view PR and Phase 4 come out with `git revert -m 1 <merge>`. Phases 1–2 are foundations: reverting them means reverting everything after (LIFO). Order constraints inside Phase 3: 3.1 (App flex shell / `dvh`) before 3.2 (landing height hack), 3.6 before 3.7 (Bought is a fork of My Deals — keep the class strings identical).
- **Golden updates:** goldens (`scripts/audit/golden/*`, `e2e/golden/*`, `allowlist.json`) change only in commits titled `Golden update: <reason>` containing nothing else, reviewed line-by-line. A wrong golden is regenerated **only** from a worktree of the baseline (`git worktree add ../bw-baseline ui-baseline`, baseline code + the throwaway backend), never from the restyled tree; the tag then moves to `ui-baseline-2`. §7 rows 4/7 additions are listed in `docs/ui-overhaul/decisions.md`.
- **Frozen after Phase 0:** `frontend/e2e/flows/**`, `frontend/e2e/fixtures/**` join G2 so the FCS itself cannot drift.
- **Rollback of the whole overhaul:** `git revert` the final merge, or redeploy `ui-baseline`; no data migration is involved because the backend never changes.
- **Execution:** run with `superpowers:subagent-driven-development` (one subagent per task, gates run by the subagent, reviewer checks the gate output and the device-checklist rows) or `superpowers:executing-plans` for inline execution. Skills per task are named in the tables above; `superpowers:verification-before-completion` applies to every "Proof" column before a task is called done.

---

## 9. Execution amendments (rulings made during execution — see the SDD ledger for reasons)

| Date | Amendment |
|---|---|
| 2026-09-04 | Task 5.6 added (user request): portable-path sweep + gate G8; final PR renumbered 5.7. Global Constraint "Portable paths" added. |
| 2026-09-04 | Task 0.4: the G4 binding manifest also records the static `to` attribute (Teleport target). Bare `v-else` entries can never be allowlisted; a new multi-branch presentational chain needs a deliberate widening. |
| 2026-09-04 | Task 0.6: the axe baseline is **rule-keyed per route** `{ruleId: {impact, count}}`, not target-selector-keyed; the recorder captures requests in-page (XHR/fetch wrap) because WebKit coalesces identical concurrent GETs. |
| 2026-09-04 | Task 1.2: token radii are exposed as `rounded-ctl` (6px) / `rounded-card` (10px) / `rounded-panel` (16px); Tailwind's `rounded-sm/md/lg` defaults stay. A mobile-only `!important` 16 px rule on `input/select/textarea` guarantees the iOS zoom fix. |
| 2026-09-04 | `future.hoverOnlyWhenSupported` is **not** enabled in Phase 1 (it would hide 14 hover-revealed controls on touch). It is enabled as the final step of Phase 3 (Task 3.11) once every `group-hover:opacity-100` has a `touch:opacity-100` sibling. |
| 2026-09-04 | Phase 2 pre-flight: the G4 comparator gains presentational tag aliases (`UiCard`, `UiStatTile`, … may replace `div/section/span/p/h*/li/…`; native tags never alias); `UiTabs`/`UiStepper` are containers around the views' existing `v-for` elements (never data-driven props); primitives receive all user-visible copy via slots. |
| 2026-09-04 | Task 3.0 added: the Ui* primitives are globally registered (`registerUiPrimitives(app)` in `main.ts`, `GlobalComponents` typing, and `config.global.components` in the Vitest setup) because view `<script>` blocks cannot gain import lines under G3. |
| 2026-09-04 | Phase 3 pre-flight: the G4 collector ignores presentational props (`variant`, `size`, `active`, `tone`, `status`, `loading`, …) with side-effect-free expressions on Ui* elements, and `v-slot` on `<template>`/Ui* elements; behavioural props (`disabled`, `type`, `href`, `value`, `is`, `to`, events, `v-model`, `v-for`, `v-if` chains) stay recorded everywhere. Implemented and tested in Task 3.0. |
| 2026-09-05 | Task 3.0 review: `as` (renders `:is`) is always recorded by G4; justified `as` usage takes an allowlist row. `++`/`--`/backticks count as side effects. Template slots are ignored only when the template's parent is a Ui* element. |
| 2026-09-05 | Task 4.1: `clearProps` is `transform,opacity,filter,willChange` on every path (never `all` — it wipes app inline styles); a cancelled leave resets `pointer-events`; `src/motion/gsap.ts` exposes `window.gsap` so the frozen e2e no-live-tweens guard is real; GSAP pinned 3.15.0. |
| 2026-09-05 | User decision (Plan B): Tasks 4.4–4.6 skipped (v2 will re-apply motion in redesigned templates); 4.7 reduced to a perf/no-live-tweens check; Phase 5 reduced to 5.1, 5.6, one quality snapshot (5.2–5.4 measure-only), 5.5-lite docs, 5.7 final review; reviews at phase gates only; execution stops after the final review — the user merges and starts UI v2 on a new branch. |
