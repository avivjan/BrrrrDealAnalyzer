# REPS tracker (mount-only) — v2 page rules

> **PROJECT:** BRRRR Deal Analyzer · **UI v2** (docs/plans/2026-09-05-ui-v2-plan.md)
> Rules here override `MASTER.md`. Look-agnostic: they name tokens and primitives, never a look.

## Rules
- **Not redesigned in v2.** The only edits: root `min-h-dvh` → `min-h-full`, the view's own header loses `sticky top-0` (the shell topbar is sticky now), `reps.refresh` gets `min-h-11 min-w-11`. Everything under `components/reps/**` is untouched. `reps.*` hooks unchanged.
