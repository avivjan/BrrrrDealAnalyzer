import { describe, expect, it } from 'vitest'

import { linkedConstructionAccountStatus } from '../test/fixtures/constructionAccountStatus'
import { checkTransfer, suggestedTransferAmount } from './constructionAccountTransferRules'

describe('the suggested amount', () => {
  it('a deposit is what is still to deposit, no more than the checking has', () => {
    expect(suggestedTransferAmount(linkedConstructionAccountStatus(), 'deposit')).toBe(5000)
    expect(suggestedTransferAmount(linkedConstructionAccountStatus({ primary_checking_available_balance_dollars: 3000 }), 'deposit')).toBe(3000)
  })

  it('a steal is safe to steal now; a close out is the whole available balance', () => {
    expect(suggestedTransferAmount(linkedConstructionAccountStatus(), 'steal')).toBe(20000)
    expect(suggestedTransferAmount(linkedConstructionAccountStatus(), 'close_out')).toBe(35000)
  })
})

describe('the checks before sending', () => {
  it('a deposit within every limit has no problem and no top-up', () => {
    expect(checkTransfer(linkedConstructionAccountStatus(), 'deposit', 5000)).toEqual({ blockingProblems: [], amountAboveSafeToStealDollars: 0 })
  })

  it('a steal above safe to steal names the top-up it will need, without blocking', () => {
    expect(checkTransfer(linkedConstructionAccountStatus(), 'steal', 25000)).toEqual({ blockingProblems: [], amountAboveSafeToStealDollars: 5000 })
  })

  it('blocks on the settings, the token, the account and the amount', () => {
    const problems = checkTransfer(linkedConstructionAccountStatus({
      in_app_transfers_are_enabled: false, has_a_transfer_token: false, closed_out_at: '2026-03-01T00:00:00Z',
      maximum_single_transfer_dollars: 1000, transfers_left_this_hour: 0,
    }), 'steal', 40000).blockingProblems
    expect(problems.join(' | ')).toContain('turned off')
    expect(problems.join(' | ')).toContain('MERCURY_TRANSFER_API_TOKEN_AJYK')
    expect(problems.join(' | ')).toContain('closed out')
    expect(problems.join(' | ')).toContain('$1,000 per-transfer maximum')
    expect(problems.join(' | ')).toContain('hourly transfer limit')
    expect(problems.join(' | ')).toContain('Only $35,000 is available in the construction account')
  })

  it('an empty or zero amount cannot be sent', () => {
    expect(checkTransfer(linkedConstructionAccountStatus(), 'deposit', 0).blockingProblems).toEqual(['Enter an amount above $0.'])
    expect(checkTransfer(linkedConstructionAccountStatus(), 'deposit', Number.NaN).blockingProblems).toEqual(['Enter an amount above $0.'])
  })
})
