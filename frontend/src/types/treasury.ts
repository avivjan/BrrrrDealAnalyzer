// Mirrored from BackEnd/treasury/schemas — keep in sync.

export type SubBucketAssignment = 'Tax' | 'Insurance' | 'General Reserve' | null
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
  ins_bucket_balance: number
  ins_to_settle: number
  reserve_bucket_balance: number
  reserve_to_settle: number
  reserve_bucket_cap: number
  reserve_debt: number
  interest_earned_counter: number
  base_rent_target: number
  target_tax_allocation: number
  target_ins_allocation: number
  target_reserve_allocation: number
  force_tax_ins_accrual: boolean
  double_reserve_on_recovery: boolean
  created_at?: string | null
  updated_at?: string | null
}

export interface PropertyStatusCreate {
  llc_id: string
  property_name: string
  tax_bucket_balance?: number
  tax_to_settle?: number
  ins_bucket_balance?: number
  ins_to_settle?: number
  reserve_bucket_balance?: number
  reserve_to_settle?: number
  reserve_bucket_cap?: number
  reserve_debt?: number
  interest_earned_counter?: number
  base_rent_target?: number
  target_tax_allocation?: number
  target_ins_allocation?: number
  target_reserve_allocation?: number
  force_tax_ins_accrual?: boolean
  double_reserve_on_recovery?: boolean
}

export type PropertyStatusUpdate = Partial<
  Omit<PropertyStatus, 'property_id' | 'created_at' | 'updated_at'>
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
  'Insurance',
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
