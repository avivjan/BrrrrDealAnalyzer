# Design System Master File

> **LOGIC:** When building a specific page, first check `design-system/pages/[page-name].md`.
> If that file exists, its rules **override** this Master file.
> If not, strictly follow the rules below.

---

**Project:** BRRRR Deal Analyzer
**Generated:** 2026-09-04 20:03:48
**Category:** Real Estate/Property
**Design Dials (v1):** Variance 4/10 | Motion 5/10 | Density 7/10 — **v2:** Variance 8/10 (Bold) | Motion 8/10 (Complex) | Density 6/10 (Standard)

---

## Approved overrides v2 (supersedes v1 in full; binding)

**This section supersedes the v1 "Approved overrides" in full.** v1's rejection
of glassmorphism and hero-centric patterns, and its "light theme app-wide, no
toggle" pin, are withdrawn. Source: `docs/plans/2026-09-05-ui-v2-plan.md` §1,
approved 2026-09-05. Wherever anything below conflicts with the generator
output further down this file (v1 or v2), the overrides win.

1. **Four looks × two modes, user-switchable.** `obsidian` (Obsidian Terminal),
   `aurora` (Aurora Glass), `brutal` (Neo-Brutal Fintech), `luxury` (Quiet
   Luxury); modes light / dark / system. **Default: `luxury` + dark.**
   Persistence is per browser (`localStorage`: `bw.look`, `bw.theme`,
   `bw.motion`); the app has no accounts. Applied as `<html data-look="…"
   class="dark">` by `index.html` (pre-paint) and `src/design/theme.ts`.
   **Components never name a look** — they use tokens; a look is one generated
   CSS file (`src/assets/looks/<id>.css`, from `scripts/design/looks.data.mjs`).
2. **Token vocabulary.** Colours `page, surface, surface-muted, surface-2,
   surface-3, line, fg, fg-muted, primary, primary-hover, primary-fg, accent,
   accent-2, positive, negative, warning, ring, glass, glass-line, chart-1..8`
   (RGB triplets); the 32 `--chart-*` literals (derived per palette); shape
   `--radius-sm/md/lg`, `--border-w`, `--shadow-1..4`, `--glow-primary/accent/negative`,
   `--blur-glass`, `--gradient-brand/surface`; type `--font-display`,
   `--font-mono`, `--track-display`; motion `--dur-fast/base/slow`,
   `--ease-*`, `--gsap-ease-*`; `--ambient`. Every look sets every token in
   both modes (`src/design/looks.test.ts`).
3. **Type.** Body is always Inter Variable. `font-display` and `font-mono`
   resolve to the look's faces; numerals use `.numeric` (mono, tabular).
   Fonts are self-hosted (`@fontsource*`) and loaded lazily per look.
4. **Depth.** Surface tiers 1–3, elevation shadow-1..4, glass panels only as
   containers (see Glass rule), glow reserved for the primary CTA, the active
   nav item and a focused KPI. Gradients from tokens only.
5. **Data-viz.** `chart-1..8` per look and mode; the liquidity chart's 32
   literals are derived from the palette (`chartLiterals()` in the generator).
6. **Iconography.** primeicons, 20 px in nav, 16 px inline; icon-only controls
   are `UiIconButton` with a `label`.
7. **App shell.** Desktop grid `[var(--sidebar-w)_1fr] / [auto_1fr]`, collapsible
   sidebar (15 rem ↔ 4.5 rem, **no width transition**), topbar (title, ⌘K,
   mode toggle, settings, connection status), `<main id="main">` as the one
   scroller. Mobile: sticky topbar + fixed bottom nav (`pb-safe-b`). Command
   palette `Cmd/Ctrl+K`, client-side only.
8. **Settings → Appearance** (a `UiDrawer`): Look picker with live previews
   (`role="radiogroup"`), Mode (Light / Dark / System), Motion (Full /
   Reduced). Saved automatically, per browser; footer copy says so.
9. **Dashboard** replaces the landing page: greeting, `PortfolioStatsBar` in a
   height-reserved slot, seven quick-action tiles (same hooks and hrefs), the
   four resource links as chips. No new fetches.
10. **PortfolioStatsBar** renders only on the dashboard; **`app.status`** lives
    in the topbar on every route (same testid, role, aria-live and strings).
11. **Liquidity** is a grid dashboard with an SVG `TimelineChart` (contract
    intact; 32 `chartToken()` calls in one theme-reactive `computed`).
