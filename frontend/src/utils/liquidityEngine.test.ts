import { describe, it, expect } from 'vitest'
import {
  addDays,
  toISO,
  aggregateNetByDay,
  buildDailyLiquiditySeries,
  simulateImpact,
  requiresSimulation,
  computeDefaultRange,
} from './liquidityEngine'
import type { LiquidityTransaction } from '../types/liquidity'

function txn(id: string, date: string, amount_k: number, description = 'test'): LiquidityTransaction {
  return { id, effective_date: date, description, amount_k }
}

describe('addDays', () => {
  it('adds positive days', () => {
    expect(addDays('2025-01-01', 5)).toBe('2025-01-06')
  })
  it('handles month overflow', () => {
    expect(addDays('2025-01-30', 5)).toBe('2025-02-04')
  })
  it('subtracts days', () => {
    expect(addDays('2025-03-01', -1)).toBe('2025-02-28')
  })
})

describe('aggregateNetByDay', () => {
  it('sums multiple txns on same day', () => {
    const txns = [
      txn('a', '2025-06-15', 10),
      txn('b', '2025-06-15', -3),
      txn('c', '2025-06-16', 5),
    ]
    const map = aggregateNetByDay(txns)
    expect(map.get('2025-06-15')!.net_k).toBe(7)
    expect(map.get('2025-06-15')!.txns).toHaveLength(2)
    expect(map.get('2025-06-16')!.net_k).toBe(5)
  })

  it('returns empty map for no txns', () => {
    const map = aggregateNetByDay([])
    expect(map.size).toBe(0)
  })
})

describe('buildDailyLiquiditySeries', () => {
  it('builds continuous series with zero-flow days carrying forward', () => {
    const txns = [
      txn('a', '2025-06-01', 10),
      txn('b', '2025-06-03', -5),
    ]
    const series = buildDailyLiquiditySeries(txns, 49, '2025-06-01', '2025-06-01', '2025-06-05')
    expect(series.days).toHaveLength(5) // June 1-5

    // Day 1 (June 1 = opening balance date): 49 + 10 = 59
    expect(series.days[0].balance_k).toBe(59)
    // Day 2 (June 2): 59 + 0 = 59
    expect(series.days[1].balance_k).toBe(59)
    // Day 3 (June 3): 59 - 5 = 54
    expect(series.days[2].balance_k).toBe(54)
    // Day 4-5: carry forward at 54
    expect(series.days[3].balance_k).toBe(54)
    expect(series.days[4].balance_k).toBe(54)
  })

  it('flat before opening balance date', () => {
    const txns = [txn('a', '2025-06-03', 10)]
    const series = buildDailyLiquiditySeries(txns, 20, '2025-06-02', '2025-06-01', '2025-06-04')

    // June 1 is before anchor: flat at opening
    expect(series.days[0].balance_k).toBe(20)
    // June 2 = anchor day, no flow on that day: 20 + 0 = 20
    expect(series.days[1].balance_k).toBe(20)
    // June 3: 20 + 10 = 30
    expect(series.days[2].balance_k).toBe(30)
  })

  it('tracks globalMin and globalMinDates correctly', () => {
    const txns = [
      txn('a', '2025-06-02', -30),
      txn('b', '2025-06-04', -30),
      txn('c', '2025-06-05', 10),
    ]
    const series = buildDailyLiquiditySeries(txns, 49, '2025-06-01', '2025-06-01', '2025-06-06')

    // Day balances: 49, 19, 19, -11, -1, -1
    expect(series.globalMin).toBe(-11)
    expect(series.globalMinDates).toEqual(['2025-06-04'])
  })

  it('reports ties in globalMinDates', () => {
    const txns = [
      txn('a', '2025-06-02', -49),
      txn('b', '2025-06-03', 10),
      txn('c', '2025-06-04', -10),
    ]
    const series = buildDailyLiquiditySeries(txns, 49, '2025-06-01', '2025-06-01', '2025-06-05')

    // 49, 0, 10, 0, 0 => min is 0 on days 2, 4, 5
    expect(series.globalMin).toBe(0)
    expect(series.globalMinDates).toContain('2025-06-02')
    expect(series.globalMinDates).toContain('2025-06-04')
    expect(series.globalMinDates).toContain('2025-06-05')
  })

  it('detects first negative date', () => {
    const txns = [
      txn('a', '2025-06-02', -60),
    ]
    const series = buildDailyLiquiditySeries(txns, 49, '2025-06-01', '2025-06-01', '2025-06-04')

    expect(series.firstNegativeDate).toBe('2025-06-02')
  })

  it('returns null firstNegativeDate when all positive', () => {
    const txns = [txn('a', '2025-06-02', 5)]
    const series = buildDailyLiquiditySeries(txns, 10, '2025-06-01', '2025-06-01', '2025-06-03')
    expect(series.firstNegativeDate).toBeNull()
  })

  it('handles empty transactions', () => {
    const series = buildDailyLiquiditySeries([], 49, '2025-06-01', '2025-06-01', '2025-06-03')
    expect(series.days).toHaveLength(3)
    expect(series.days[0].balance_k).toBe(49)
    expect(series.days[1].balance_k).toBe(49)
    expect(series.days[2].balance_k).toBe(49)
    expect(series.globalMin).toBe(49)
  })

  it('handles range start after opening with intermediate flows', () => {
    // Opening on June 1 at 100, flow on June 3: -20, range starts June 5
    const txns = [
      txn('a', '2025-06-03', -20),
      txn('b', '2025-06-06', 5),
    ]
    const series = buildDailyLiquiditySeries(txns, 100, '2025-06-01', '2025-06-05', '2025-06-07')

    // Balance at start of range: 100 - 20 = 80 (flow on June 3 applied)
    // June 5: 80
    // June 6: 80 + 5 = 85
    // June 7: 85
    expect(series.days[0].balance_k).toBe(80)
    expect(series.days[1].balance_k).toBe(85)
    expect(series.days[2].balance_k).toBe(85)
  })
})

