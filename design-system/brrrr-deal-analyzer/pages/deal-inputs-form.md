# Deal inputs form — v2 page rules

> **PROJECT:** BRRRR Deal Analyzer · **UI v2** (docs/plans/2026-09-05-ui-v2-plan.md)
> Rules here override `MASTER.md`. Look-agnostic: they name tokens and primitives, never a look.

## Layout
- Fields in a responsive `grid-cols-1 md:grid-cols-2` with `UiField` wrappers; money inputs use `.numeric`; helper text in `text-fg-muted`; invalid state via `.ui-input-invalid` + `aria-describedby`.
- Section headers `UiSectionHeader as="h2"`; "Quick defaults" stays the **first** button (test contract).

## Accessibility musts
- Every control labelled (`for`/`id` via `useId`); slider handle ≥ 24 px, 44 px hit area; 16 px inputs on phones.
