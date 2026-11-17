import { describe, expect, it } from 'vitest'

import { linkedConstructionAccountStatus } from '../test/fixtures/constructionAccountStatus'
import { backToYouAtTheEndExplanation, safeToTakeOutNowExplanation, type FigureExplanationLine } from './constructionAccountFigureExplanations'
import { moneyBackToYouAtTheEndDollars } from './constructionAccountSummaryFigures'

const sumBySource = (total_dollars: number) => ({ from_the_bank_feed_dollars: total_dollars, before_this_account_dollars: 0, entered_by_hand_dollars: 0, total_dollars })

const lastLineOf = (lines: FigureExplanationLine[]) => lines[lines.length - 1]!

/** The lines before the result, applied in order, as the reader would add them up. */
function addedUp(lines: FigureExplanationLine[]): number {
  return lines.filter(line => line.operation !== 'result')
    .reduce((total, line) => line.operation === 'minus' ? total - line.amountDollars : total + line.amountDollars, 0)
}

/** 1640 Chateau, as on the owner's screen: $24,100 in the account, $52,900 of $73,000 drawn, $30,750 of $65,000 paid. */
const chateau = () => linkedConstructionAccountStatus({
  current_balance_dollars: 24100, available_balance_dollars: 24100, construction_budget_dollars: 73000, rehab_cost_dollars: 65000,
  loan_draws_pulled: sumBySource(52900), loan_draws_remaining_to_pull_dollars: 20100,
  rehab_payments_made: sumBySource(30750), unpaid_rehab_remaining_dollars: 34250,
  remaining_deposit_dollars: 0, projected_return_at_rehab_end_dollars: 9950, own_money_back_at_rehab_end_dollars: 5000,
  spread_at_rehab_end_dollars: 4950, safe_to_steal_now_dollars: 9950, safe_to_steal_now_is_capped_by: 'projected_return',
})

describe('Back to you at the end', () => {
  it('adds up, line by line, to the figure on the card', () => {
    const explanation = backToYouAtTheEndExplanation(chateau())
    const result = lastLineOf(explanation.lines)
    expect(result).toMatchObject({ operation: 'result', amountDollars: 9950 })
    expect(addedUp(explanation.lines)).toBe(9950)
    expect(explanation.lines[1]!.detail).toBe('$73,000 budget − $52,900 received')
    expect(explanation.lines[2]!.detail).toBe('$65,000 rehab − $30,750 paid')
    expect(explanation.footnote).toBe('Of it: your own money $5,000, and the budget spread $4,950.')
  })

  it('counts the deposit still owed, as the card does', () => {
    const status = { ...chateau(), remaining_deposit_dollars: 5000 }
    const explanation = backToYouAtTheEndExplanation(status)
    expect(explanation.lines.map(line => line.label)).toContain('The deposit you still owe')
    expect(addedUp(explanation.lines)).toBe(moneyBackToYouAtTheEndDollars(status))
    expect(lastLineOf(explanation.lines).amountDollars).toBe(14950)
  })

  it('a shortfall says how much to add', () => {
    const status = { ...chateau(), current_balance_dollars: 1000, projected_return_at_rehab_end_dollars: -13150 }
    const explanation = backToYouAtTheEndExplanation(status)
    expect(lastLineOf(explanation.lines)).toMatchObject({ label: 'Short: you need to add now', amountDollars: 13150 })
  })

  it('before an account is linked: the deposit plus what you keep under budget', () => {
    const status = linkedConstructionAccountStatus({ is_linked: false })
    const explanation = backToYouAtTheEndExplanation(status)
    expect(addedUp(explanation.lines)).toBe(moneyBackToYouAtTheEndDollars(status))
  })
})

describe('Safe to take out now', () => {
  it('the smaller of what is free now and what the account gives back, and which one limits it', () => {
    const explanation = safeToTakeOutNowExplanation(chateau())
    expect(explanation.lines.map(line => [line.label, line.amountDollars])).toEqual([
      ['Available in the account', 24100], ['What the account gives back at the end', 9950], ['Safe to take out now (the smaller of the two)', 9950],
    ])
    expect(explanation.footnote).toContain('what the account will give back at the end')
  })

  it('a buffer shows what is free after it', () => {
    const status = { ...chateau(), minimum_balance_to_keep_in_construction_account_dollars: 20000, safe_to_steal_now_dollars: 4100,
      safe_to_steal_now_is_capped_by: 'buffer_to_keep' as const }
    const explanation = safeToTakeOutNowExplanation(status)
    expect(explanation.lines.find(line => line.label === 'Free now')?.amountDollars).toBe(4100)
    expect(lastLineOf(explanation.lines).amountDollars).toBe(4100)
    expect(explanation.footnote).toContain('buffer')
  })

  it('a closed-out account has nothing to take out', () => {
    expect(lastLineOf(safeToTakeOutNowExplanation({ ...chateau(), closed_out_at: '2026-03-01T00:00:00Z' }).lines).amountDollars).toBe(0)
  })
})
