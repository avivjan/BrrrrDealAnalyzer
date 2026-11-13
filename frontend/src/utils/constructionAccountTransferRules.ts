/**
 * What a Deposit, a Steal or a Close out may move, before anything is asked of Mercury
 * (tasks/todo/ConstructionAccountPerRehab.md, Step E). The server checks the same things again; these only let the
 * transfer window say so at once.
 */
import type { ConstructionAccountStatus } from '../types/constructionAccount'
import { formatMoney } from './money'

/** Close out = a Steal of the whole available balance, then the account is marked closed out. */
export type ConstructionAccountTransferKind = 'deposit' | 'steal' | 'close_out'

const roundToTheCent = (amount: number) => Math.round(amount * 100) / 100

/** Deposit: what is still to deposit, no more than the checking has. Steal: safe to steal now. Close out: everything. */
export function suggestedTransferAmount(status: ConstructionAccountStatus, kind: ConstructionAccountTransferKind): number {
  if (kind === 'deposit') {
    const remaining = status.remaining_deposit_dollars ?? 0
    const checkingAvailable = status.primary_checking_available_balance_dollars
    return roundToTheCent(Math.max(0, checkingAvailable == null ? remaining : Math.min(remaining, checkingAvailable)))
  }
  if (kind === 'steal') return roundToTheCent(Math.max(0, status.safe_to_steal_now_dollars ?? 0))
  return roundToTheCent(Math.max(0, status.available_balance_dollars ?? 0))
}

export interface ConstructionAccountTransferCheck {
  /** Reasons the transfer cannot be sent; empty = it can. */
  blockingProblems: string[]
  /** A Steal above safe to steal now: the top-up it will need, to confirm. 0 when not above. */
  amountAboveSafeToStealDollars: number
}

export function checkTransfer(status: ConstructionAccountStatus, kind: ConstructionAccountTransferKind, amountDollars: number): ConstructionAccountTransferCheck {
  const blockingProblems: string[] = []
  if (!status.in_app_transfers_are_enabled) blockingProblems.push('In-app transfers are turned off in the construction account settings.')
  if (!status.has_a_transfer_token) {
    blockingProblems.push(`No transfer token for this LLC: add ${status.transfer_token_environment_variable_name ?? 'its transfer token'} to the hosting secrets.`)
  }
  if (status.closed_out_at) blockingProblems.push('This construction account is closed out: reopen it first.')
  if (!(amountDollars > 0)) blockingProblems.push('Enter an amount above $0.')
  if (status.maximum_single_transfer_dollars != null && amountDollars > status.maximum_single_transfer_dollars) {
    blockingProblems.push(`Above the ${formatMoney(status.maximum_single_transfer_dollars)} per-transfer maximum in the settings.`)
  }
  if (status.transfers_left_this_hour === 0) blockingProblems.push('The hourly transfer limit is reached. Try again later.')
  const sourceAvailable = kind === 'deposit' ? status.primary_checking_available_balance_dollars : status.available_balance_dollars
  if (sourceAvailable != null && amountDollars > sourceAvailable) {
    blockingProblems.push(`Only ${formatMoney(sourceAvailable)} is available in ${kind === 'deposit' ? 'the checking account' : 'the construction account'}.`)
  }
  const safeToSteal = status.safe_to_steal_now_dollars ?? 0
  const amountAboveSafeToStealDollars = kind === 'deposit' ? 0 : roundToTheCent(Math.max(0, amountDollars - safeToSteal))
  return { blockingProblems, amountAboveSafeToStealDollars }
}