12. **Script-emitted palette classes** in MyDeals / BoughtDeals map to token
    classes (`text-positive`, `border-l-chart-1..4`, `bg-surface border-line`).
13. **Motion tiers per look.** Standard (presets + directives) and Complex (six
    one-shot choreographies). GSAP reads `--dur-*` / `--gsap-ease-*` from the
    active look at tween time. Ambient loops are CSS `@keyframes`, never GSAP
    `repeat: -1`, never `quickTo`. Look/mode cross-fade is CSS.
14. **Accessibility floor.** WCAG 2.2 AA: 4.5:1 text in all 8 look × mode
    sets (`npm run audit:contrast`, 27 pairs per set), 44 px primary touch
    targets, visible focus, `prefers-reduced-motion` **and** the in-app
    Motion setting honoured, no new axe violations in any set.

### Glass rule

Body text never sits directly on glass. A `UiGlassPanel` is a *container*;
its children are `UiSurface`s, `UiKpiCard`s or a nav list. Text over a
blurred, moving background cannot be held to a contrast ratio, so the ratio is
measured on the inner surface instead. Looks with `--blur-glass: 0px` render
glass as an opaque surface-2 panel from the same class.

### Motion tiers

- **Standard:** `v-reveal` / `v-reveal.stagger` on grids, `UiTransition
  preset="modal"` on modals and drawers, `preset="page"` (opacity-only,
  enter-only) on routes, `v-press` on primary buttons, `v-hover-lift` on KPI
  cards, `v-flash` on autosave values, `v-count-up` on dashboard numerals.
- **Complex (one-shot, `clearProps` on complete):** dashboard KPI count-up +
  sparkline draw-on; sidebar active-indicator slide; command palette spring
  (`back.out`) + item stagger; liquidity balance draw-on once per mount;
  kanban column-header stagger on tab change; theme cross-fade (CSS).
- Tempo per look: obsidian 120/180/280 ms, aurora 200/320/480 ms (spring),
  brutal 120/200/300 ms, luxury 220/400/600 ms.

## Looks

Values are in `scripts/design/looks.data.mjs`; this is the intent behind them.
Each look must never: name itself in a component, drop a token, or fall below
the contrast floor in either mode.

### Obsidian Terminal (`obsidian`)

Near-black surfaces, one electric-cyan accent, hairline borders, mono
numerals everywhere. Bloomberg meets Linear. Display face **JetBrains Mono**
(the numerals *are* the headline). Radii 4/6/8, borders 1 px, no drop shadow
(depth is a hairline ring), no glow, no blur. Tempo 120/180/280 ms with
near-linear eases. Light mode: cool greys, cyan-700 accent. Never: gradients
as decoration, springy easing, large type.

### Aurora Glass (`aurora`)

Deep navy-to-indigo gradients, aurora blobs drifting behind frosted panels,
violet primary with cyan and magenta accents. Display face **Space Grotesk**.
Radii 12/16/20, blur 14 px, glows on CTA / active nav / focused KPI, deep soft
shadows. Tempo 200/320/480 ms, `back.out(1.4)` for emphasis. Ambient
`gradient-drift` (CSS). Light mode: lavender page, white panels, indigo
primary. Never: body text directly on glass (Glass rule), more than one glow
per viewport region, blur on scrolling containers.

### Neo-Brutal Fintech (`brutal`)

Flat saturated blocks, 2 px borders in the ink colour, hard offset shadows
(`6px 6px 0`), lime on black in dark mode, black on off-white in light mode
(lime becomes the on-primary ink and `accent-2`). Display face **Unbounded**
900. Radii 2 px, no blur, no glow. Tempo 120/200/300 ms, `expo.out`. Never:
soft shadows, translucency, thin type, more than three colours on one panel.

### Quiet Luxury (`luxury`) — default

Warm charcoal and graphite, champagne-gold accent, **Fraunces** serif
headlines beside Inter, generous whitespace, soft two-tier depth. Radii
10/12/16, borders 1 px, no glow, no blur. Tempo 220/400/600 ms, gentle
eases. Ambient `shimmer` on the hero rule only. Light mode: warm paper page,
bronze primary. Never: neon, hard shadows, dense layouts, bright semantic
colours (positive/negative stay muted but ≥ 4.5:1).

### v2 generator run (recorded, mostly rejected)

