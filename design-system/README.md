# Design system

`brrrr-deal-analyzer/MASTER.md` is the design-system reference for the UI overhaul: color, typography, spacing, motion, and component-spec tokens for the BRRRR Deal Analyzer frontend.
It was generated with the `ui-ux-pro-max` search script's `--design-system --persist` mode (`.claude/skills/ui-ux-pro-max-skill/src/ui-ux-pro-max/scripts/search.py`), then hand-annotated with the plan's verified domain queries and the approved overrides from the master plan's §2.
Within MASTER.md, the **"Approved overrides (plan §2, binding)"** section at the top always wins over the generic generated body below it wherever the two disagree — the generated body and its "Rejected tool output" note are kept for traceability only.
No frontend code or backend code changes with this file; it is documentation consumed by later Phase 1+ token-implementation tasks.
See `MASTER.md`'s own "Verified queries" section for how each domain-specific search result was checked against the app's actual needs before being applied.
