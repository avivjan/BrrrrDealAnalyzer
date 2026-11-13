/**
 * A rehab's own Mercury construction account (tasks/todo/ConstructionAccountPerRehab.md). Mirrors
 * `BackEnd/ReqRes/common/liquidity_construction_account_schemas.py`. Every amount is exact dollars; a Mercury
 * account is named by its id, its name and the last four digits of its number (never the full number).
 */
import type { DealCashRowChanges, UseDealValueForField } from './liquidity'

export type ConstructionAccountManualAdjustmentType = 'manual_payment' | 'manual_draw'
export type ConstructionAccountTransactionCategory = 'loan_draw' | 'rehab_payment' | 'own_money'
export type SafeToStealCap = 'available_balance' | 'buffer_to_keep' | 'projected_return'
export type ConstructionAccountAttentionReason = 'deposit_due' | 'top_up_needed' | 'mercury_unavailable'

export interface MercuryAccountName {
  mercury_account_id: string
  name: string
  account_number_last_four: string
}

/** One sum and where it comes from: the bank feed, the amount before this account, and what you entered by hand. */
export interface ConstructionAccountSumBySource {
  from_the_bank_feed_dollars: number
  before_this_account_dollars: number
  entered_by_hand_dollars: number
  total_dollars: number
}

export interface ConstructionAccountDatedAmount {
  date: string
  amount_dollars: number
  counterparty_name: string
}

export interface ConstructionAccountPayeeTotal {
  payee_name: string
  amount_dollars: number
}

export interface ConstructionAccountTimelineRow {
  item_key: string
  transaction_id: string
  description: string
  effective_date: string
  amount_dollars: number
  is_done: boolean
  is_overdue: boolean
}

export interface ConstructionAccountManualAdjustment {
  id: string
  adjustment_type: ConstructionAccountManualAdjustmentType
  amount_dollars: number
  date: string
  note: string | null
}

/** One Bought BRRRR deal on the Construction Accounts page. The fields after `appliances_dollars` are null until an account is linked. */
export interface ConstructionAccountStatus {
  bought_deal_id: string
  deal_address: string
  deal_updated_at: string | null
  is_linked: boolean
  is_in_the_liquidity_timeline: boolean
  liquidity_rows_are_out_of_date: boolean
  actual_rehab_cost_dollars: number
  rehab_contingency_percent: number
  rehab_cost_dollars: number
  construction_budget_dollars: number
  original_steal_dollars: number
  rehab_cushion_dollars: number
  suggested_rehab_cushion_dollars: number
  rehab_beyond_the_construction_budget_dollars: number
  total_to_deposit_dollars: number
  purchase_closing_date: string
  rehab_completed_date: string
  rehab_completed_is_approved: boolean
  refi_closing_date: string
  refi_closed_is_approved: boolean
  timeline_rows: ConstructionAccountTimelineRow[]
  appliances_dollars: number
  mercury_workspace_label: string | null
  construction_account: MercuryAccountName | null
  primary_checking_account: MercuryAccountName | null
  previous_construction_mercury_account_ids: string[]
  amounts_as_of: string | null
  mercury_is_unavailable: boolean
  current_balance_dollars: number | null
  available_balance_dollars: number | null
  pending_money_in_dollars: number | null
  pending_money_out_dollars: number | null
  primary_checking_available_balance_dollars: number | null
  loan_draws_pulled: ConstructionAccountSumBySource | null
  loan_draws_remaining_to_pull_dollars: number | null
  percent_of_the_construction_budget_pulled: number | null
  loan_draw_count: number | null
  last_loan_draw: ConstructionAccountDatedAmount | null
  rehab_payments_made: ConstructionAccountSumBySource | null
  unpaid_rehab_remaining_dollars: number | null
  percent_of_the_rehab_paid: number | null
  last_rehab_payment: ConstructionAccountDatedAmount | null
  rehab_paid_by_payee: ConstructionAccountPayeeTotal[]
  own_money_transferred_into_the_account_dollars: number | null
  own_money_transferred_out_of_the_account_dollars: number | null
  own_money_still_in_the_account_dollars: number | null
  spread_already_taken_dollars: number | null
  remaining_deposit_dollars: number | null
  minimum_balance_to_keep_in_construction_account_dollars: number | null
  projected_return_at_rehab_end_dollars: number | null
  own_money_back_at_rehab_end_dollars: number | null
  spread_at_rehab_end_dollars: number | null
  safe_to_steal_now_dollars: number | null
  safe_to_steal_now_is_capped_by: SafeToStealCap | null
  top_up_needed_dollars: number | null
  loan_draws_pulled_before_construction_account_dollars: number | null
  rehab_payments_made_before_construction_account_dollars: number | null
  transactions_counted_count: number | null
  transactions_ignored_count: number | null
  transactions_recategorised_count: number | null
  transactions_failed_or_cancelled_count: number | null
  last_transaction_date: string | null
  marked_ready_for_close_out_at: string | null
  closed_out_at: string | null
  manual_adjustments: ConstructionAccountManualAdjustment[]
  transfers_made_in_the_app: ConstructionAccountTransfer[]
  in_app_transfers_are_enabled: boolean
  has_a_transfer_token: boolean
  transfer_token_environment_variable_name: string | null
  transfers_left_this_hour: number | null
  maximum_single_transfer_dollars: number | null
  needs_attention_because: ConstructionAccountAttentionReason[]
}

