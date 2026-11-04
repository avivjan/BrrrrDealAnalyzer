import { describe, expect, it } from "vitest";

import type { DealCashRowChange, LiquiditySeries } from "../types/liquidity";
import { buildDealImpactDecision, type DealImpactDecision } from "./dealImpactDecision";

const TODAY = "2026-11-03";

/** One balance per day from Nov 1 on. */
function series(balances: number[]): LiquiditySeries {
  const days = balances.map((balance_dollars, index) => {
    const date = new Date(Date.UTC(2026, 10, 1 + index)).toISOString().slice(0, 10);
    return { date, transactions: [], net_dollars: 0, balance_dollars };
  });
  const globalMin = Math.min(...balances);
  return { days, globalMin, globalMinDates: days.filter((day) => day.balance_dollars === globalMin).map((day) => day.date), firstNegativeDate: null };
}

const dateOf = (index: number) => new Date(Date.UTC(2026, 10, 1 + index)).toISOString().slice(0, 10);

function change(item_key: string, dayIndex: number, amount: number): DealCashRowChange {
  return {
    change_kind: "added", item_key, occurrence_number: 1, description: item_key, transaction_id: null,
    date_before: null, date_after: dateOf(dayIndex), amount_dollars_before: null, amount_dollars_after: amount,
    deal_date_not_applied_because_you_changed_it: null, deal_amount_dollars_not_applied_because_you_changed_it: null,
    created_because_refi_is_late: false,
  };
}

const verdictText = (decision: DealImpactDecision) => decision.verdictHeadline.map((segment) => segment.text).join("");
const followUpText = (decision: DealImpactDecision) => (decision.verdictFollowUp ?? []).map((segment) => segment.text).join("");

const FLAT = Array.from({ length: 20 }, () => 50_000);

