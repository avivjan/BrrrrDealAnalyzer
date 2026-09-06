# Analyze deal — v2 page rules

> **PROJECT:** BRRRR Deal Analyzer · **UI v2** (docs/plans/2026-09-05-ui-v2-plan.md)
> Rules here override `MASTER.md`. Look-agnostic: they name tokens and primitives, never a look.

## Layout
- `lg+`: two columns `grid-cols-[minmax(0,1fr)_20rem]` — the form left, a sticky live summary rail right (`UiKpiCard`s for the headline outputs once results exist; empty state before). `<lg`: single column, rail below the form.
- Strategy switch (BRRRR / FLIP) as `UiSegmented`-styled `UiTabs` around the existing buttons (handlers unchanged), with the strategy colour token (`primary` for BRRRR, `warning` for FLIP) as a thin accent rule, never as the only signal.
- Form sections on `UiSurface level=1` with `UiSectionHeader`; the Rehab/Contingency pair keeps `data-layout`.
- Save modal: `UiModalPanel size="md"` on the existing overlay `div` (`@click.self` stays), fields in `UiField`.

## Accessibility musts
- The LTV slider gets an accessible name (v1 defect). Validation list `role="alert"`. Primary CTA ≥ 44 px.
- Hooks `analyze.*`, `form.*` unchanged; contract tests and `DealInputsForm.test.ts` unchanged.
