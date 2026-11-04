// @vitest-environment jsdom
/** The store's recurring occurrences (tasks/todo/DealImpactSimulator.md, E): from a row id to its rule and date, and a state change re-expands the rule. */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createPinia, setActivePinia } from "pinia";

import { liquidityApi } from "../api/liquidity";
import { useLiquidityStore } from "./liquidityStore";

const RULE = {
  id: "r1", description: "Misc", amount_dollars: -1500, start_date: "2026-08-01", end_date: null, occurrences: null,
  frequency: "monthly" as const, interval: 1, occurrences_can_be_overdue_from: "2026-09-15", occurrence_states: [],
};

describe("liquidity store: recurring occurrences", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(new Date(2026, 10, 4, 12));
  });
  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it("finds an occurrence's rule and scheduled date from its row id, and only for an occurrence", () => {
    const store = useLiquidityStore();
    store.settings = { opening_balance_dollars: 10_000, opening_balance_date: "2026-11-04", reserve_dollars: 5000 };
    store.recurringRules = [RULE];
    const missed = store.overdueMoneyOut.find((row) => row.recurring_scheduled_date === "2026-10-01")!;
    expect(store.recurringOccurrenceOf(missed.id)).toEqual({ ruleId: "r1", scheduledDate: "2026-10-01", effectiveDate: "2026-10-01" });
    expect(store.recurringOccurrenceOf("some-one-off-id")).toBeNull();
  });

  it("marks an occurrence done and re-expands the rule: it is no longer overdue", async () => {
    const store = useLiquidityStore();
    store.settings = { opening_balance_dollars: 10_000, opening_balance_date: "2026-11-04", reserve_dollars: 5000 };
    store.recurringRules = [RULE];
    expect(store.overdueMoneyOut.map((row) => row.recurring_scheduled_date)).toEqual(["2026-10-01", "2026-11-01"]);
    vi.spyOn(liquidityApi, "markRecurringOccurrenceDone").mockResolvedValue({
      ...RULE, occurrence_states: [{ scheduled_date: "2026-10-01", done_at: "2026-11-04T12:00:00Z", moved_to_date: null }],
    });
    await store.markRecurringOccurrenceDone("r1", "2026-10-01");
    expect(liquidityApi.markRecurringOccurrenceDone).toHaveBeenCalledWith("r1", "2026-10-01");
    expect(store.overdueMoneyOut.map((row) => row.recurring_scheduled_date)).toEqual(["2026-11-01"]);
  });
});