export type ConstructionAccountTransferDirection = 'deposit_into_construction_account' | 'steal_to_primary_checking'
export type ConstructionAccountTransferOutcome =
  | 'being_sent' | 'accepted_by_mercury' | 'refused_by_mercury' | 'mercury_did_not_answer' | 'failed_or_cancelled_at_mercury'

/** A Deposit or a Steal the app asked Mercury to make (tasks/todo/ConstructionAccountPerRehab.md, Step E). */
export interface ConstructionAccountTransfer {
  transfer_id: string
  transfer_direction: ConstructionAccountTransferDirection
  amount_dollars: number
  transfer_outcome: ConstructionAccountTransferOutcome
  mercury_transfer_status: string | null
  requested_at: string
  is_in_the_bank_feed: boolean
}

/** The accounts always come from the stored link: a transfer names only its amount and its key. */
export interface ConstructionAccountTransferReq {
  amount_dollars: number
  idempotency_key: string
  confirm_amount_exceeds_safe_to_steal?: boolean
}

export interface ConstructionAccountTotals {
  linked_account_count: number
  current_balance_dollars: number
  projected_return_at_rehab_end_dollars: number
  safe_to_steal_now_dollars: number
  remaining_deposit_dollars: number
  top_up_needed_dollars: number
  accounts_needing_attention_count: number
}

export interface ConstructionAccountList {
  totals: ConstructionAccountTotals
  accounts: ConstructionAccountStatus[]
}

/** The answer of every write. With `was_preview_only`, nothing was saved: it is what Confirm would do. */
export interface ConstructionAccountWriteResult {
  was_preview_only: boolean
  status_before: ConstructionAccountStatus
  status_after: ConstructionAccountStatus
  changes_the_liquidity_timeline: boolean
  liquidity_row_changes: DealCashRowChanges | null
  row_descriptions_marked_done: string[]
  balance_left_in_the_account_dollars: number | null
}

/** A Deposit or a Steal: the write's answer and the transfer (null for a preview: nothing was asked of Mercury). */
export interface ConstructionAccountTransferWriteResult extends ConstructionAccountWriteResult {
  transfer: ConstructionAccountTransfer | null
}

export interface ConstructionAccountLinkReq {
  construction_mercury_account_id: string
  primary_checking_mercury_account_id: string
  loan_draws_pulled_before_construction_account_dollars: number
  rehab_payments_made_before_construction_account_dollars: number
  minimum_balance_to_keep_in_construction_account_dollars: number
}

export interface ConstructionAccountRehabFiguresReq {
  actual_rehab_cost_dollars?: number
  rehab_contingency_percent?: number
  construction_budget_dollars?: number
  rehab_cushion_dollars?: number
}

export interface ConstructionAccountSwitchReq {
  new_construction_mercury_account_id: string
  loan_draws_pulled_before_construction_account_dollars: number
  rehab_payments_made_before_construction_account_dollars: number
}

export interface ConstructionAccountSwitchPreview {
  old_construction_account_balance_dollars: number
  old_account_must_be_emptied_first: boolean
  loan_draws_pulled_before_construction_account_dollars: number
  rehab_payments_made_before_construction_account_dollars: number
}

export interface ConstructionAccountManualAdjustmentReq {
  adjustment_type: ConstructionAccountManualAdjustmentType
  amount_dollars: number
  date: string
  note?: string | null
}

export interface ConstructionAccountTransactionOverrideReq {
  ignored: boolean
  category_override: ConstructionAccountTransactionCategory | null
  note?: string | null
}

export interface ConstructionAccountTransaction {
  mercury_transaction_id: string
  transaction_date: string | null
  counterparty_name: string
  signed_amount_dollars: number
  bank_status: string
  is_pending: boolean
  automatic_category: ConstructionAccountTransactionCategory
  ignored: boolean
  category_override: ConstructionAccountTransactionCategory | null
  note: string | null
  effective_category: ConstructionAccountTransactionCategory | null
}

export interface ConstructionAccountRefreshResult {
  refreshed_deal_count: number
  changed_row_count: number
  mercury_is_unavailable: boolean
  next_mercury_read_not_before: string | null
  cash_balance_changed: boolean
  construction_accounts_changed: boolean
  cash_balance_last_changed_at: string | null
  construction_accounts_last_changed_at: string | null
  bank_reported_row_changes: DealCashRowChanges[]
}

export interface MercuryLastChange {
  last_changed_at: string | null
  cash_balance_last_changed_at: string | null
  construction_accounts_last_changed_at: string | null
  /** When a Mercury event (instant updates) last changed timeline rows, and which: the "updated from the bank" window. */
  last_instant_update_at?: string | null
  bank_reported_row_changes_of_last_instant_update?: DealCashRowChanges[]
}

export interface MercuryWorkspaceConnection {
  mercury_workspace_label: string
  has_read_token: boolean
  has_transfer_token: boolean
  read_token_environment_variable_name: string
  transfer_token_environment_variable_name: string
  instant_updates_are_on: boolean
  last_valid_event_received_at: string | null
  last_webhook_error_message: string | null
  last_webhook_error_at: string | null
  next_mercury_read_not_before: string | null
}

export interface MercuryConnectionStatus {
  workspaces: MercuryWorkspaceConnection[]
  read_token_environment_variable_name_pattern: string
  transfer_token_environment_variable_name_pattern: string
}

/** Every write's options: preview it (save nothing), the browser's date, and the rows that take the new value anyway. */
export interface ConstructionAccountWriteOptions {
  previewOnly?: boolean
  today?: string
  useTheNewValueFor?: UseDealValueForField[]
}