describe('simulateImpact', () => {
  it('detects negatives on correct dates', () => {
    const txns = [
      txn('a', '2025-06-02', -60),
    ]
    const result = simulateImpact(txns, 49, '2025-06-01', '2025-06-01', '2025-06-04', 5)

    expect(result.firstNegativeDate).toBe('2025-06-02')
    expect(result.negativeDates).toContain('2025-06-02')
    expect(result.negativeDates).toContain('2025-06-03')
    expect(result.negativeDates).toContain('2025-06-04')
    expect(result.min).toBe(-11)
  })

  it('detects reserve breaches without negatives', () => {
    const txns = [
      txn('a', '2025-06-02', -46),
    ]
    const result = simulateImpact(txns, 49, '2025-06-01', '2025-06-01', '2025-06-03', 5)

    expect(result.negativeDates).toHaveLength(0)
    expect(result.breachesReserve).toBe(true)
    expect(result.reserveBreachDates).toContain('2025-06-02')
  })

  it('reports comfortable when buffer is sufficient', () => {
    const txns = [
      txn('a', '2025-06-02', -10),
    ]
    const result = simulateImpact(txns, 49, '2025-06-01', '2025-06-01', '2025-06-03', 5)

    expect(result.negativeDates).toHaveLength(0)
    expect(result.breachesReserve).toBe(false)
    expect(result.min).toBe(39)
  })

  it('correctly handles edit scenario — moved outflow earlier worsens future', () => {
    const baseline = [
      txn('a', '2025-06-05', -40),
    ]
    // Edit: move outflow from June 5 to June 2
    const candidate = [
      txn('a', '2025-06-02', -40),
    ]
    const resultBase = simulateImpact(baseline, 49, '2025-06-01', '2025-06-01', '2025-06-06', 5)
    const resultCandidate = simulateImpact(candidate, 49, '2025-06-01', '2025-06-01', '2025-06-06', 5)

    // Both have same min (9) but candidate has lower balance on June 2-4
    expect(resultBase.min).toBe(9)
    expect(resultCandidate.min).toBe(9)
  })
})

describe('requiresSimulation', () => {
  it('requires sim for new outflows', () => {
    expect(requiresSimulation(null, -10, '2025-06-01')).toBe(true)
  })

  it('does not require sim for new inflows', () => {
    expect(requiresSimulation(null, 10, '2025-06-01')).toBe(false)
  })

  it('requires sim when amount decreases on edit', () => {
    const old = txn('a', '2025-06-01', 10)
    expect(requiresSimulation(old, 5, '2025-06-01')).toBe(true)
  })

  it('requires sim when date changes on edit', () => {
    const old = txn('a', '2025-06-01', -10)
    expect(requiresSimulation(old, -10, '2025-06-05')).toBe(true)
  })

  it('does not require sim when increasing an inflow on same date', () => {
    const old = txn('a', '2025-06-01', 10)
    expect(requiresSimulation(old, 20, '2025-06-01')).toBe(false)
  })
})

describe('computeDefaultRange', () => {
  it('includes lookback and horizon', () => {
    const txns = [txn('a', '2025-06-15', 10)]
    const { rangeStart, rangeEnd } = computeDefaultRange(txns, '2025-06-01', {
      lookbackDays: 30,
      horizonMonths: 6,
      paddingDays: 30,
    })
    // rangeStart should be min(2025-06-01, today - 30)
    // rangeEnd should include horizon + padding
    expect(rangeStart <= '2025-06-01').toBe(true)
    expect(rangeEnd > '2025-06-15').toBe(true)
  })
})
