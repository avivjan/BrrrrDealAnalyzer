# App shell — v2 page rules

> **PROJECT:** BRRRR Deal Analyzer · **UI v2** (docs/plans/2026-09-05-ui-v2-plan.md)
> Rules here override `MASTER.md`. Look-agnostic: they name tokens and primitives, never a look.

## Layout
- Desktop (`lg+`): CSS grid `grid-cols-[var(--sidebar-w)_1fr] grid-rows-[auto_1fr] h-dvh`. Sidebar spans both rows; topbar row 1; `<main id="main" class="min-h-0 overflow-y-auto">` row 2 is the **only page scroller**. Sidebar collapse changes `--sidebar-w` on the root **without a transition** (the liquidity chart's ResizeObserver must never see an animated ancestor).
- Mobile (`<lg`): single column. Sticky topbar (`pt-safe-t`, height `--topbar-h`), fixed bottom nav (`pb-safe-b`, 5 routes + "More" → Settings), `<main>` padded `pb-[calc(4rem+env(safe-area-inset-bottom))]`.
- The topbar is mounted on **every route**, including `/reps`.

## Hierarchy
- Sidebar: wordmark (`font-display`), primary nav (`<nav aria-label="Primary">`, `aria-current="page"`, active item with `shadow-glow-primary` and a sliding indicator `data-part="active-indicator"`), footer gear (`shell.settings-open`).
- Topbar: view title `h1` (`font-display tracking-display`), then `CommandTrigger` ("Search… ⌘K"), `ThemeToggle`, `SettingsTrigger`, `ConnectionStatus` (`app.status`, `role="status"`, same three strings as v1, visible label on `lg`).
- Surfaces: sidebar and topbar are `UiGlassPanel` containers (Glass rule: text sits on inner surfaces or is a nav label on `bg-surface` items).

## Accessibility musts
- One `<main>` per page (fixes the v1 `landmark-one-main` findings); one `<header>` (the topbar) — views no longer render their own `<header>` landmark.
- Skip link "Skip to content" → `#main`, first in DOM.
- Every nav item ≥ 44 px on touch; icon-only state (collapsed sidebar) keeps `aria-label`.
- `Cmd/Ctrl+K` opens the palette; Escape closes drawer and palette; focus returns to the trigger.
