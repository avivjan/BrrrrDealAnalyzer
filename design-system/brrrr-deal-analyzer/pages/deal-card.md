# Deal card — v2 page rules

> **PROJECT:** BRRRR Deal Analyzer · **UI v2** (docs/plans/2026-09-05-ui-v2-plan.md)
> Rules here override `MASTER.md`. Look-agnostic: they name tokens and primitives, never a look.

## Rules
- `UiSurface interactive padding="sm"`; title `font-display text-base`; address `text-fg-muted text-sm`; figures `.numeric`; `UiBadge dealType`; progress as `UiProgressRing size=32` with `label`.
- Actions row top-right: `UiIconButton`s, `group-hover:opacity-100 touch:opacity-100`; `@click.stop` handlers unchanged; the card root stays a plain element (SortableJS drags it).
- Never a tone class as the only signal: positive/negative figures carry a sign.
