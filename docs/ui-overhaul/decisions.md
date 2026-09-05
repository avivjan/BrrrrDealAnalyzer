# UI overhaul v1 — decisions

Every decision that shaped the visual overhaul on `refactor/ui-overhaul`, and
every one it deliberately postponed. Two audiences: someone changing the UI now,
who needs to know why a rule exists before working around it; and whoever plans
**UI v2**, who needs the list of things v1 chose not to do.

The plan is `docs/superpowers/plans/2026-09-04-ui-ux-overhaul-master-plan.md`
(§2.4 decisions, §3 gates, §5 motion, §9 execution amendments). The reasoning
behind each ruling, dated and in order, is
`.superpowers/sdd/2026-09-04-ui-ux-overhaul-master-plan/progress.md`.

Paths are repo-relative except `src/`, `e2e/` and `scripts/`, which are relative
to `frontend/`.

---

## 1. The one invariant

**Nothing the app does changed.** Not a request, not a payload, not an order of
calls, not a string on screen. Every visual change had to survive a gate set that
compares the working tree against `ui-baseline` — the script block of every
`.vue` file, the ordered list of every behavioural template binding, every
on-screen copy string, the HTTP contract of every flow, and the axe violation
counts per route. `frontend/README.md` lists the eleven gates and what each
proves.

That invariant is the reason for most of what follows. A rule that looks like
fussiness — copy frozen, `as` recorded, a hidden parking element in a template —
is almost always the cheapest way to keep a mechanical proof honest.

---

## 2. Design decisions (plan §2.4)

| # | Decision | Why, and what it would cost to reverse |
| --- | --- | --- |
| D1 | **Light theme app-wide. Dark tokens are complete; no toggle ships.** The Liquidity island, which was dark, was migrated onto the tokens and rendered light. | One visual language across the app. Every `--color-*` has a `.dark` value that passed the contrast audit, so a toggle is additive work, not a retrofit. Keeping Liquidity dark instead is still a one-line change: `class="dark"` on its view root. |
| D2 | **PrimeVue stays unstyled.** Styling arrives through one global pass-through preset, `src/design/primevue-pt.ts`. No theme preset; no new PrimeVue component. | A theme preset or a new component changes the DOM the frozen tests select on. The preset moved the slider's and switch's colours off `blue-500`/`gray-400` and onto tokens, grew the slider handle 20 → 24 px for WCAG 2.5.8, and moved its ring from `focus:` to `focus-visible:`. |
| D3 | **Icons stay `primeicons`.** | Already loaded, consistent stroke; the design-system search returned no match worth a new dependency. |
| D4 | **Playwright is a dev dependency**, used to record the network-contract goldens. It never runs in the Netlify build. | The behaviour proof needs a real browser against the real backend. |
| D5 | **Commit convention `Step N: <what>`**, one integration branch with phase tags `ui-baseline`, `ui-p0`…`ui-p4`. | Matches the house style; the tags are what the gates diff against. |
| D6 | **The generated "Enterprise Gateway" design system was rejected** — a marketing pattern with a luxury serif, mis-fit for a numeric tool. The targeted domain queries (Financial Dashboard: data-dense + Swiss, trust blue / profit green / red alerts) are the source of truth in `design-system/brrrr-deal-analyzer/MASTER.md`. | v2 explicitly revisits this and embraces the bolder direction. |

### Token shapes that are decisions, not defaults

- **Colours are RGB triplets, not colour strings** (`--color-fg: 15 23 42`), so
  Tailwind can wrap them as `rgb(var(--color-fg) / <alpha-value>)` and alpha
  modifiers keep working. `--chart-*` are the exception — a `<canvas>` needs a
  resolved string and silently ignores an invalid one.
- **New radius keys, not overridden defaults.** `rounded-ctl` / `rounded-card` /
  `rounded-panel` were added and Tailwind's `rounded-sm/md/lg` left alone. The
  first attempt mapped the token radii onto the defaults and changed 148 existing
  corners from 8 px to 16 px in one commit — a restyle nobody asked for. Cost:
  the semantic keys have to be adopted deliberately, view by view.
