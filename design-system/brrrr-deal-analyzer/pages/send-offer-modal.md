# Send offer modal — v2 page rules

> **PROJECT:** BRRRR Deal Analyzer · **UI v2** (docs/plans/2026-09-05-ui-v2-plan.md)
> Rules here override `MASTER.md`. Look-agnostic: they name tokens and primitives, never a look.

## Rules
- `UiModalPanel size="md"` with `UiField`s; message banner tones via `UiBadge`/`UiSurface`; primary "Send" ≥ 44 px; the 1500 ms auto-close and form reset are untouched; enter-only motion (`modalEnterOnly`). `offer.*` hooks unchanged.
