# Bought Deals pipeline — v2 page rules

> **PROJECT:** BRRRR Deal Analyzer · **UI v2** (docs/plans/2026-09-05-ui-v2-plan.md)
> Rules here override `MASTER.md`. Look-agnostic: they name tokens and primitives, never a look.

## Layout
- Same board rules as My Deals. Pipeline shown with `UiTimelineRail` (stages as steps; active stage `aria-current`), horizontal on desktop, compact below `md`.
- Cards (`BoughtDealCard`): stage accent via `border-l-chart-1..4` (from `getStageAccentColor`), substage checklist with **labelled** checkboxes (`<label for>`; fixes the `label` critical), `UiProgressRing` = substages done.
- Detail modal as My Deals plus the stepper (`UiStepper`/`UiTimelineRail`) and the substage list; "Advance" as `UiButton variant="primary"`.

## Accessibility musts
- Every substage checkbox has a visible label; `boughtdeals.*`, `boughtcard.*` hooks unchanged; drag flow (`bought-deals-drag.spec`) green on chromium.
