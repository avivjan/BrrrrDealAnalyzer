import { describe, expect, it } from 'vitest'

import { linkedConstructionAccountStatus } from '../test/fixtures/constructionAccountStatus'
import { constructionAccountDisplayRank, constructionAccountSummaryFiguresOf } from './constructionAccountSummaryFigures'

const sumBySource = (total_dollars: number) => ({ from_the_bank_feed_dollars: total_dollars, before_this_account_dollars: 0, entered_by_hand_dollars: 0, total_dollars })

describe('constructionAccountSummaryFiguresOf', () => {
  it('a linked account: the draws against the budget, the payments against the rehab cost, and what comes back', () => {
    const figures = constructionAccountSummaryFiguresOf(linkedConstructionAccountStatus({
      loan_draws_pulled: sumBySource(35000), rehab_payments_made: sumBySource(12500), needs_attention_because: ['deposit_due'],
    }))
    expect(figures.moneyInTheAccountDollars).toBe(35000)
    expect(figures.lenderDrawsReceivedOutOfLenderBudget).toEqual({ amountDollars: 35000, totalDollars: 70000, percentOfTotal: 50 })
    expect(figures.paidToContractorsOutOfRehabCost).toEqual({ amountDollars: 12500, totalDollars: 50000, percentOfTotal: 25 })
    expect(figures.rehabBudgetDifference).toEqual({ kind: 'under_budget_you_keep', dollars: 20000 })
    // $20,000 projected + the $5,000 deposit still to come, as the timeline's return row shows it.
    expect(figures.rehabEndOutcome).toEqual({ kind: 'back_to_you_at_the_end', dollars: 25000 })
    expect(figures.urgentAction).toEqual({ label: 'Deposit $5,000 due', tone: 'warning' })
  })

  it('not linked yet: the plan from the deal, no money in an account', () => {
    const figures = constructionAccountSummaryFiguresOf(linkedConstructionAccountStatus({ is_linked: false, current_balance_dollars: null, remaining_deposit_dollars: null }))
    expect(figures.moneyInTheAccountDollars).toBeNull()
    expect(figures.rehabEndOutcome).toEqual({ kind: 'back_to_you_at_the_end', dollars: 25000 })
  })

  it('over budget: what you cover', () => {
    const figures = constructionAccountSummaryFiguresOf(linkedConstructionAccountStatus({ original_steal_dollars: -3000 }))
    expect(figures.rehabBudgetDifference).toEqual({ kind: 'over_budget_you_cover', dollars: 3000 })
  })

  it('a top-up: what to add now, before anything else', () => {
    const figures = constructionAccountSummaryFiguresOf(linkedConstructionAccountStatus({
      top_up_needed_dollars: 1200, needs_attention_because: ['deposit_due', 'top_up_needed'],
    }))
    expect(figures.rehabEndOutcome).toEqual({ kind: 'you_need_to_add_now', dollars: 1200 })
    expect(figures.urgentAction).toEqual({ label: 'Add $1,200 now', tone: 'negative' })
  })

  it('bars stay between 0 and 100, and a zero budget is an empty bar', () => {
    expect(constructionAccountSummaryFiguresOf(linkedConstructionAccountStatus({ loan_draws_pulled: sumBySource(90000) }))
      .lenderDrawsReceivedOutOfLenderBudget.percentOfTotal).toBe(100)
    expect(constructionAccountSummaryFiguresOf(linkedConstructionAccountStatus({ rehab_payments_made: sumBySource(-500) }))
      .paidToContractorsOutOfRehabCost.percentOfTotal).toBe(0)
    expect(constructionAccountSummaryFiguresOf(linkedConstructionAccountStatus({ construction_budget_dollars: 0 }))
      .lenderDrawsReceivedOutOfLenderBudget.percentOfTotal).toBe(0)
  })

  it('a closed-out account asks for nothing', () => {
    const figures = constructionAccountSummaryFiguresOf(linkedConstructionAccountStatus({ closed_out_at: '2026-03-01T00:00:00Z', needs_attention_because: ['deposit_due'] }))
    expect(figures.urgentAction).toBeNull()
  })
})

describe('constructionAccountDisplayRank', () => {
  it('needing you, live, not linked, closed out', () => {
    expect(constructionAccountDisplayRank(linkedConstructionAccountStatus({ needs_attention_because: ['top_up_needed'] }))).toBe(0)
    expect(constructionAccountDisplayRank(linkedConstructionAccountStatus())).toBe(1)
    expect(constructionAccountDisplayRank(linkedConstructionAccountStatus({ is_linked: false }))).toBe(2)
    expect(constructionAccountDisplayRank(linkedConstructionAccountStatus({ closed_out_at: '2026-03-01T00:00:00Z' }))).toBe(3)
  })
})