`search.py "enterprise fintech analytics platform, futuristic, premium"
--design-system --density 6 --motion 8 --variance 8` returned pattern
**Scroll-Triggered Storytelling** (a marketing narrative; this is a tool with
no scroll story — rejected), style **Brutalism** (adopted only as one of the
four looks, not as *the* style), an indigo/orange OLED palette (not used; each
look has its own), typography Inter/Inter (kept as the body face only) and a
**Flip-plugin page transition** (rejected: GSAP core only, and the `page`
preset must stay opacity-only because a fixed modal can open mid-transition).

Domain queries (`--max-results 2`): typography "geometric display paired with
Inter" → *SaaS Mobile Boutique* (Calistoga + Inter + JetBrains Mono) —
confirms the tri-stack shape (display + Inter + mono) used by every look;
Calistoga itself not adopted. "serif display fintech premium" → *Classic
Elegant* (Playfair + Inter) — confirms serif-display-over-Inter for Quiet
Luxury; Fraunces chosen for its variable optical size. "monospace-led
interface terminal" → *Terminal CLI Monospace* (JetBrains Mono single family)
— adopted for Obsidian's display face; its "400 weight only" note is kept.
Colour "dark fintech dashboard glow accents" → *Financial Dashboard* (dark bg
+ green positive indicators) — confirms positive/negative as the only semantic
hues; "warm charcoal gold luxury" → *E-commerce Luxury* (stone neutrals +
`#A16207` gold) — confirms the bronze light-mode primary for Quiet Luxury;
"neo-brutalist high contrast" → no brutalist row (a navy government palette)
— recorded as a miss. UX "command palette accessibility", "sidebar navigation
collapsed", "dashboard KPI hierarchy" → generic rows (keyboard navigation
with visible focus; sticky nav must not obscure content; sequential heading
levels) — all carried into the shell rules; "theme picker settings" → **no
database match**; the Settings drawer follows the radiogroup pattern instead.
Chart "running balance timeline dark" → *Trend Over Time* (line/area, SVG
below 1000 points, keyboard focus reveals values, never hue alone) — adopted
for the SVG `TimelineChart`.

---

## v1 record (historical)

The sections below are the v1 design system as generated on 2026-09-04 and its
approved overrides. They are kept for the record; **the v2 overrides above
replace them.**

### v1 approved overrides (plan §2)

These come from the master plan's §2 (verified, domain-targeted searches) and are **binding**: wherever they conflict with the generic `--design-system` output further down this file, the overrides win.

- Typography: single family **Inter** (self-hosted variable font).
- Primary: indigo-600 **#4F46E5** (hover indigo-700 **#4338CA**, on-primary white) — the app's existing accent.
- Neutrals: **slate** (bg slate-50, surface white, muted surface slate-100, border slate-200, text slate-900 / slate-600).
- Financial semantics: positive **emerald-700 #047857**, negative **red-600 #DC2626**, warning **amber-700 #B45309** (text-safe shades, always paired with a sign or icon).
- Focus ring: indigo-500.
- Radii: 6 / 10 / 16 px.
- 4-pt spacing; density 7 (standard).
- Type scale 12/14/16/18/24/32, weights 400/500/600–700, tabular numerals on all money/percent cells, body ≥ 16 px on mobile.
- Motion 150 / 250 / 400 ms with eases power2.out (standard), power3.inOut (emphasized), power1.in (exit).
- Light theme app-wide, dark tokens defined under `.dark` but no toggle shipped.

#### Rejected tool output (v1)

The generic `--design-system` run above (query `"financial dashboard calculator real estate"`, density 7 / motion 5 / variance 4) picked its style and typography from the "Real Estate/Property" category rather than a numeric-tool category, and the raw pick does not fit this app. Concretely, this run returned: page pattern **Hero-Centric Design** (a marketing/landing funnel — full-bleed hero, single value-prop strip, key-benefit proof, one primary CTA — built for conversion, not for a form-heavy calculator with no funnel to convert through); style **Glassmorphism** (frosted-glass panels, backdrop blur, "vibrant background/light source" effects aimed at high-end corporate and SaaS marketing surfaces); and typography **Cinzel / Josefin Sans**, a luxury real-estate serif pairing (mood keywords: "luxury, elegant, sophisticated, premium") that is wrong for tabular financial data. The color palette it generated (teal/blue on a light `#F0FDFA` background) is also not dark/OLED, in case a different run of this generator is compared later — it is simply an unrelated real-estate brand palette, not a financial one. All three (pattern, style, typography) are rejected as a mis-fit for a numeric deal-analysis tool; the plan's §2 domain-targeted queries (color/typography/style/product, run below) are the source of truth instead, per plan §2.1: *"The generic `--design-system` run returned a marketing 'Enterprise Gateway' pattern with a luxury serif (Cinzel), which is a mis-fit for a numeric tool and is rejected; the targeted domain queries below are the source of truth."*

