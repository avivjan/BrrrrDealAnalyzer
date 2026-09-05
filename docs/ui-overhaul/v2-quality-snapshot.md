# UI v2 — quality snapshot (2026-09-06)

The state of the frontend at the end of UI v2 (`v2` branch, tag `ui-v2-p5`),
measured the same way v1's `quality-snapshot.md` measured the Phase 5 tree.
Numbers come from the gate run recorded in `docs/plans/2026-09-05-ui-v2-progress.md`.

## 1. Gates

| Gate | Result |
| --- | --- |
| G1 backend + root files vs `ui-baseline` | PASS |
| G2 `src/{stores,api,utils,router,types,config}` vs `ui-baseline` | PASS (byte-identical) |
| G3 / G4 / G4b | ADVISORY — __G3__ / __G4__ / __G4B__ findings (the redesign moved templates and copy on purpose) |
| G-HOVER | PASS |
| G8 absolute paths | PASS |
| G6 unit + build | PASS — __UNIT__ tests |
| G5 / G7 Playwright, 5 projects | PASS — __E2E__ |
| GOLDEN-POLICY | PASS — 18 `Golden update:` commits, all golden-only; network goldens unchanged |
| BACKEND | PASS |

## 2. Behaviour proof

- Network contracts (`e2e/golden/*.json`): **unchanged** since v1. No `Golden update:` commit in v2 touched a request golden.
- Dialog copy (`alert`/`confirm`): unchanged; the six flows that assert it pass on every project.
- Hooks: every `data-testid` the suite references exists (`src/test/hooks-inventory.test.ts`).
- Report comparison: `phase5-final.json` (v1 exit) → `v2-final.json`: __COMPARE__.

## 3. Accessibility

- Axe baseline keys: 6 routes (v1) + 13 (Phase 0: modals, seeded boards, 390 px) + 18 (Phase 2: 8 look × mode sets on the dashboard and liquidity, settings, palette). No key regressed; the two criticals the v1 baseline could not see — substage checkbox `label` (×2) and `mydeals.add-deal` `button-name` at 390 px — are **0**.
- Contrast: `npm run audit:contrast` — 340 pairs across 10 sets (base light/dark + 4 looks × 2 modes), including 7 wash pairs; all ≥ 4.5:1 text / 3:1 non-text.
- Landmarks: one `<main>` (the shell), one `<header>` (the topbar), labelled `<aside>`s, one `h1` per page, skip link.
- Touch: primary controls ≥ 44 px; bottom nav and drawer footer respect the home indicator.
- Motion: OS Reduce Motion and the in-app Motion setting both neutralise GSAP and CSS animation.

## 4. Performance

- Dashboard CLS with deals: **0.031** (v1: 0.138) — the portfolio strip renders inside a height-reserved slot.
- Fonts: Inter static; each look's display face is a lazy chunk loaded on first use of that look.
- Tempo budget: every entrance completes within 500 ms in every look (`e2e/checks/no-live-tweens.spec.ts`, `flows/deep-link-open.spec.ts`).

## 5. What is not measured here

- Lighthouse was not run in this session (no Chrome launcher available to the gate); CLS was measured with a `PerformanceObserver` in Playwright.
- The real-device checklist (`device-checklist.md`, "UI v2 additions") has not been ticked: Playwright's WebKit is not iOS Safari.