- **`cn` extends `tailwind-merge` with the custom scales** (`borderRadius`,
  `boxShadow`, `transitionDuration`, `transitionTimingFunction`). Stock
  `twMerge` does not know `rounded-card` conflicts with `rounded-panel`, so a
  caller's override stacked instead of replacing.
- **A mobile-only `!important` 16 px floor** on `input, select, textarea` under
  `max-width: 767px`. iOS Safari zooms on focus below 16 px, and a utility class
  can beat a normal rule — this is the only reliable spelling. On desktop the
  floor loses to `text-sm` on twelve inputs, which is intentional.
- **`--chart-weekend-band` is stored as the exact canvas literal**
  (`rgba(255,255,255,0.015)`), whitespace included, so the token/literal equality
  tests can stay strict.

---

## 3. Gate rulings a maintainer will meet

These are the parts of the gate set most likely to surprise someone restyling a
template. The implementations are `scripts/audit/bindings.mjs` (G4),
`script-blocks.mjs` (G3), `text.mjs` (G4b).

### G3 — script blocks

Frozen byte-for-byte, with exactly two additive shapes allowed, each needing an
`allowlist.json` row:

1. `import { useId } from "vue";` as a **separate new import line** (the existing
   `vue` import is never edited — an edited line is a removed line), plus
   `const <name>Id = useId();` after the last baseline line. Five files needed
   this so a `<label for>` could reach an input PrimeVue wraps.
2. **E1**, the chart-token substitution: in `TimelineChart.vue`'s `draw()`, each
   `'#…'` / `'rgba(…)'` literal becomes `chartToken('<name>')` on the same line.
   G3 pairs every removed line with its added line and accepts only that rewrite.

### G4 — bindings

**Presentational props are ignored on primitives.** On an element whose tag is a
`Ui*` primitive, G4 ignores `variant`, `size`, `tone`, `status`, `loading` and
the rest of `PRESENTATIONAL_PROPS`, as long as the expression neither calls nor
assigns nor mutates: no `(`, no `=>`, no `++`/`--`, no backtick, no `=` beyond
`===`/`!==`/`>=`/`<=`. So `<button :class="c ? a : b" @click="f">` becoming
`<UiButton :variant="v" :active="c" @click="f">` is no drift. A prop that calls
something — `:tone="toneFor(deal)"` — stays recorded.

**Slots are ignored on a primitive, and on a `<template>` whose parent is a
primitive.** Moving copy into `<UiModalPanel><template #header>` is no drift.
A slot on `RouterView`, on `VueDraggable`, or on a `<template>` under either,
stays recorded.

**`as` is always recorded**, because `<UiCard as="button">` renders
`<component :is>` — it picks the element, which can change what a click or a form
submit does. One exception, added after the rule proved too noisy: a **static**
`as` naming a tag in `PRESENTATIONAL_TAGS` (`div`, `section`, `article`, `span`,
`p`, `h1`–`h6`, `li`, `ul`, `ol`, `dl`, `dt`, `dd`, `small`, `strong` — every
entry but `label`, which carries `for` semantics) needs no row. A **bound** `:as`
always stays recorded; the collector cannot see its runtime value.

**Presentational tags may alias.** A `Ui*` presentational primitive in the
working tree matches a `div`/`section`/`span`/`p`/`h*`/`li`/… in the manifest;
`button` matches `UiButton`/`UiIconButton`. Native and behavioural tags (`input`,
`a`, `form`, `canvas`, `VueDraggable`, `Teleport`, …) never alias. Goldens store
the original tags, so this widened the comparator, not the baseline.

**Static attributes that are behaviour stay recorded**, `to` among them — a moved
`<Teleport to>` is behaviour. `id`, `for`, `inputId`/`input-id`, `class`,
`style`, `pt`, `data-*`, `aria-*` and `role` are ignored as presentation.

### Two rules that follow from the freeze

- **Primitives never hard-code user-visible copy.** All of it arrives through
  slots from the view, so G4b's text manifest still sees it. Visually-hidden
  accessibility text inside a primitive is fine — G4b does not read primitive
  templates.
- **`UiTabs` and `UiStepper` are containers, never data-driven.** They wrap the
  view's existing `v-for` elements. A `steps` prop would delete the view's
  `v-for` and its interpolations, failing G4 and G4b at once.

### The parking elements

