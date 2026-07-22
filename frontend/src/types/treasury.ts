// Mirrored from BackEnd/treasury/schemas — keep in sync.

export type SubBucketAssignment = 'Tax' | 'General Reserve' | null
export type TransactionType =
  | 'Rent'
  | 'P&I'
  | 'Repair'
  | 'Emergency Advance'
  | 'Intercompany Loan'

export interface LLCConfiguration {
  llc_id: string
  llc_name: string
  checking_redline_buffer: number
  created_at?: string | null
  updated_at?: string | null
}

export interface LLCConfigurationCreate {
  llc_id?: string
  llc_name: string
  checking_redline_buffer?: number
}

export interface LLCConfigurationUpdate {
  llc_name?: string
  checking_redline_buffer?: number
}

export interface PropertyStatus {
  property_id: string
  llc_id: string
  property_name: string
  tax_bucket_balance: number
  tax_to_settle: number
  reserve_bucket_balance: number
  reserve_to_settle: number
  reserve_bucket_cap: number
  reserve_debt: number
  base_rent_target: number
  target_tax_allocation: number
  /** Explicit percentage input (e.g. 10.0 == 10% of rent to reserve). */
  precentage_of_rent_to_reserve: number
  /** Derived, read-only: base_rent_target * precentage_of_rent_to_reserve / 100. */
  target_reserve_allocation: number
  chase_reserves: boolean
  created_at?: string | null
  updated_at?: string | null
}

export interface PropertyStatusCreate {
  llc_id: string
  property_name: string
  tax_bucket_balance?: number
  tax_to_settle?: number
  reserve_bucket_balance?: number
  reserve_to_settle?: number
  reserve_bucket_cap?: number
  reserve_debt?: number
  base_rent_target?: number
  target_tax_allocation?: number
  precentage_of_rent_to_reserve?: number
  chase_reserves?: boolean
}

// `target_reserve_allocation` is derived server-side and never sent on writes.
export type PropertyStatusUpdate = Partial<
  Omit<PropertyStatus, 'property_id' | 'target_reserve_allocation' | 'created_at' | 'updated_at'>
>

export interface TransactionLedger {
  transaction_id: string
  property_id: string | null
  amount: number
  description: string
  timestamp: string
  is_real_bank_tx: boolean
  sub_bucket_assignment: SubBucketAssignment
  transaction_type: TransactionType
  settlement_batch_id: string | null
  created_at?: string | null
  updated_at?: string | null
}

export interface TransactionLedgerCreate {
  transaction_id?: string
  property_id?: string | null
  amount: number
  description: string
  timestamp: string
  is_real_bank_tx?: boolean
  sub_bucket_assignment?: SubBucketAssignment
  transaction_type: TransactionType
  settlement_batch_id?: string | null
}

export type TransactionLedgerUpdate = Partial<
  Omit<TransactionLedger, 'transaction_id' | 'created_at' | 'updated_at'>
> & { clear_property?: boolean }

export interface PropertyCashFlowHistory {
  history_id: string
  property_id: string
  month_year: string
  monthly_cash_flow: number
  cumulative_cash_flow: number
  created_at?: string | null
  updated_at?: string | null
}

export interface PropertyCashFlowHistoryCreate {
  history_id?: string
  property_id: string
  month_year: string
  monthly_cash_flow?: number
  cumulative_cash_flow?: number
}

export type PropertyCashFlowHistoryUpdate = Partial<
  Omit<PropertyCashFlowHistory, 'history_id' | 'property_id' | 'created_at' | 'updated_at'>
>

export const SUB_BUCKET_OPTIONS: Array<SubBucketAssignment | 'None'> = [
  'Tax',
  'General Reserve',
  'None',
]

export const TRANSACTION_TYPE_OPTIONS: TransactionType[] = [
  'Rent',
  'P&I',
  'Repair',
  'Emergency Advance',
  'Intercompany Loan',
]
