import { describe, it, expect } from 'vitest'
import {
  addDays,
  aggregateNetByDay,
  buildDailyLiquiditySeries,
  simulateImpact,
  requiresSimulation,
  computeDefaultRange,
  projectTransactionsOntoToday,
  firstOfNextMonth,
} from './liquidityEngine'
import type { LiquidityTransaction } from '../types/liquidity'

function txn(id: string, date: string, amount_dollars: number, description = 'test'): LiquidityTransaction {
  return { id, effective_date: date, description, amount_dollars }
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
    expect(map.get('2025-06-15')?.net_dollars).toBe(7)
    expect(map.get('2025-06-15')?.txns).toHaveLength(2)
    expect(map.get('2025-06-16')?.net_dollars).toBe(5)
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
    expect(series.days).toHaveLength(5)

    expect(series.days[0]?.balance_dollars).toBe(59)
    expect(series.days[1]?.balance_dollars).toBe(59)
    expect(series.days[2]?.balance_dollars).toBe(54)
    expect(series.days[3]?.balance_dollars).toBe(54)
    expect(series.days[4]?.balance_dollars).toBe(54)
  })

  it('flat before opening balance date', () => {
    const txns = [txn('a', '2025-06-03', 10)]
    const series = buildDailyLiquiditySeries(txns, 20, '2025-06-02', '2025-06-01', '2025-06-04')

    expect(series.days[0]?.balance_dollars).toBe(20)
    expect(series.days[1]?.balance_dollars).toBe(20)
    expect(series.days[2]?.balance_dollars).toBe(30)
  })

  it('tracks globalMin and globalMinDates correctly', () => {
    const txns = [
      txn('a', '2025-06-02', -30),
      txn('b', '2025-06-04', -30),
      txn('c', '2025-06-05', 10),
    ]
    const series = buildDailyLiquiditySeries(txns, 49, '2025-06-01', '2025-06-01', '2025-06-06')

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
    expect(series.days[0]?.balance_dollars).toBe(49)
    expect(series.days[1]?.balance_dollars).toBe(49)
    expect(series.days[2]?.balance_dollars).toBe(49)
    expect(series.globalMin).toBe(49)
  })

  it('handles range start after opening with intermediate flows', () => {
    const txns = [
      txn('a', '2025-06-03', -20),
      txn('b', '2025-06-06', 5),
    ]
    const series = buildDailyLiquiditySeries(txns, 100, '2025-06-01', '2025-06-05', '2025-06-07')

    expect(series.days[0]?.balance_dollars).toBe(80)
    expect(series.days[1]?.balance_dollars).toBe(85)
    expect(series.days[2]?.balance_dollars).toBe(85)
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
    const candidate = [
      txn('a', '2025-06-02', -40),
    ]
    const resultBase = simulateImpact(baseline, 49, '2025-06-01', '2025-06-01', '2025-06-06', 5)
    const resultCandidate = simulateImpact(candidate, 49, '2025-06-01', '2025-06-01', '2025-06-06', 5)

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
    expect(rangeStart <= '2025-06-01').toBe(true)
    expect(rangeEnd > '2025-06-15').toBe(true)
  })
})

describe("projectTransactionsOntoToday — a row leaves only when marked done", () => {
  const TODAY = "2026-11-04";
  const row = (over: Partial<LiquidityTransaction>): LiquidityTransaction => ({
    id: "t", effective_date: TODAY, description: "row", amount_dollars: -100, ...over,
  });

  it("counts open rows from today on as they are", () => {
    const result = projectTransactionsOntoToday([row({ id: "today" }), row({ id: "later", effective_date: "2026-12-01" })], TODAY);
    expect(result.countedTransactions.map((t) => [t.id, t.effective_date])).toEqual([["today", TODAY], ["later", "2026-12-01"]]);
    expect(result.overdueMoneyOut).toEqual([]);
  });

  it("moves overdue money out onto today and keeps counting it", () => {
    const result = projectTransactionsOntoToday([row({ id: "hml", effective_date: "2026-11-01", amount_dollars: -1970.83 })], TODAY);
    expect(result.countedTransactions).toEqual([
      expect.objectContaining({ id: "hml", effective_date: TODAY, overdue_since_date: "2026-11-01", amount_dollars: -1970.83 }),
    ]);
    expect(result.overdueMoneyOut.map((t) => t.effective_date)).toEqual(["2026-11-01"]);
  });

  it("sets overdue money in aside, shown but not counted", () => {
    const result = projectTransactionsOntoToday([row({ id: "rent", effective_date: "2026-11-01", amount_dollars: 2600 })], TODAY);
    expect(result.countedTransactions).toEqual([]);
    expect(result.expectedMoneyInNotCounted.map((t) => t.id)).toEqual(["rent"]);
  });

  it("leaves done rows out wherever they are dated", () => {
    const result = projectTransactionsOntoToday([
      row({ id: "paid", effective_date: "2026-11-01", done_at: "2026-11-02T10:00:00Z" }),
      row({ id: "released-early", effective_date: "2026-12-01", done_at: "2026-11-03T10:00:00Z" }),
    ], TODAY);
    expect(result).toEqual({ countedTransactions: [], overdueMoneyOut: [], expectedMoneyInNotCounted: [] });
  });

  it("keeps recurring occurrences as before (they cannot be marked done)", () => {
    const occurrence = row({ id: "rule-1:0", effective_date: "2026-10-01", recurring_rule_id: "rule-1", recurring_index: 0 });
    expect(projectTransactionsOntoToday([occurrence], TODAY).countedTransactions).toEqual([occurrence]);
  });

  it("lowers today's balance by what is still owed", () => {
    const { countedTransactions } = projectTransactionsOntoToday([row({ effective_date: "2026-11-01", amount_dollars: -500 })], TODAY);
    const series = buildDailyLiquiditySeries(countedTransactions, 10_000, TODAY, TODAY, "2026-11-10");
    expect(series.days[0]!.balance_dollars).toBe(9_500);
  });
});

describe("firstOfNextMonth", () => {
  it("is the first 1st strictly after the date", () => {
    expect(firstOfNextMonth("2026-11-04")).toBe("2026-12-01");
    expect(firstOfNextMonth("2026-12-01")).toBe("2027-01-01");
  });
});
