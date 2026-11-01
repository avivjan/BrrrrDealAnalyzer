/** All monetary amounts on the liquidity feature are in exact dollars (to the cent). */

export interface LiquidityTransaction {
  id: string
  effective_date: string // ISO date YYYY-MM-DD
  description: string
  /** Signed: positive = inflow, negative = outflow. In exact dollars. */
  amount_dollars: number
  created_at?: string
  updated_at?: string
  /**
   * Set on virtual transactions expanded from a recurring rule. The UI
   * keys edit/delete intent off this field to operate on the source rule
   * instead of the (non-persisted) instance.
   */
  recurring_rule_id?: string
  /** 0-based occurrence index within the rule. Only set when recurring_rule_id is set. */
  recurring_index?: number
}

export interface LiquidityTransactionCreate {
  effective_date: string
  description: string
  amount_dollars: number
}

export interface LiquidityTransactionUpdate {
  effective_date?: string
  description?: string
  amount_dollars?: number
}

/**
 * Supported repetition cadences. Each value pairs with `interval` to
 * produce the next-event date — e.g. `weekly + interval=2` == every two
 * weeks, `monthly + interval=3` == every quarter.
 *
 * Keep in sync with `LIQUIDITY_RECURRING_FREQUENCIES` on the backend.
 */
export type LiquidityRecurringFrequency =
  | 'daily'
  | 'weekly'
  | 'biweekly'
  | 'monthly'
  | 'quarterly'
  | 'yearly'

export interface LiquidityRecurringTransaction {
  id: string
  description: string
  /** Signed amount in exact dollars (positive=inflow, negative=outflow). */
  amount_dollars: number
  start_date: string
  end_date: string | null
  occurrences: number | null
  frequency: LiquidityRecurringFrequency
  interval: number
  created_at?: string
  updated_at?: string
}

export interface LiquidityRecurringTransactionCreate {
  description: string
  amount_dollars: number
  start_date: string
  end_date?: string | null
  occurrences?: number | null
  frequency: LiquidityRecurringFrequency
  interval: number
}

export interface LiquidityRecurringTransactionUpdate {
  description?: string
  amount_dollars?: number
  start_date?: string
  end_date?: string | null
  occurrences?: number | null
  frequency?: LiquidityRecurringFrequency
  interval?: number
}

export interface LiquiditySettings {
  opening_balance_dollars: number
  opening_balance_date: string // ISO date
  reserve_dollars: number
  /** The Mercury accounts whose balance is cash on hand; null = every active account. */
  mercury_account_ids_counted_as_cash?: string[] | null
  updated_at?: string
}

export interface LiquiditySettingsUpdate {
  opening_balance_dollars?: number
  opening_balance_date?: string
  reserve_dollars?: number
  /** Null = count every active account again. */
  mercury_account_ids_counted_as_cash?: string[] | null
}

export interface DayBucket {
  date: string // YYYY-MM-DD
  transactions: LiquidityTransaction[]
  net_dollars: number
  balance_dollars: number
}

export interface LiquiditySeries {
  days: DayBucket[]
  globalMin: number
  globalMinDates: string[]
  firstNegativeDate: string | null
}

export interface SimulationResult {
  min: number
  minDates: string[]
  firstNegativeDate: string | null
  negativeDates: string[]
  breachesReserve: boolean
  reserveBreachDates: string[]
}

export interface MercuryAccountSummary {
  id: string
  name: string
  type: string
  status: string
  current_balance_dollars: number
  available_balance_dollars: number
  workspace: string
  /** Whether this account's balance is cash on hand for the liquidity timeline (chosen in the settings). */
  is_counted_as_cash: boolean
}

export interface MercuryWorkspaceSummary {
  workspace: string
  total_balance_dollars: number
  total_available_dollars: number
  account_count: number
  accounts: MercuryAccountSummary[]
}

export interface MercuryWorkspaceError {
  workspace: string
  error: string
}

export interface MercuryBalanceResponse {
  total_balance_dollars: number
  total_available_dollars: number
  account_count: number
  workspace_count: number
  workspaces: MercuryWorkspaceSummary[]
  workspace_errors: MercuryWorkspaceError[]
  accounts: MercuryAccountSummary[]
  /** The balance the timeline anchors on: only the accounts counted as cash. */
  counted_as_cash_balance_dollars: number
  mercury_account_ids_counted_as_cash: string[] | null
}