### v1 verified queries

Each query below was run with `--max-results 3` against the same script. "Applied as" states how it feeds the tokens above; a row is kept only if it plausibly fits a numeric financial tool, otherwise the mismatch is noted and the plan §2 default is cited instead.

1. **`"personal finance tracker trust blue profit green" --domain color`** → top result: *Personal Finance Tracker* — primary `#1E40AF` (trust blue) + accent `#059669` (profit green), notes "Trust blue + profit green on dark". Fit: the trust-blue/profit-green *concept* fits, but the row itself is a dark-background palette (`#0F172A`). Applied as: confirms the color pairing named in plan §2.2, adapted to light theme with the app's existing indigo-600 accent per the Approved overrides above (not copied verbatim) — this is exactly the adaptation plan §2.2 already documents.
2. **`"inter system modern dashboard" --domain typography`** → top result: *Modern Dark Cinema (Inter System)* — single-family Inter, "Best For: Developer tools, fintech/trading, AI dashboards... high-end utility". Fit: direct match. Applied as: source for the Inter-only type system in the Approved overrides.
3. **`"data dense dashboard minimal swiss" --domain style`** → only 1 result: *Data-Dense Dashboard* — "Best For: Business intelligence dashboards, financial analytics, enterprise reporting". Fit: direct match. Applied as: confirms plan §2.1's stated secondary style (Minimalism/Swiss reads as this style's low-chrome, grid-driven presentation) for the calculator's information density.
4. **`"fintech calculator analytics dashboard tool" --domain product`** → top result: *Analytics Dashboard* (SaaS growth metrics — funnel/cohort/attribution), 2nd result: *Financial Dashboard* (portfolio/trading/pnl/budget/cashflow/investment, "Color Palette Focus: Dark bg + red/green alerts + trust blue"). Fit: the top row is a generic BI-analytics fit; the 2nd row is the better fit for a real-estate deal calculator's domain (cashflow/investment vocabulary). Applied as: used result 2's palette focus ("trust blue + profit green [green via financial-semantics token] + red alerts") as confirmation of plan §2.1's product classification; its own suggested "Dark Mode (OLED)" is not used — superseded by the Approved overrides' light-theme decision.
5. **`"dark mode contrast semantic tokens" --domain ux`** → top result: generic *Contrast Readability* (light-background text contrast); no row specifically addresses dark-mode semantic tokens. Fit: no literal match; recording the miss per the brief. Applied as: falls back to the plan §2 default — dark values are defined under `.dark` as desaturated tonal variants (not inversions) per plan §2.2, and the 2nd result's general rule (4.5:1 minimum contrast, WCAG AA) is the contrast law carried into both themes.
6. **`"slider handle touch target" --domain ux`** → top result: *Touch Target Size* — "44pt iOS / 48dp Android / 24 CSS px web + WCAG Target Size rule". Fit: direct match for the app's percentage/rate sliders. Applied as: minimum hit-area rule for slider handle components (Phase 2 `UiField`/slider primitives).
7. **`"cumulative running balance timeline" --domain chart`** → top result: *Cumulative Changes* → Waterfall Chart (discrete additive P&L/budget-variance bars); 2nd result: *Trend Over Time* → Line Chart (continuous time-series, "trend, timeline, progress"). Fit: the top row matches the word "cumulative" but describes a discrete bar breakdown, not what the app's existing Liquidity `TimelineChart` renders (a continuous running-balance line over time). Applied as: result 2 (Line/Area, continuous time series) is the one actually applied to `--color-chart-1..6` and the Liquidity `TimelineChart`; result 1's waterfall pattern is noted as a candidate only if a future discrete P&L-bridge view is added, not used now.
8. **`"hover micro-interaction subtle" --domain gsap`** → top result: *Hover Micro-interaction, Subtle* (150-200ms, `power1.out`); 2nd result: *Standard* (200-300ms, `power2.out`, "Use `gsap.quickTo()` for cards with many hover targets"). Fit: both are usable; result 2 matches the project's motion dial (5/10 = "Standard") and the Approved overrides' "standard" ease (`power2.out`) exactly, while result 1's ease doesn't match any of the three approved eases. Applied as: result 2 is the one applied to hover states on `UiCard`/`UiStatTile`; its `quickTo()` guidance is noted for grids of many stat tiles.
9. **`"stagger list reveal" --domain gsap`** → top result: *Complex* tier using the `SplitText` plugin (headline character-splitting); 3rd result: *Standard* tier, plain `gsap.from` grid stagger, `back.out(1.4)`, no plugin. Fit: the top row needs the `SplitText` plugin, which conflicts with plan §5's "GSAP core only (no Flip, no ScrollTrigger)" — it also targets headline copy, not financial list/card reveals. Applied as: result 3 (core-only, matches this run's own generated Motion section verbatim) is the one applied to list/card reveal.
10. **`"page transition fade" --domain gsap`** → top result: *Subtle* tier, plain opacity cross-fade (`power1.inOut`, 200-300ms, route-change trigger, no plugin). Fit: direct match, and it is core-GSAP only. Applied as: applied for view-to-view transitions; the 2nd result (uses the Flip plugin) is rejected per plan §5's "GSAP core only" constraint, and the 3rd result's overlay wipe is heavier than this form-heavy tool needs.

