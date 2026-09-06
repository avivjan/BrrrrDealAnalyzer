# Liquidity timeline — v2 page rules

> **PROJECT:** BRRRR Deal Analyzer · **UI v2** (docs/plans/2026-09-05-ui-v2-plan.md)
> Rules here override `MASTER.md`. Look-agnostic: they name tokens and primitives, never a look.

## Layout
- `xl+`: `grid grid-cols-[1fr_20rem] grid-rows-[auto_auto_1fr] gap-4`. Row 1 (both columns): header KPIs — current balance, minimum, days to negative, reserve — as `UiKpiCard`s computed from `store.series` (no new fetch). Row 2 (both columns): the chart panel (`UiSurface level=1 padding="none"`, `min-h-[380px]`). Row 3: `DayDetail` left, `LiquiditySidebar` right rail.
- `lg`: sidebar `18rem`. `<lg`: single column — KPIs (2-up), chart (`min-h-[320px]`), DayDetail, then the sidebar as an **inline collapsible section** (`liquidity.sidebar-toggle`, `aria-expanded`), never `hidden`.
- Header controls (`liquidity.back/today/mercury-sync/settings-open/add-flow`) wrap to two rows below `sm` so the page never overflows 390 px.
- **No size/padding/transform transitions on the chart panel or any ancestor.**

## Chart (`TimelineChart`, SVG)
- Contract unchanged (props, `selectDay(date)`, `centerOnToday`, `chart.container` `tabindex="0"`, arrow keys, hover-over-selection, <4 px click vs pan, wheel pan). Per-day `<g aria-label>`; balance path with a one-shot draw-on; bars for inflow/outflow; zero line; reserve band; today line; global-min markers; crosshair moved by direct CSS transform. Colours via the 32 `chartToken()` calls in one `computed` that reads `themeEpoch`.
- Legend as text + line style, never hue alone; a "Data" toggle reveals the same series as a `UiDataTable` (the chart's accessible fallback).

## Modals (`TransactionForm`, `SettingsPanel`, `SimulationWarning`)
- `UiModalPanel` inside the existing `Teleport` + `<Transition name="modal">`; `UiField` wiring; one-time/recurring as `UiSegmented`; recurring preview as `UiDataTable`; warning severity with `shadow-glow-negative` in looks that glow. Props/emits/keydown unchanged; `txnform.*`, `settings.*`, `simwarn.*` hooks unchanged.
