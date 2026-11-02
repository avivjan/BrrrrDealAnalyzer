import { describe, expect, it } from 'vitest'

import type { DealCashRowChange, LiquiditySeries, LiquidityTransaction } from '../types/liquidity'
import { buildDealImportInsights, transactionsAfterDealChanges } from './dealCashRowsPreview'

function change(overrides: Partial<DealCashRowChange>): DealCashRowChange {
  return {
    change_kind: 'added', item_key: 'cash_to_close_buy', occurrence_number: 1, description: 'Cash to close',
    transaction_id: null, date_before: null, date_after: '2026-12-01', amount_dollars_before: null, amount_dollars_after: -50000,
    deal_date_not_applied_because_you_changed_it: null, deal_amount_dollars_not_applied_because_you_changed_it: null,
    created_because_refi_is_late: false, ...overrides,
  }
}

function seriesOf(balances: Array<[string, number]>): LiquiditySeries {
  const days = balances.map(([date, balance_dollars]) => ({ date, balance_dollars, net_dollars: 0, transactions: [] }))
  const globalMin = Math.min(...balances.map(([, balance]) => balance))
  return { days, globalMin, globalMinDates: [], firstNegativeDate: days.find(day => day.balance_dollars < 0)?.date ?? null }
}

describe('transactionsAfterDealChanges', () => {
  const manualRow: LiquidityTransaction = { id: 'manual', effective_date: '2026-11-15', description: 'Rent', amount_dollars: 2000 }
  const importedRow: LiquidityTransaction = { id: 'imported', effective_date: '2026-12-01', description: 'HOA dues', amount_dollars: -100, source_item_key: 'hoa_dues' }
  const doneRow: LiquidityTransaction = { id: 'done', effective_date: '2026-10-01', description: 'EMD', amount_dollars: -5000, done_at: '2026-10-01T00:00:00Z' }
  const droppedRow: LiquidityTransaction = { id: 'dropped', effective_date: '2026-12-05', description: 'Survey', amount_dollars: -400 }

  it('replaces the deal rows, adds the new ones, drops the removed ones and keeps every other row', () => {
    const after = transactionsAfterDealChanges([manualRow, importedRow, doneRow, droppedRow], [
      change({ change_kind: 'updated', transaction_id: 'imported', item_key: 'hoa_dues', date_before: '2026-12-01', date_after: '2027-01-01', amount_dollars_before: -100, amount_dollars_after: -120, description: 'HOA dues' }),
      change({ change_kind: 'kept_done', transaction_id: 'done', item_key: 'earnest_money_deposit', date_after: '2026-10-01', amount_dollars_after: -5000 }),
      change({ change_kind: 'removed', transaction_id: 'dropped', item_key: 'survey_fee', date_after: null, amount_dollars_after: null }),
      change({ change_kind: 'added' }),
    ])
    expect(after.map(txn => [txn.id, txn.effective_date, txn.amount_dollars])).toEqual([
      ['manual', '2026-11-15', 2000],
      ['imported', '2027-01-01', -120],
      ['done', '2026-10-01', -5000],
      ['preview-cash_to_close_buy-1', '2026-12-01', -50000],
    ])
    expect(after.find(txn => txn.id === 'done')?.done_at).toBeTruthy()
  })
})

describe('buildDealImportInsights', () => {
  const today = '2026-11-01'
  const withoutTheDeal = seriesOf([['2026-10-31', 90000], ['2026-11-01', 90000], ['2026-11-15', 90000], ['2026-12-01', 90000], ['2027-01-02', 90000]])
  const withTheDeal = seriesOf([['2026-10-31', 90000], ['2026-11-01', 85000], ['2026-11-15', 30000], ['2026-12-01', 3000], ['2027-01-02', 60000]])
  const changes = [
    change({ item_key: 'earnest_money_deposit', date_after: '2026-10-20', amount_dollars_after: -5000 }),
    change({ item_key: 'cash_to_close_buy', date_after: '2026-11-15', amount_dollars_after: -55000 }),
    change({ item_key: 'hoa_dues', date_after: '2026-12-05', amount_dollars_after: -27000 }),
    change({ item_key: 'property_tax_bucket_balance_released_at_refi', date_after: '2027-01-01', amount_dollars_after: 57000 }),
    change({ change_kind: 'kept_done', item_key: 'survey_fee', date_after: '2026-09-01', amount_dollars_after: -400 }),
    change({ change_kind: 'removed', item_key: 'appliances', date_after: null, amount_dollars_after: null }),
  ]
  const insights = buildDealImportInsights(withoutTheDeal, withTheDeal, changes, 5000, today)

  it('compares the lowest balance from today on, with and without the deal', () => {
    expect(insights.lowestBalanceWithoutTheDeal).toEqual({ date: '2026-11-01', amountDollars: 90000 })
    expect(insights.lowestBalanceWithTheDeal).toEqual({ date: '2026-12-01', amountDollars: 3000 })
    expect(insights.firstNegativeDateWithTheDeal).toBeNull()
  })

  it('counts the days under the reserve and when the balance is back above it after the refi', () => {
    expect(insights.daysBelowReserveWithTheDeal).toBe(1)
    expect(insights.firstDateBelowReserveWithTheDeal).toBe('2026-12-01')
    expect(insights.lastDealRowDate).toBe('2027-01-01')
    expect(insights.dateBackAtOrAboveReserveAfterTheLastDealRow).toBe('2027-01-02')
  })

  it('totals only the rows that still move money; an overdue money-out row counts on today', () => {
    expect(insights.dealMoneyOutDollars).toBe(87000)
    expect(insights.dealMoneyInDollars).toBe(57000)
    expect(insights.dealMoneyOutInTheNext30DaysDollars).toBe(60000)
    expect(insights.largestSingleDayOutflowOfTheDeal).toEqual({ date: '2026-11-15', amountDollars: 55000 })
    expect(insights.cashTodayDollars).toBe(90000)
  })

  it('groups the rows by month', () => {
    expect(insights.dealRowsByMonth).toEqual([
      { month: '2026-10', rowCount: 1, netDollars: -5000 },
      { month: '2026-11', rowCount: 1, netDollars: -55000 },
      { month: '2026-12', rowCount: 1, netDollars: -27000 },
      { month: '2027-01', rowCount: 1, netDollars: 57000 },
    ])
  })
})
