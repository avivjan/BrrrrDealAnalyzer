# Dashboard (route /) — v2 page rules

> **PROJECT:** BRRRR Deal Analyzer · **UI v2** (docs/plans/2026-09-05-ui-v2-plan.md)
> Rules here override `MASTER.md`. Look-agnostic: they name tokens and primitives, never a look.

## Layout
- `max-w-7xl` grid. Row 1: greeting + date (`h1 font-display`) and the `landing.offer` primary CTA (`shadow-glow-primary`). Row 2: `PortfolioStatsBar` inside `<div class="min-h-stats-bar">` (reserved height → CLS 0). Row 3: quick-action grid of the **seven** feature tiles (`grid-cols-2 md:grid-cols-3 xl:grid-cols-4`), each `UiKpiCard`-styled on a `UiSurface interactive`, keeping `:data-testid="`landing.card.${card.title}`"`, the same `component :is` (RouterLink / `a`) and hrefs. My Deals / Bought Deals / Liquidity tiles show a figure from `dealStore.portfolioStats` (already fetched). Row 4: the four resources as `UiChip href` (`landing.resource.<title>`).
- Ambient background: the look's `--ambient` via CSS keyframes only; paused under reduced motion and `(hover: none)`.

## Copy / hooks that must not change
- Card titles: REPS Tracker, Daily Tasks, Stessa, Analyze Deal, My Deals, Bought Deals, Liquidity. Hooks `landing.offer`, `landing.card.*`, `landing.resource.*`, `statsbar.root`, `app.status`.
- Network: load issues exactly `GET /helloworld` and `GET /active-deals` (App.vue), nothing else.

## Accessibility musts
- `h1` then `h2` per row; tiles are links with visible focus; external links say so (icon + `rel="noopener"`).
