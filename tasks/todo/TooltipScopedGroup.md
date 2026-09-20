# TooltipScopedGroup: the (i) tooltips open all at once while the pointer is over the deal form

Branch `TooltipScopedGroup` from `main` (e3153f4). Hotfix for a bug shipped by #70.

## Context

`DealInputsForm.vue`'s root carries Tailwind's plain `group` class (it lets the inset boxes read the
card/panel surface). `UiTooltip.vue` reveals its bubble with `group-hover:opacity-100` /
`group-focus-within:opacity-100`, and Tailwind's unnamed `group-*` variants match **any** ancestor
`.group`. Until #70 no tooltip lived inside that form; now every input has an (i), so hovering
anywhere over the form opens every bubble at once (screenshot from the owner).

## Fix (one component, naming only in CSS)

- `UiTooltip.vue`: scope the reveal to the tooltip's own root with a named group —
  `group/tooltip` on the root, `group-hover/tooltip:opacity-100`,
  `group-focus-within/tooltip:opacity-100`, `group-data-[open=true]/tooltip:opacity-100`,
  `touch:group-data-[open=true]/tooltip:block`. `touch:opacity-100` + `touch:hidden` stay (G-HOVER pair).
- `UiTooltip.test.ts`: assert the scoped class tokens.
- No other file changes; the form keeps its `group`.

## Todo
- [ ] T1 (5 min) `UiTooltip.vue` named group + test update.
- [ ] T2 (5 min) Tests: unit — `UiTooltip.test.ts` (scoped tokens, tap toggle); integration — `DealInputsForm.test.ts` already mounts every (i) and passes; E2E — none (Playwright untouched per owner).
- [ ] T3 (2 min) MCP: no endpoint or field change, nothing to add.
- [ ] T4 (3 min) Security (`.claude/security.md`): CSS-only change, no data, no new sinks; `npm audit` unchanged.
- [ ] T5 (5 min) `npm test`, `npm run build`; push; PR.