---

## Global Rules

### Color Palette

| Role | Hex | CSS Variable |
|------|-----|--------------|
| Primary | `#0F766E` | `--color-primary` |
| On Primary | `#FFFFFF` | `--color-on-primary` |
| Secondary | `#14B8A6` | `--color-secondary` |
| On Secondary | `#0F172A` | `--color-on-secondary` |
| Accent/CTA | `#0369A1` | `--color-accent` |
| On Accent/CTA | `#FFFFFF` | `--color-on-accent` |
| Background | `#F0FDFA` | `--color-background` |
| Foreground | `#134E4A` | `--color-foreground` |
| Card | `#FFFFFF` | `--color-card` |
| Card Foreground | `#134E4A` | `--color-card-foreground` |
| Muted | `#E8F0F3` | `--color-muted` |
| Muted Foreground | `#475569` | `--color-muted-foreground` |
| Border | `#99F6E4` | `--color-border` |
| Destructive | `#DC2626` | `--color-destructive` |
| On Destructive | `#FFFFFF` | `--color-on-destructive` |
| Ring | `#0F766E` | `--color-ring` |

**Color Notes:** Trust teal + professional blue

### Typography

- **Heading Font:** Cinzel
- **Body Font:** Josefin Sans
- **Mood:** real estate, luxury, elegant, sophisticated, property, premium
- **Google Fonts:** [Cinzel + Josefin Sans](https://fonts.googleapis.com/css2?family=Cinzel:wght@400;500;600;700&family=Josefin+Sans:wght@300;400;500;600;700&display=swap)

**CSS Import:**
```css
@import url('https://fonts.googleapis.com/css2?family=Cinzel:wght@400;500;600;700&family=Josefin+Sans:wght@300;400;500;600;700&display=swap');
```

### Spacing Variables

*Density: 7/10 — Standard*

| Token | Value | Usage |
|-------|-------|-------|
| `--space-xs` | `4px` / `0.25rem` | Tight gaps |
| `--space-sm` | `8px` / `0.5rem` | Icon gaps, inline spacing |
| `--space-md` | `16px` / `1rem` | Standard padding |
| `--space-lg` | `24px` / `1.5rem` | Section padding |
| `--space-xl` | `32px` / `2rem` | Large gaps |
| `--space-2xl` | `48px` / `3rem` | Section margins |
| `--space-3xl` | `64px` / `4rem` | Hero padding |

### Shadow Depths

| Level | Value | Usage |
|-------|-------|-------|
| `--shadow-sm` | `0 1px 2px rgba(0,0,0,0.05)` | Subtle lift |
| `--shadow-md` | `0 4px 6px rgba(0,0,0,0.1)` | Cards, buttons |
| `--shadow-lg` | `0 10px 15px rgba(0,0,0,0.1)` | Modals, dropdowns |
| `--shadow-xl` | `0 20px 25px rgba(0,0,0,0.15)` | Hero images, featured cards |

---

## Component Specs

### Buttons

```css
/* Primary Button */
.btn-primary {
  background: #0369A1;
  color: white;
  padding: 12px 24px;
  border-radius: 8px;
  font-weight: 600;
  transition: all 200ms ease;
  cursor: pointer;
}

.btn-primary:hover {
  opacity: 0.9;
  transform: translateY(-1px);
}

/* Secondary Button */
.btn-secondary {
  background: transparent;
  color: #0F766E;
  border: 2px solid #0F766E;
  padding: 12px 24px;
  border-radius: 8px;
  font-weight: 600;
  transition: all 200ms ease;
  cursor: pointer;
}
```

### Cards

```css
.card {
  background: #F0FDFA;
  border-radius: 12px;
  padding: 24px;
  box-shadow: var(--shadow-md);
  transition: all 200ms ease;
  cursor: pointer;
}

.card:hover {
  box-shadow: var(--shadow-lg);
  transform: translateY(-2px);
}
```

### Inputs

```css
.input {
  padding: 12px 16px;
  border: 1px solid #E2E8F0;
  border-radius: 8px;
  font-size: 16px;
  transition: border-color 200ms ease;
}

.input:focus {
  border-color: #0F766E;
  outline: none;
  box-shadow: 0 0 0 3px #0F766E20;
}
```

### Modals

```css
.modal-overlay {
  background: rgba(0, 0, 0, 0.5);
  backdrop-filter: blur(4px);
}

.modal {
  background: white;
  border-radius: 16px;
  padding: 32px;
  box-shadow: var(--shadow-xl);
  max-width: 500px;
  width: 90%;
}
```

---

## Style Guidelines

**Style:** Glassmorphism

**Keywords:** Frosted glass, transparent, blurred background, layered, vibrant background, light source, depth, multi-layer

**Best For:** Modern SaaS, financial dashboards, high-end corporate, lifestyle apps, modal overlays, navigation

**Key Effects:** Backdrop blur (10-20px), subtle border (1px solid rgba white 0.2), light reflection, Z-depth

### Page Pattern

**Pattern Name:** Hero-Centric Design

- **Conversion Strategy:** One primary CTA. Let the hero dominate the initial viewport without hiding the next content cue. Use a static hero and non-pulsing CTA when reduced motion is requested; provide video controls. Pause hero media offscreen/hidden and keep the final hero message and CTA static under reduced motion.
- **CTA Placement:** Hero dominant (center/bottom) + Sticky nav CTA
- **Section Order:** Full-bleed Hero (headline + visual) > Single value prop strip > Key benefit or proof > Primary CTA

---

## Motion

**Stagger List** (Standard) — Trigger: load or scroll | Duration: 300-450ms | Easing: `back.out(1.4)`

```js
gsap.from('.grid-item', { opacity: 0, scale: 0.92, y: 16, duration: 0.4, stagger: { each: 0.06, from: 'start', grid: 'auto' }, ease: 'back.out(1.4)' });
```

**Framework notes:** grid: 'auto' lets GSAP infer rows/columns from a CSS grid layout for a natural wave stagger; Use matchMedia('(prefers-reduced-motion: reduce)') to skip non-essential motion and render the final state immediately

- ✅ Combine with from: 'center' for a bento-grid layout to draw the eye inward first
- ❌ Don't use back.out on dense data tables; the overshoot reads as sloppy on informational UI
- ⚡ Group DOM writes; avoid interleaving layout reads (getBoundingClientRect) between staggered tweens

---

## Anti-Patterns (Do NOT Use)

- ❌ Poor photos
- ❌ No virtual tours

### Additional Forbidden Patterns

- ❌ **Emojis as icons** — Use SVG icons (Heroicons, Lucide, Simple Icons)
- ❌ **Missing cursor:pointer** — All clickable elements must have cursor:pointer
- ❌ **Layout-shifting hovers** — Avoid scale transforms that shift layout
- ❌ **Low contrast text** — Maintain 4.5:1 minimum contrast ratio
- ❌ **Instant state changes** — Always use transitions (150-300ms)
- ❌ **Invisible focus states** — Focus states must be visible for a11y

---

## Pre-Delivery Checklist

Before delivering any UI code, verify:

- [ ] No emojis used as icons (use SVG instead)
- [ ] All icons from consistent icon set (Heroicons/Lucide)
- [ ] `cursor-pointer` on all clickable elements
- [ ] Hover states with smooth transitions (150-300ms)
- [ ] Light mode: text contrast 4.5:1 minimum
- [ ] Focus states visible for keyboard navigation
- [ ] `prefers-reduced-motion` respected
- [ ] Responsive: 375px, 768px, 1024px, 1440px
- [ ] No content hidden behind fixed navbars
- [ ] No horizontal scroll on mobile
