/**
 * A construction account's state in one word, shown on its card and on the Bought deal card
 * (tasks/todo/ConstructionAccountPerRehab.md): the most urgent thing first.
 */
import type { ConstructionAccountStatus } from '../types/constructionAccount'

export interface ConstructionAccountState {
  label: 'Not linked' | 'Closed out' | 'Top-up needed' | 'Deposit due' | 'Live'
  tone: 'neutral' | 'positive' | 'warning' | 'negative'
}

export function constructionAccountStateOf(status: ConstructionAccountStatus): ConstructionAccountState {
  if (!status.is_linked) return { label: 'Not linked', tone: 'neutral' }
  if (status.closed_out_at) return { label: 'Closed out', tone: 'neutral' }
  if (status.needs_attention_because.includes('top_up_needed')) return { label: 'Top-up needed', tone: 'negative' }
  if (status.needs_attention_because.includes('deposit_due')) return { label: 'Deposit due', tone: 'warning' }
  return { label: 'Live', tone: 'positive' }
}
