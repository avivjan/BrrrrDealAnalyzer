# Property inspection walkthrough: page rules

> **PROJECT:** BRRRR Deal Analyzer · tasks/todo/PropertyInspection.md
> Rules here override `MASTER.md`. Look-agnostic: they name tokens and primitives, never a look.

## Concept: "Walkthrough"
A premium field app, played like levels rather than filled in like a form. The walkthrough is used on an iPad or a phone, standing in a house, often with one hand. It must stay fast: every action takes one or two taps.

## Structure
- **Level map** (`/inspections/:id`): one tile per checklist section ("level"). Each tile has:
  - a `UiProgressRing` (size 56) and an "n / m checked" count, in `.numeric`;
  - a wrapping row of item chips. Each chip is at least 48 px tall and carries the status icon; CRITICAL items carry a small "Critical" badge.
- **Sticky header** across the map and cards:
  - the address, in `font-display`;
  - a 6 px overall progress bar in `bg-primary`;
  - the **Missions left** pill (count of CRITICAL items still unchecked);
  - the save state (`UiSaveStatus`): "Saving…", "Saved", or "Offline · n queued".
- **Item card** (`/inspections/:id/items/:key`): one item per screen.
  - Questions are revealed one at a time: status → each field (follow-ups only when relevant) → photos and notes.
  - An answered question collapses to a one-line answer; tapping it reopens the question.
  - A bottom bar holds ◀ / ▶ (at least 56 px) and "Map".
- **Summary** (`/inspections/:id/summary`): start info, then Replace items, Repair items, windows to replace, then OK items (collapsed), then a Share button.

## Status colours (always with an icon, never colour alone)
- OK: `positive`, `pi-check`
- Repair: `warning`, `pi-wrench`
- Replace: `negative`, `pi-refresh`
- Not checked: `fg-muted`, `pi-circle`

## Tap targets
- At least 44 px everywhere.
- Status buttons and steppers: at least 56 px.
- The window counter's −/+ buttons: 72 px.

## Motion (CSS only, so the `main.css` reduced-motion neutraliser governs all of it)
- Question reveal: 180 ms fade and 8 px rise.
- Card change: 220 ms slide of 24 px, in the direction of travel.
- Level cleared: a ≤500 ms ring pulse plus a burst of 10 token-coloured dots, and a toast.
- Finish: a full-screen panel. The stats count up through `v-count-up`, which already respects reduced motion.
- Swipe: horizontal pointer drag of at least 60 px, mostly horizontal. A vertical scroll never counts as a swipe.

## Hooks
Every interactive element has `data-testid="inspection.<area>.<thing>"`. For example: `inspection.card.status.ok`, `inspection.card.next`, `inspection.map.item.roof`, `inspection.finish`.
