/** All monetary amounts on the liquidity feature are in $k (thousands of dollars). */

export interface LiquidityTransaction {
  id: string
  effective_date: string // ISO date YYYY-MM-DD
  description: string
  /** Signed: positive = inflow, negative = outflow. In $k. */
  amount_k: number
  created_at?: string
  updated_at?: string
}

export interface LiquidityTransactionCreate {
  effective_date: string
  description: string
  amount_k: number
}

export interface LiquidityTransactionUpdate {
  effective_date?: string
  description?: string
  amount_k?: number
}

export interface LiquiditySettings {
  opening_balance_k: number
  opening_balance_date: string // ISO date
  reserve_k: number
  updated_at?: string
}

export interface LiquiditySettingsUpdate {
  opening_balance_k?: number
  opening_balance_date?: string
  reserve_k?: number
}

export interface DayBucket {
  date: string // YYYY-MM-DD
  transactions: LiquidityTransaction[]
  net_k: number
  balance_k: number
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
