# Link inspections to My Deals too (plan)

Task name `InspectionLinkToMyDeals`. The branch is `claude/relaxed-meitner-z0vzc9`, the session's only push branch. PR #109 (completion report) is still open on it, so this work joins that PR unless #109 is merged first. If it is, the branch restarts from `main` and gets a new PR.

## Context

Today an inspection can be linked only to a Bought Deal (`linked_bought_brrrr_deal_id` / `linked_bought_flip_deal_id`). The owner wants to link one to a deal on **My Deals** (the active pipeline, tables `active_deals` and `flip_deals`) as well. Houses are usually inspected *before* the purchase, while the deal is still on My Deals.

## Decisions (proposed)

| # | Decision |
|---|---|
| L1 | **Two more nullable foreign keys** on `property_inspections`: `linked_active_brrrr_deal_id` → `active_deals.id` and `linked_active_flip_deal_id` → `flip_deals.id`. Both are `ON DELETE SET NULL`. The check becomes "at most one of the four is set", so an inspection still belongs to at most one deal. The table already exists in production, so this needs a migration step: `migrations/steps/inspection_link_to_active_deals.py` adds the columns with `add_column_if_missing`, then swaps the check constraint. It is idempotent. |
| L2 | **API:** `PUT /inspections/{id}/deal-link` takes `deal_board: "my_deals" \| "bought"`, defaulting to `"bought"` so existing callers and the MCP tool keep working. The link response gains `deal_board`. New endpoints, behind login like the Bought ones: `GET` and `POST /active-deals/{deal_id}/inspections?deal_type=`. The `GET` lists a My Deals deal's inspections; the `POST` creates one already linked, with the address prefilled. The list of all inspections shows the board too. |
| L3 | **Moving to Bought carries the links.** "Move to Bought" (`POST /bought-deals/from-active/{id}`) re-points the source deal's inspections at the new Bought Deal in the same transaction. The inspection then shows on the Bought Deal, where the rest of the purchase is tracked. The My Deals copy stays as it is today. **Owner to confirm** (see the question below). |
| L4 | **Public responses are unchanged:** still only `linked: true/false`, never which deal or board. |
| L5 | **UI:** the "Link to deal" drawer gets a **My Deals / Bought** switch. Each list is searchable by address, from the already-authenticated `GET /active-deals` and `GET /bought-deals`. The My Deals deal window gets the same *Inspections* section as the Bought Deal window (the list plus **New inspection**), reusing `BoughtDealLinkedInspectionsSection`, renamed `DealLinkedInspectionsSection` with a `deal_board` prop. |
| L6 | **MCP:** the new routes become tools (`list_active_deal_inspections`, `create_inspection_for_active_deal`) with descriptions, and `link_inspection_to_deal` documents `deal_board`. |

## Todo (agent wall-clock)
- [x] **0** (5 min): Add this plan to the branch.
- [x] **1** (25 min): The model columns, the migration step (columns plus check-constraint swap), and its idempotency test.
- [x] **2** (30 min): BL and schemas: `deal_board` on link, link details, the list rows, and the active-deal list and create. The routes.
- [x] **3** (15 min): Move to Bought re-points the source deal's inspections.
- [x] **4** (10 min): **MCP support:** descriptions for the 2 new tools, the `link_inspection_to_deal` text, and tests.
- [x] **5** (35 min): Frontend: the board switch in the link drawer, `DealLinkedInspectionsSection` in the My Deals window and in the Bought window, the API client, and the types.
- [x] **6** (10 min): Regenerate the goldens; review the diff.
- [x] **7** (20 min): **Security task** (from `.claude/security.md`): *"Please check through all the code you just wrote and make sure it follows security best practices. make sure there are no sensitive information in the frontend and there are no vulnerabilities that can be exploited throughout all the code in this repo"*. Specific checks:
  - The new routes return 401 without a session.
  - Public responses still carry no deal data, from either board.
  - `deal_board` is validated.
  - Then bandit, pip-audit and npm audit.
- [x] **8** (10 min): README and the Review section.
- [ ] **9** (5 min): Push and update the PR; CI green.

## Tests
**Unit:** the check constraint refuses two links at once, and the migration step runs twice cleanly.

**Integration (pytest):**
- Link to a My Deals BRRRR deal and to a FLIP deal; unlink.
- Linking a missing deal → 404.
- `deal_board` defaults to `bought`.
- The new routes, and link/unlink, return 401 without a session.
- Public GET has no deal data when linked to My Deals.
- Deleting the My Deals deal clears the link.
- Moving to Bought re-points the link, and the Bought Deal lists the inspection.
- The list of all inspections shows the board.

**MCP:** link with `deal_board="my_deals"` through the tool; the new tools are listed.

**Frontend (Vitest):** the drawer switches boards and links the chosen deal, and the section renders for both boards.

**E2E:** the existing flows pass. A My Deals window flow checks the Inspections section: open a seeded deal, then **New inspection** lands on its walkthrough.

## Owner's answers (2026-10-28)
- On Move to Bought, the inspections **move to the new Bought Deal** (L3 as proposed).
- This work joins PR #109.

## Review

| Check | Result |
|---|---|
| Backend `pytest` | 1,255 passed, including `test_inspection_my_deals_link.py` (14) |
| Migration | The step runs on a database from before this change (adds the two columns, their foreign keys and indexes, and swaps the check), and is a no-op on a fresh one. It is idempotent (tested) |
| `verify_regression.py` | `openapi` and `schema` changed, inspection-only: the two columns, the two new routes, `deal_board`, and `bought_deal_id` → `deal_id` in the link request and response. Regenerated |
| Frontend `vitest` and build | 1,714 passed; the build passes |
| Playwright | All flows pass on Chromium. Opening a My Deals deal now also requests `GET /active-deals/{id}/inspections`. That is the only change in the four re-recorded goldens (`analyze-brrr-save`, `analyze-flip-save`, `deep-link-open`, `my-deals-modal-duplicate-delete`), committed alone as a `Golden update:` |
| Security | bandit and `npm audit --omit=dev` are clean |

**Deviations from the plan.**
1. **The link field is renamed** from `bought_deal_id` to `deal_id`, in both the request and the response, because it can now be a My Deals deal. The frontend and the MCP tool description changed with it. The frontend and backend deploy together; an MCP caller still sending `bought_deal_id` gets a 422 that names the field.
2. **One shared request per board** in the link drawer. Opening on the linked board used to fetch the list twice; a Vitest test caught it.

**Security notes.** The new routes are behind the normal gates (401 without a session, tested). `deal_board` is a closed `Literal` (422 otherwise). Public responses still carry only `linked`, tested for a My Deals link too.