describe("buildDealImpactDecision: an import", () => {
  it("goes negative: says how far below zero, when, whether the refi brings it back, and the cash that covers it", () => {
    // Closing on Nov 5 takes 80k; the refi on Nov 12 brings 60k back.
    const after = FLAT.map((balance, index) => (index < 4 ? balance : index < 11 ? balance - 80_000 : balance - 20_000));
    const decision = buildDealImpactDecision({
      seriesBefore: series(FLAT), seriesAfter: series(after), reserveDollars: 5000, todayIsoDate: TODAY, mode: "import",
      changes: [change("cash_to_close_buy", 4, -80_000), change("stolen_money", 11, 60_000)],
      keyDates: [{ key: "refi_closed", date: dateOf(11), description: "Refi closing" }],
    });
    expect(decision.riskLevel).toBe("goes_negative");
    expect(decision.tone).toBe("negative");
    expect(verdictText(decision)).toBe("This deal takes you $30,000 below zero on Nov 5, 2026, and the refi brings you back above your reserve by Nov 12, 2026.");
    expect(decision.verdictHeadline.filter((segment) => segment.isEmphasised).map((segment) => segment.text)).toContain("$30,000 below zero");
    expect(followUpText(decision)).toBe("Bring $35,000 by Nov 5, 2026 to keep your reserve ($30,000 just to stay above zero).");
    expect(decision.cashToKeepTheReserve).toEqual({ amountDollars: 35_000, neededByDate: dateOf(4) });
    expect(decision.peakCashTiedUp).toEqual({ date: dateOf(4), amountDollars: 80_000 });
    expect(decision.refi).toEqual({ date: dateOf(11), netDollarsOnTheDay: 60_000 });
    expect(decision.backAboveReserveAfterTheRefi).toEqual({ date: dateOf(11), daysAfterTheRefi: 0 });
    expect(decision.longestStretchBelowReserve).toMatchObject({ fromDate: dateOf(4), toDate: dateOf(10), days: 7, runsToTheEndOfTheTimeline: false });
    expect(decision.daysBelowZeroAfter).toBe(7);
  });

  it("goes negative and never recovers: says so, and how far short the timeline ends", () => {
    const after = FLAT.map((balance, index) => (index < 2 ? balance : balance - 105_000));
    const decision = buildDealImpactDecision({
      seriesBefore: series(FLAT), seriesAfter: series(after), reserveDollars: 5000, todayIsoDate: TODAY, mode: "import",
      changes: [change("cash_to_close_buy", 2, -105_000)],
    });
    expect(verdictText(decision)).toBe("This deal takes you $55,000 below zero on Nov 3, 2026, and you don't recover in the timeline.");
    expect(decision.backAboveReserveAfterTheRefi).toBeNull();
    expect(decision.shortOfTheReserveAtTheEnd).toEqual({ date: dateOf(19), amountDollars: 60_000 });
    expect(decision.longestStretchBelowReserve?.runsToTheEndOfTheTimeline).toBe(true);
  });

  it("dips below the reserve without going negative", () => {
    const after = FLAT.map((balance, index) => (index >= 5 && index < 8 ? 2_000 : balance));
    const decision = buildDealImpactDecision({
      seriesBefore: series(FLAT), seriesAfter: series(after), reserveDollars: 5000, todayIsoDate: TODAY, mode: "import",
      changes: [change("cash_to_close_buy", 5, -48_000), change("stolen_money", 8, 48_000)],
    });
    expect(decision.riskLevel).toBe("dips_below_reserve");
    expect(verdictText(decision)).toMatch(/^You'd be under your \$5,000 reserve for 3 days \(lowest \$2,000 on Nov 6, 2026\)/);
    expect(followUpText(decision)).toBe("Bring $3,000 by Nov 6, 2026 to keep your reserve.");
    expect(decision.cashToStayAboveZero).toBeNull();
  });

  it("stays safe", () => {
    const after = FLAT.map((balance, index) => (index >= 5 ? 30_000 : balance));
    const decision = buildDealImpactDecision({
      seriesBefore: series(FLAT), seriesAfter: series(after), reserveDollars: 5000, todayIsoDate: TODAY, mode: "import",
      changes: [change("cash_to_close_buy", 5, -20_000)],
    });
    expect(decision.riskLevel).toBe("stays_above_reserve");
    expect(decision.tone).toBe("positive");
    expect(verdictText(decision)).toBe("You stay above your $5,000 reserve: lowest $30,000 on Nov 6, 2026.");
    expect(decision.verdictFollowUp).toBeNull();
    expect(decision.lowestChangeDollars).toBe(-20_000);
  });

  it("does not blame the deal for a timeline already under the reserve", () => {
    const before = FLAT.map(() => 3_000);
    const decision = buildDealImpactDecision({
      seriesBefore: series(before), seriesAfter: series(before.map((balance) => balance - 1_000)), reserveDollars: 5000,
      todayIsoDate: TODAY, mode: "import", changes: [change("cash_to_close_buy", 2, -1_000)],
    });
    expect(decision.alreadyBelowReserveBefore).toBe(true);
    expect(followUpText(decision)).toContain("Your timeline is already under the reserve without this deal.");
  });

  it("measures the next 30 days against today's cash", () => {
    const decision = buildDealImpactDecision({
      seriesBefore: series(FLAT), seriesAfter: series(FLAT.map((balance) => balance - 100_000)), reserveDollars: 5000,
      todayIsoDate: TODAY, mode: "import", changes: [change("cash_to_close_buy", 5, -100_000)],
    });
    expect(decision.next30Days).toEqual({ cashTodayDollars: 50_000, dealMoneyOutDollars: 100_000, coveredFraction: 0.5 });
  });
});

describe("buildDealImpactDecision: a re-sync", () => {
  const resync = (after: number[]) => buildDealImpactDecision({
    seriesBefore: series(FLAT.map((balance) => balance - 20_000)), seriesAfter: series(after), reserveDollars: 5000,
    todayIsoDate: TODAY, mode: "resync", changes: [change("cash_to_close_buy", 5, -1)],
  });

  it("words a negative result as applying the changes", () => {
    expect(verdictText(resync(FLAT.map((balance, index) => (index >= 5 ? -1_000 : balance))))).toMatch(/^Applying these changes takes you \$1,000 below zero/);
  });

  it("words a dip under the reserve as applying the changes", () => {
    expect(verdictText(resync(FLAT.map((balance, index) => (index >= 5 ? 1_000 : balance))))).toMatch(/^Applying these changes puts you under your \$5,000 reserve/);
  });

  it("says when the changes improve the low point", () => {
    expect(verdictText(resync(FLAT.map((balance) => balance - 15_000)))).toBe("These changes improve your lowest point by $5,000 (to $35,000 on Nov 3, 2026).");
  });

  it("says when the changes barely move the timeline", () => {
    expect(verdictText(resync(FLAT.map((balance) => balance - 20_050)))).toBe("These changes barely move your timeline (lowest $30,000 → $29,950).");
  });

  it("says when the changes keep you safe but lower the low point", () => {
    expect(verdictText(resync(FLAT.map((balance) => balance - 30_000)))).toBe("Applying these changes keeps you above your $5,000 reserve: lowest $20,000 on Nov 3, 2026.");
  });
});
