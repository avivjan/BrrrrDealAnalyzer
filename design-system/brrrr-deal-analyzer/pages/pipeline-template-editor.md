# Pipeline template editor — v2 page rules

> **PROJECT:** BRRRR Deal Analyzer · **UI v2** (docs/plans/2026-09-05-ui-v2-plan.md)
> Rules here override `MASTER.md`. Look-agnostic: they name tokens and primitives, never a look.

## Rules
- Editor on `UiModalPanel size="lg"`; stages as `UiSurface level=2` rows with a 44 px drag handle (`.stage-drag-handle` class kept), `UiIconButton`s with labels for the 15 icon-only actions; substages as `UiChip`s with remove buttons.
- `VueDraggable` children are never wrapped or animated. `pipeline.*` hooks unchanged.
