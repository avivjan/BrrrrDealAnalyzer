# ConstructionAccountCardExplanations: what's left, and "why this number" on the compact construction-account cards

On the PR #131 branch `DealDriveFolderRehabSummaryAndProjection` (as asked: everything on #131). Frontend only: every number already comes in the status the page loads.

## Context
On each closed card (`ConstructionAccountSummaryCard.vue`) the owner wants:
1. **Left to draw** under "Lender draws received": the lender budget not drawn yet (`loan_draws_remaining_to_pull_dollars`).
2. **Left to pay** under "Paid to contractors": the rehab cost not paid yet (`unpaid_rehab_remaining_dollars`).
3. An (i) on **"Back to you at the end"**, opened by hover or a tap, with a plain explanation and the calculation. For example, on 1640 Chateau:

   | Line | Amount |
   |---|---|
   | In the account now | $24,100 |
   | + Lender draws still to come | $20,100 ($73,000 budget − $52,900 received) |
   | − Rehab still to pay | $34,250 ($65,000 rehab − $30,750 paid) |
   | + The deposit you still owe | only when there is one |
   | **= Back to you at the end** | **$9,950** |

   Then "of it, your own money $X and the budget spread $Y". Before an account is linked, it shows "your deposit + what you keep under budget".
4. A new figure, **"Safe to take out now (steal)"**, with its own (i):

   | Line | Amount |
   |---|---|
   | Available in the account | $A |
   | − Always keep in the account (buffer) | $B |
   | = Free now | $C |
   | What the account gives back at the end | $D |
   | **Safe to take out now = the smaller of C and D, never below $0** | |

   Then one line saying which of the two limits it.

## Todo
- [x] Commit this plan on the branch (5 min)
- [x] `utils/constructionAccountFigureExplanations.ts`: pure functions that build both explanations (a summary sentence, the signed lines, the result) from a `ConstructionAccountStatus`. They use the same formulas as the backend projection (`construction_account_projection.py`), so the lines add up to the shown figure (45 min)
- [x] `ConstructionAccountFigureExplanation.vue`: an (i) button with a popover. It opens on hover and keyboard focus, and toggles on a tap (phones); it closes on Escape or a tap outside; `aria-describedby` / `aria-expanded` (45 min)
- [x] `ConstructionAccountSummaryCard.vue`:
  - the "left to draw" / "left to pay" lines under the bars;
  - the (i) on "Back to you at the end";
  - the new "Safe to take out now" figure with its (i), five columns on wide screens.

  The card's open/close button no longer wraps the numbers, so the (i) buttons are not nested inside a button (invalid HTML). The number area still opens the card on a mouse click, and the address row stays the keyboard toggle (1 h)
- [x] Docs: the README's Construction accounts line; check off this plan; push to PR #131 and add this to its description (15 min)

## Tests
- **Unit (vitest):**
  - the explanations add up to `moneyBackToYouAtTheEndDollars` and to `safe_to_steal_now_dollars` for: a live account, a deposit still owed, a top-up, not linked, and each of the three caps;
  - the card shows "left to draw" / "left to pay", and the new figure;
  - the (i) opens on a click, shows the lines, closes on Escape;
  - clicking an (i) does not open the card.
- **Integration:** none. No backend or API change.
- **E2E:** `construction-accounts.spec.ts`: the compact card shows "left to draw" and "left to pay"; the (i) of "Back to you at the end" shows the calculation; the a11y spec stays green.

**What I changed while building it:** the popover first opened on CSS hover and focus. On a phone it stayed open after a second tap or Escape, because the focus kept it open, and covered the next (i). It is now driven by state: a mouse hover, keyboard focus or a tap opens it; a second tap, Escape or a tap outside closes it. Checked in phone and desktop screenshots.

## MCP
No change: no new endpoint, and every figure is already in `list_liquidity_construction_accounts`.

## Security (`.claude/security.md`)
"Please check through all the code you just wrote and make sure it follows security best practices. make sure there are no sensitive information in the frontend and there are no vulnerabilities that can be exploited throughout all the code in this repo".
- Only numbers already on the page.
- Rendered as text: no `v-html`.
- No new request.