`DealInputsForm.vue` and `DaysUntilRefiField.vue` each end with a
`<span hidden aria-hidden="true" style="display: none" :class="[…]">` that
renders nothing. Seven frozen `<script>` computeds across the two files (six in
`DealInputsForm`, `dateInputClass` in `DaysUntilRefiField`) emit baseline class
strings that no rendered element wears any more, and `vue-tsc`'s `noUnusedLocals` rejects a
binding nothing reads. Parking them keeps both rules true and keeps rendered
elements on tokens only.

The inline `display: none` is load-bearing, not belt-and-braces: under
`surface="panel"` one of those computeds contributes `grid`, and Preflight's
`[hidden]` rule is emitted *before* `.grid` at equal specificity — the attribute
alone lost, and an empty grey card rendered at the foot of both deal modals until
the inline style was added. Measured: `display:none` 0 × 0 versus `grid`
942 × 50.

The alternative — raising `[hidden]`'s specificity globally — was rejected in
favour of the documented trap. **The computeds and their parking element come out
together the moment the freeze lifts**, which is the first thing v2 should do.

### G-HOVER and the hover flag

`future.hoverOnlyWhenSupported` wraps every `hover:` utility in
`@media (hover: hover)`, so a phone stops firing a hover style on the first tap
and keeping it until the next one. The plan enabled it in Phase 1; that was
**amended** — at that point fourteen hover-revealed controls had no touch
counterpart, and the flag would have made them invisible (though still clickable)
on every phone. It was enabled instead as the last step of Phase 3, once each of
the ten `group-hover:opacity-100` sites had a `touch:opacity-100` sibling.

Gate `G-HOVER` (`scripts/audit/hover-pairs.mjs`) fails the build if a new reveal
ever lands without one, because no Playwright actionability check and no axe run
can see an invisible-but-clickable control. The same `touch:` variant carries the
44 px floor (`touch:min-h-11`) on `size="sm"` buttons that are a primary action.

### Chart colours

`:root` carries the **light** chart palette; `.dark` keeps the original dark
literals, and so do `chartToken`'s fallbacks. The "fallback == tokens.css"
invariant from Phase 1 therefore ends at Task 3.9 by design: if a custom property
fails to resolve, the canvas falls back to exactly what it drew before the
overhaul rather than to a colour nobody has seen. Two palette values were moved to
clear 3:1 (`day-idle`, `marker-idle`); the decorative grid and bands are
deliberately below 3:1. jsdom has no custom-property cascade, so an unresolved
`--chart-*` can only be caught in a browser — `e2e/checks/chart-tokens.spec.ts`
asserts all 32 resolve non-empty on `/liquidity`.

### G1's two exclusions

`REPS_README.md` (Task 5.6) and the root `README.md` (Task 5.5) are excluded from
G1. Both are documentation in the class of `docs/`, not root files that carry
behaviour: `REPS_README.md` needed a `<path-to>/…` placeholder that G8 requires
and G1 would forbid, and the root README still told a reader that "Node not
required; frontend is static HTML/JS" and to serve a `FrontEnd/` directory that
no longer exists. `BackEnd/`, `runtime.txt` and `.gitignore` remain inside G1's
pathspec, so the gate still proves what it was written to prove.

### GOLDEN-POLICY covers the archived reports

The policy watched `scripts/audit/golden`, `e2e/golden` and `allowlist.json`.
`e2e/reports` joined them in Task 5.5: the behaviour-freeze proof *is*
`npm run e2e:compare` reading `phase0-baseline.json` against `phase5-final.json`,
so re-archiving either one inside an ordinary commit would move the proof's own
baseline with nobody reviewing the move.

---

## 4. Motion decisions

- **GSAP core only, pinned exact `3.15.0`.** No plugins. The plan said 3.13.x;
  that was superseded before Phase 4 began.
- **Motion attaches through globally registered wrappers and directives only** —
  `<UiTransition>`, `<UiTransitionGroup>`, `v-reveal`/`v-press`/`v-hover-lift`/
  `v-flash`/`v-count-up`. No view imports anything, because G3 forbids it. The
  entire surface a template sees is a `preset` attribute and a valueless
  directive.
