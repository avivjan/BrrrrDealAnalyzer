# Settings → Appearance — v2 page rules

> **PROJECT:** BRRRR Deal Analyzer · **UI v2** (docs/plans/2026-09-05-ui-v2-plan.md)
> Rules here override `MASTER.md`. Look-agnostic: they name tokens and primitives, never a look.

## Layout
- `UiDrawer side="right" size="md"`, `data-testid="shell.settings"`, heading "Appearance". Opened from the sidebar gear, the topbar and the palette ("Open settings").
- Sections in order: **Look**, **Mode**, **Motion**. Footer: "Saved automatically in this browser. Each browser keeps its own choice; a private window starts from the default."

## Components
- Look: `LookPicker` — `role="radiogroup" aria-label="Look"`, four `LookPreview` cards (`shell.look.<id>`, `role="radio" aria-checked`, arrow keys). Each card renders a static mock (sidebar strip, two KPI tiles, a primary button, a sparkline) inside an element carrying `data-look="<id>"` and `data-mode` matching the current mode, so every card shows its own look while another is active.
- Mode: `UiSegmented` Light / Dark / System (`shell.mode.<value>`, `aria-label="Mode"`).
- Motion: `UiSegmented` Full / Reduced (`shell.motion.<value>`, `aria-label="Motion"`).
- A polite live region announces "Look: Quiet Luxury · Dark" on change.

## Accessibility musts
- Choices apply instantly (no Save button) and persist via `theme.ts`; no request leaves the browser.
- Cards ≥ 44 px, visible focus ring, checked card also marked by an icon (never colour alone).
