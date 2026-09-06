# UI v2 follow-up prompt (drafted 2026-09-05 during the UI v1 overhaul; not part of the current plan)

Paste the block below as the opening prompt of a new session once `refactor/ui-overhaul` is merged.

```text
Enter plan mode and create a phased execution plan for "UI v2": a bold, futuristic,
enterprise-grade redesign of the BrrrrDealAnalyzer frontend (Vue 3 + Tailwind), the kind of
polish a large product-design org ships. Then execute it with the superpowers
subagent-driven-development skill.

WHAT MAY CHANGE
- Everything the user sees and how they interact: layout, information architecture, navigation
  (e.g. a persistent app shell/sidebar, command-style search, dashboard landing), typography,
  colour, depth, glass/gradient surfaces, iconography, empty states, modals, forms, tables,
  charts, micro-interactions and page/section choreography (GSAP). Templates and view scripts
  MAY be restructured. New presentational components are welcome.

WHAT MAY NOT CHANGE
- No backend change of any kind (BackEnd/**, request/response shapes, endpoints, payloads).
- Feature set and outcomes: every flow a user can complete today must still be completable
  with the same data written and the same requests sent. Prove it with the existing
  Functional Characterization Suite: Playwright network-contract goldens (frontend/e2e/golden),
  dialog copy, rendered result values, and the component contract tests. Behaviour is the
  contract, not code structure.
- Stores, API client, utils, router, types, config stay frozen (frontend/src/{stores,api,
  utils,router,types,config}).
- iOS Safari, Chrome on iPhone and desktop Chrome remain fully supported (4-project Playwright
  matrix + the real-device checklist in docs/ui-overhaul/device-checklist.md).

REUSE WHAT EXISTS (built by the UI v1 overhaul, branch refactor/ui-overhaul, tags ui-p0..ui-p5)
- Tokens (frontend/src/assets/tokens.css, Tailwind semantic keys), primitives
  (frontend/src/components/ui/Ui*.vue, docs/ui-overhaul/primitives.md), the motion layer
  (frontend/src/motion, UiTransition/UiTransitionGroup, v-reveal/v-press/v-hover-lift/v-flash),
  the gates (npm run verify:ui) and the design-system docs (design-system/brrrr-deal-analyzer).
- Gate policy for v2: keep G1 (backend), G2 (frozen logic dirs), G5/G7 (Playwright contract +
  axe), G6 (unit/build), G-HOVER, G8 (portable paths). RETIRE the structure-level gates G3
  (script freeze), G4 (binding manifest) and G4b (copy freeze) or downgrade them to advisory
  reports, because they forbid the layout and copy changes this redesign needs. Every
  data-testid hook must survive so the frozen e2e/contract suites keep selecting correctly;
  where a redesign genuinely needs a hook to move, update the spec in a dedicated
  "Golden update:" commit reviewed line by line.
- If a view's script needs to change for a UX change (e.g. a new navigation state), the change
  must be presentational state only (open/closed, selected tab, hover) and must not alter
  fetch triggers, debounces, watchers, submission logic or dialog copy.

DESIGN DIRECTION
- Run the ui-ux-pro-max design-system generator for "enterprise fintech analytics platform,
  futuristic, premium" with high variance and high motion, and adopt its output (it previously
  proposed hero-centric glassmorphism with a display serif; v1 rejected that for restraint —
  v2 embraces boldness). Deliver a MASTER.md with: dark-first or dual theme with a real toggle,
  layered depth (glass, glow, gradients used with contrast discipline), a display + body type
  pairing, a data-visualisation palette, iconography rules, motion tiers (Standard + Complex
  where it aids comprehension), and per-view page files.
- Accessibility floor stays WCAG 2.2 AA (4.5:1 text, 44 px primary touch targets, visible
  focus, reduced-motion honoured, no new axe violations).

DELIVERABLES OF THE PLAN
- Audit of v1's result and the FCS coverage gaps that v2 must close before restructuring
  (any flow the suite does not cover gets a characterization test first).
- Phases: 0 gate re-scoping + FCS gap-fill → 1 design system v2 (tokens/type/themes) →
  2 app shell + navigation → 3 views (one per task, boldest last) → 4 motion choreography →
  5 QA sweep (full FCS on all projects, axe, Lighthouse, real device) → final PR.
- Per-phase verification and rollback (phase tags), and the review cadence: reviews at phase
  ends rather than after every task (per-task reviews were the main cost of v1).
```

## Time estimate (from the v1 measured pace)
- Reviews and browser suite at phase ends (recommended): 18–26 h agent wall time.
- Per-task reviews and per-task browser suite (as v1): 32–45 h.
About half is the 12 view redesigns; design system + app shell ≈ a fifth; motion + QA the rest.
Main risk: with templates/scripts restructurable, only the test suites guard behaviour — Phase 0 must close the v1 suite's
coverage gaps first (chromium-only drag flows, skipped narrow-viewport liquidity cases, modal markup never scanned by axe).