- **`clearProps` is `transform,opacity,filter,willChange` on every path, never
  `all`** — `all` wipes the app's own inline styles. A cancelled leave also resets
  `pointer-events`.
- **`src/motion/gsap.ts` exposes `window.gsap`**, so the frozen e2e
  "no live tweens after navigation" guard is a real assertion rather than a
  vacuous one.
- **Modal transitions nest under the page transition.** That is a consequence of
  the mandated `RouterView` slot rewrite; it is safe because `page` has no leave
  hook and a cancel runs before the inner mount.
- **Board rows are revealed, cards never are.** A cross-column drop remounts the
  card vnode and SortableJS reads rects on drag start. `MyDeals` and
  `BoughtDeals` both use a bare `v-reveal` rather than `.stagger` on the rows,
  because a stagger would exceed the deep-link flow's 500 ms zero-tween check.

`frontend/README.md` carries the timing rules a change must not break (settle
window, `pointer-events` on leave, enter-only regions, opacity-only page and
chart, SortableJS).

---

## 5. Copy and markup changes that were dropped

- **The deal-type emoji badges stay.** The plan called for removing "🏠 BRRRR" /
  "💰 FLIP", but `src/components/DealCard.contract.test.ts` asserts both strings
  and the frozen suite wins over a copy preference. The badge is now driven by
  `:tone`, so removing the emoji in v2 is a template edit plus a test update.
- **`role="combobox"` on the REPS property input stays as found**, even though it
  advertises keyboard behaviour the frozen script does not implement. Zero-drift
  means pre-existing quirks are frozen, not fixed.
- **`NumberInput` reads `$attrs['data-input-id']` as an `inputId` stand-in**,
  because a frozen script cannot add a prop. Recorded for cleanup when the freeze
  lifts.
- **`DealCard`'s stage accent bar is restored through scoped `[data-stage]` CSS**
  that duplicates the frozen colour map, for the same reason.
- **The `DealInputsForm.vue` header comment was not updated**, though the root
  README's copy of the same checklist was: the comment lives inside the frozen
  script block.

---

## 6. Plan B — what v1 deliberately did not do

On 2026-09-05 the user chose to finish v1 as **"foundation complete"** and start
a bolder UI v2 on a new branch rather than keep polishing inside the freeze.
What that skipped, and why:

| Skipped | Why |
| --- | --- |
| **Task 4.4** — `v-flash` on stat tiles and results, keyed save-status fade, enter-only banners, optional `v-count-up` | The directives are built, unit-tested and registered; attaching them means editing templates v2 will rewrite. |
| **Task 4.5** — `<UiTransitionGroup>` on the comps lists, REPS entries, day rows, recurring rules | Same: the component exists and is tested, and is attached nowhere. |
| **Task 4.6** — drag polish (`ghost-class`, `chosen-class`, hover-lift suppression inside `VueDraggable`) | Touches the boards, which v2 restructures first. |
| **Task 4.7 reduced** to a performance / no-live-tweens check | The full DevTools-recording pass buys little against templates that are about to change. |
| **Tasks 5.2–5.4 folded** into one measure-only quality snapshot | Nothing was fixed; everything measured became a v2 follow-up. `docs/ui-overhaul/quality-snapshot.md` |
| **Per-task reviews dropped** in favour of reviews at the Phase 4 and Phase 5 gates | Per-task review was the single largest cost of v1. |

Consequence, stated plainly: **the motion layer is about a third attached.** Six
presets exist and three are used; five directives exist and one is used. That is
a deliberate hand-off, not an oversight — and it is why the README's motion table
has an "Attached in v1" column.

---

## 7. Parked follow-ups

None of these were fixed. `docs/ui-overhaul/quality-snapshot.md` §7 has the full
twenty with file and line references and the measurements behind them; this is
the maintainer's-eye summary, worst first.

**Accessibility**

1. **Substage checkboxes have no accessible name** (`BoughtDealCard.vue`) — axe
   `label`, critical, ×5. The Phase 0 baseline scans an empty board, so it never
   saw them. Fixing it is behavioural (a `<label>` or `aria-label`), which the
   freeze forbade.
2. **`mydeals.add-deal` is an unnamed icon button below 768 px** — critical, and
   the only thing between `/my-deals` and a Lighthouse accessibility 100.
