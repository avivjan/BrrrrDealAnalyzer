# My Deals board — v2 page rules

> **PROJECT:** BRRRR Deal Analyzer · **UI v2** (docs/plans/2026-09-05-ui-v2-plan.md)
> Rules here override `MASTER.md`. Look-agnostic: they name tokens and primitives, never a look.

## Layout
- Root `h-full flex flex-col` (not `h-dvh`; the shell owns the viewport). Header row: title, tabs (`UiTabs`), add-deal (`mydeals.add-deal`, **labelled** at every width — fixes the 390 px `button-name` critical).
- Board: horizontal `overflow-x-auto` row of stage columns, each `min-w-[16rem]` on a `UiSurface level=1`; column header is a glass strip with a `UiChip` count; empty column = compact `UiEmptyState` (`min-h-0`, no 243 px well). Both the `VueDraggable` branch and the plain-grid branch render identically; **nothing wraps or animates draggable children**; `ghost-class`/`chosen-class` are token classes.
- Cards (`DealCard`): `UiSurface interactive`, `UiBadge dealType`, `UiProgressRing` for completeness, action buttons as `UiIconButton`s visible on touch (`touch:opacity-100`).
- Detail modal: `UiModalPanel size="xl"`; body is the only scroller; a sticky summary rail of `UiKpiCard`s at the top of the body; `modalScrollContainer` ref stays `flow-root`; `analysisResultsEl` keeps its ref. Footer: `UiSaveStatus` + actions.
- Script helpers `getCashFlowColor/getPerformanceColor/getDSCRColor` return `text-positive/text-negative/text-fg/text-fg-muted`; `stages[].color` → `bg-surface border-line`.

## Accessibility musts
- Kanban columns that scroll are focusable (`tabindex="0"` + `aria-label`). Heading order h1 → h2 → h3. Hooks `mydeals.*`, `dealcard.*` unchanged; `modal-scroll.spec.ts` green.
