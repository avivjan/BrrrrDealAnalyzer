import type { ConstructionAccountStatus } from '../../types/constructionAccount'

/** A linked construction account mid-rehab: budget $70,000, rehab $50,000, cushion $5,000 still to deposit. */
export function linkedConstructionAccountStatus(overrides: Partial<ConstructionAccountStatus> = {}): ConstructionAccountStatus {
  return {
    bought_deal_id: 'deal-1', deal_address: '12 Oak St', deal_updated_at: null, is_linked: true, is_in_the_liquidity_timeline: true,
    liquidity_rows_are_out_of_date: false, actual_rehab_cost_dollars: 50000, rehab_contingency_percent: 0, rehab_cost_dollars: 50000,
    construction_budget_dollars: 70000, original_steal_dollars: 20000, rehab_cushion_dollars: 5000, suggested_rehab_cushion_dollars: 5000,
    rehab_beyond_the_construction_budget_dollars: 0, total_to_deposit_dollars: 5000, purchase_closing_date: '2026-01-10',
    rehab_completed_date: '2026-02-24', rehab_completed_is_approved: false, refi_closing_date: '2026-04-10', refi_closed_is_approved: false,
    timeline_rows: [], appliances_dollars: 0, mercury_workspace_label: 'AJYK',
    construction_account: { mercury_account_id: 'construction', name: 'Oak rehab', account_number_last_four: '1234' },
    primary_checking_account: { mercury_account_id: 'checking', name: 'AJYK checking', account_number_last_four: '5678' },
    previous_construction_mercury_account_ids: [], amounts_as_of: '2026-02-01T12:00:00Z', mercury_is_unavailable: false,
    current_balance_dollars: 35000, available_balance_dollars: 35000, pending_money_in_dollars: 0, pending_money_out_dollars: 0,
    primary_checking_available_balance_dollars: 80000, loan_draws_pulled: null, loan_draws_remaining_to_pull_dollars: 35000,
    percent_of_the_construction_budget_pulled: 50, loan_draw_count: 1, last_loan_draw: null, rehab_payments_made: null,
    unpaid_rehab_remaining_dollars: 50000, percent_of_the_rehab_paid: 0, last_rehab_payment: null, rehab_paid_by_payee: [],
    own_money_transferred_into_the_account_dollars: 0, own_money_transferred_out_of_the_account_dollars: 0,
    own_money_still_in_the_account_dollars: 0, spread_already_taken_dollars: 0, remaining_deposit_dollars: 5000,
    minimum_balance_to_keep_in_construction_account_dollars: 0, projected_return_at_rehab_end_dollars: 20000,
    own_money_back_at_rehab_end_dollars: 0, spread_at_rehab_end_dollars: 20000, safe_to_steal_now_dollars: 20000,
    safe_to_steal_now_is_capped_by: 'projected_return', top_up_needed_dollars: 0,
    loan_draws_pulled_before_construction_account_dollars: 0, rehab_payments_made_before_construction_account_dollars: 0,
    transactions_counted_count: 1, transactions_ignored_count: 0, transactions_recategorised_count: 0,
    transactions_failed_or_cancelled_count: 0, last_transaction_date: '2026-01-15', marked_ready_for_close_out_at: null, closed_out_at: null,
    manual_adjustments: [], transfers_made_in_the_app: [], in_app_transfers_are_enabled: true, has_a_transfer_token: true,
    transfer_token_environment_variable_name: 'MERCURY_TRANSFER_API_TOKEN_AJYK', transfers_left_this_hour: 5,
    maximum_single_transfer_dollars: 100000, needs_attention_because: [],
    ...overrides,
  }
}