3. **`text-negative` on `bg-negative/10` is 4.14:1 at ten sites** (six rendered,
   three hover-only, one latent in `UiBadge`'s `negative` tone). The contrast
   script audits declared token *pairs* and cannot see a foreground on a tint of
   its own token. Candidate fix: step `--color-negative` to red-700 and re-run.
4. **`text-emerald-600` bypasses the `positive` token** — 3.77:1 on `surface`, in
   four `return` strings in `MyDeals`/`BoughtDeals`. The token in the same slot
   is 5.48:1.
5. **No `<main>` on five of six routes** — collapses five `landmark-one-main`
   violations and most of twenty-six `region` ones.
6. **`h1 → h3` skips a level on three routes**, and `/liquidity`'s sidebar uses
   `UiSectionHeader as="h4"` under an `h3`.
7. **An open modal leaves the page `<header>` in the tree** —
   `landmark-no-duplicate-banner` on all three modals.
8. **Kanban columns scroll but cannot be focused** (`scrollable-region-focusable`,
   serious, ×2).
9. **PrimeVue's LTV slider has no accessible name** (`aria-input-field-name` ×2).
10. **`role="combobox"` advertises keyboard behaviour that does not exist** (§5).
11. **Comp delete is an icon button whose `aria-label` differs from its visible
    `x`** — noted in the Task 3.7 review, left alone.

**Layout and interaction**

12. **CLS 0.138 (`/`) and 0.178 (`/my-deals`)**, both above the 0.1 threshold and
    both traced to one node: `PortfolioStatsBar.vue`'s `v-if="hasDeals"`, which
    does not exist until `GET /active-deals` resolves and then pushes the page
    down. Pre-existing — the same `v-if` is on the same line at `ui-baseline`.
    The highest-value performance fix available.
13. **A deep-linked deal modal opens two-thirds scrolled.**
14. **The liquidity chart's plot area is flush with its container at every
    width** — the y-axis labels overprint the leading column.
15. **Empty kanban columns reserve 243 CSS px each** at 390 × 664 — 37 % of the
    viewport.
16. **`reps.refresh` is still a 36 px target** (ratified in Task 3.11b rather
    than fixed).
17. **The PDF preview may bottom out in the iOS home-indicator band, and an iOS
    `iframe` renders page 1 only.**
18. **`TransactionForm`'s submit shortcut is `metaKey`-only** — Ctrl+Enter is
    dead on Windows and Linux. Frozen as found in Phase 0.

**Cosmetic / content**

19. **The required-asterisk class never renders, in all four input primitives.**
    Tailwind emits `after\:content-\[\\'\*\\']:after{--tw-content:'*'}`, whose
    selector cannot match the class Vue renders (`after:content-['*']`).
20. **`Cash Out Routi` is truncated in the data**, and **`/reps` prints its
    README hint twice.**

**Engineering**

21. **No mechanical guard against `computed()` over `useSlots()`/`useAttrs()` in
    a primitive.** Such a computed caches with an empty dependency set and never
    updates — it was found by review three times in Phase 2. A one-line grep
    check could join `verify:ui`.
22. **`chromium-motion` ran in Phase 0 but not in the Phase 5 archive** (four
    projects versus five); its two specs were proven separately. It is now in
    `PHASE_PLAYWRIGHT_PROJECTS`, so the next phase run covers it.
23. **Two frozen `test.skip(isNarrow)` reasons are stale** — Task 3.9's
    header-wrap fix made one of them pass. Un-skipping edits a frozen spec and
    needs a tag move.

---

## 8. Next

`docs/superpowers/plans/2026-09-05-ui-v2-followup-prompt.md` is the drafted
opening prompt for UI v2. Its two load-bearing points:

- **Retire or downgrade G3, G4 and G4b.** They forbid exactly the layout and copy
  changes a redesign needs. Keep G1, G2, G5, G6, G7, G-HOVER and G8 — the
  behaviour proof survives without the structure freeze, as long as every
  `data-testid` hook survives with it.
- **Close the suite's coverage gaps before restructuring anything.** With
  templates and scripts open to change, the test suites are the only guard left,
  and today they have known holes: chromium-only drag flows, skipped
  narrow-viewport liquidity cases, and modal markup that axe never scans.
