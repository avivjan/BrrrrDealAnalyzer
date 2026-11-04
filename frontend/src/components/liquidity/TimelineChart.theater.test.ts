// @vitest-environment jsdom
/**
 * TimelineChart's theater-mode additions (tasks/todo/LiquidityTheaterMode.md, section E): today emphasised (a
 * glow, a TODAY pill, an edge chip when it is scrolled away), the floating tooltip for hover only, no hover from
 * a touch pointer, `openDay` on a tap or Enter, and the deal dots and tooltip deal tags from the injected lookup.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { mount } from "@vue/test-utils";
import { defineComponent, h, ref } from "vue";

import TimelineChart from "./TimelineChart.vue";
import { provideLiquidityDealAttribution } from "../../composables/useLiquidityDealAttribution";
import type { DayBucket, ImportedLiquidityDeal } from "../../types/liquidity";

const TODAY = "2026-11-03";
const DEAL: ImportedLiquidityDeal = {
  deal_board: "my_deals", deal_id: "d1", deal_address: "4431 Victor St, Jacksonville, FL 32207", my_deals_deal_id_it_was_moved_from: null,
  liquidity_rows_out_of_date: false, open_row_count: 1, done_row_count: 0, overdue_open_row_count: 0, late_refi_row_count: 0, refi_is_late: false, milestones: [],
};

/** 60 days from Oct 1; today (Nov 3) carries one deal row and one manual row. */
function days(): DayBucket[] {
  return Array.from({ length: 60 }, (_, index) => {
    const date = new Date(2026, 9, 1 + index);
    const iso = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
    const transactions = iso === TODAY
      ? [
          { id: "cushion", effective_date: iso, description: "Rehab cushion", amount_dollars: -5000, source_deal_board: "my_deals" as const, source_deal_id: "d1" },
          { id: "groceries", effective_date: iso, description: "Groceries", amount_dollars: -100 },
        ]
      : [];
    return { date: iso, transactions, net_dollars: transactions.reduce((total, txn) => total + txn.amount_dollars, 0), balance_dollars: 40000 };
  });
}

const DAYS = days();

function mountChart(props: Record<string, unknown> = {}, withDealLookup = false) {
  const chartProps = { days: DAYS, globalMin: 40000, globalMinDates: [], firstNegativeDate: null, ...props };
  if (!withDealLookup) return mount(TimelineChart, { props: chartProps, attachTo: document.body });
  const Host = defineComponent({
    setup() {
      provideLiquidityDealAttribution(ref([DEAL]));
      return () => h(TimelineChart, chartProps);
    },
  });
  return mount(Host, { attachTo: document.body });
}

/** jsdom has no PointerEvent: a MouseEvent with the pointer fields added. */
async function pointer(wrapper: { vm: { $nextTick: () => Promise<void> } }, target: Element, type: string, clientX: number, pointerType: "mouse" | "touch") {
  const event = new MouseEvent(type, { clientX, bubbles: true, cancelable: true });
  Object.defineProperty(event, "pointerType", { value: pointerType });
  Object.defineProperty(event, "pointerId", { value: 1 });
  target.dispatchEvent(event);
  await wrapper.vm.$nextTick();
}

const proto = HTMLElement.prototype;
function setSize(name: "clientWidth" | "clientHeight", value: number) {
  Object.defineProperty(proto, name, { configurable: true, get: () => value });
}

describe("TimelineChart in theater mode", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date(2026, 10, 3, 12));
    setSize("clientWidth", 800);
    setSize("clientHeight", 400);
    Object.defineProperty(Element.prototype, "setPointerCapture", { configurable: true, value: () => {} });
    Object.defineProperty(Element.prototype, "hasPointerCapture", { configurable: true, value: () => true });
    Object.defineProperty(Element.prototype, "releasePointerCapture", { configurable: true, value: () => {} });
  });
  afterEach(() => {
    vi.useRealTimers();
    Reflect.deleteProperty(proto, "clientWidth");
    Reflect.deleteProperty(proto, "clientHeight");
  });

  /** The x of today's column after `centerOnToday` (the container starts at 0 in jsdom). */
  function todayClientX(wrapper: ReturnType<typeof mountChart>) {
    const todayLine = wrapper.get('[data-part="today-glow-line"]');
    return Number(todayLine.attributes("x1"));
  }

  it("emphasises today with a glow and a TODAY pill", async () => {
    const wrapper = mountChart();
    await wrapper.vm.$nextTick();
    expect(wrapper.findAll('[data-part="today-glow"]')).toHaveLength(1);
    expect(wrapper.get('[data-part="today-pill"]').text()).toBe("TODAY");
    expect(wrapper.find('[data-testid="chart.today-edge-chip"]').exists()).toBe(false);
    wrapper.unmount();
  });

  it("offers an edge chip when today is scrolled away, and re-centres on it", async () => {
    const wrapper = mountChart();
    await wrapper.vm.$nextTick();
    const svg = wrapper.get('[data-testid="chart.svg"]');
    await svg.trigger("wheel", { deltaY: 5000 });
    const chip = wrapper.get('[data-testid="chart.today-edge-chip"]');
    expect(chip.attributes("data-side")).toBe("left");
    await chip.trigger("click");
    expect(wrapper.find('[data-testid="chart.today-edge-chip"]').exists()).toBe(false);
    wrapper.unmount();
  });

  it("floats the tooltip beside the crosshair only with tooltipFollowsPointer", async () => {
    const fixed = mountChart();
    await fixed.vm.$nextTick();
    await pointer(fixed, fixed.get('[data-testid="chart.svg"]').element, "pointermove", todayClientX(fixed), "mouse");
    expect(fixed.get('[data-testid="chart.tooltip"]').attributes("data-floating")).toBeUndefined();
    fixed.unmount();

    const floating = mountChart({ tooltipFollowsPointer: true });
    await floating.vm.$nextTick();
    await pointer(floating, floating.get('[data-testid="chart.svg"]').element, "pointermove", todayClientX(floating), "mouse");
    const tooltip = floating.get('[data-testid="chart.tooltip"]');
    expect(tooltip.attributes("data-floating")).toBe("true");
    expect(tooltip.attributes("style")).toContain("translate(");
    floating.unmount();
  });

  it("takes no hover from a finger: a touch move shows no tooltip, a tap opens the day", async () => {
    const wrapper = mountChart({ tooltipFollowsPointer: true });
    await wrapper.vm.$nextTick();
    const svg = wrapper.get('[data-testid="chart.svg"]');
    const clientX = todayClientX(wrapper);
    await pointer(wrapper, svg.element, "pointermove", clientX, "touch");
    expect(wrapper.find('[data-testid="chart.tooltip"]').exists()).toBe(false);
    await pointer(wrapper, svg.element, "pointerdown", clientX, "touch");
    await pointer(wrapper, svg.element, "pointerup", clientX, "touch");
    expect(wrapper.emitted("openDay")).toEqual([[TODAY]]);
    // A floating tooltip is a hover preview: the tap's selection does not show one.
    expect(wrapper.find('[data-testid="chart.tooltip"]').exists()).toBe(false);
    wrapper.unmount();
  });

  it("opens the day on Enter but not on the arrow keys", async () => {
    const wrapper = mountChart();
    await wrapper.vm.$nextTick();
    const container = wrapper.get('[data-testid="chart.container"]');
    await container.trigger("keydown", { key: "ArrowRight" });
    expect(wrapper.emitted("openDay")).toBeUndefined();
    await container.trigger("keydown", { key: "Enter" });
    expect(wrapper.emitted("openDay")).toEqual([[DAYS[0]!.date]]);
    wrapper.unmount();
  });

  it("draws one dot per deal on a day, tags the tooltip rows with their deal, and dims other deals on highlight", async () => {
    const wrapper = mountChart({ tooltipFollowsPointer: true, highlightedDealKey: "bought:other" }, true);
    await wrapper.vm.$nextTick();
    const dots = wrapper.findAll('[data-part="deal-dot"]');
    expect(dots).toHaveLength(1);
    expect(dots[0]!.attributes("data-deal-key")).toBe("my_deals:d1");
    expect(dots[0]!.attributes("opacity")).toBe("0.2");
    await pointer(wrapper, wrapper.get('[data-testid="chart.svg"]').element, "pointermove", todayClientX(wrapper), "mouse");
    expect(wrapper.get('[data-testid="deal-tag.cushion"]').text()).toBe("4431 Victor St");
    expect(wrapper.find('[data-testid="deal-tag.groceries"]').exists()).toBe(false);
    wrapper.unmount();
  });

  it("centres a day and selects it, its floating tooltip showing (the Lowest button)", async () => {
    const wrapper = mountChart({ tooltipFollowsPointer: true });
    await wrapper.vm.$nextTick();
    const chart = wrapper.findComponent(TimelineChart);
    (chart.vm as unknown as { centerOnDate: (isoDate: string) => void }).centerOnDate("2026-11-20");
    await wrapper.vm.$nextTick();
    expect(wrapper.get('[data-testid="chart.tooltip"]').text()).toContain("Nov 20");
    expect(chart.emitted("selectDay")).toEqual([["2026-11-20"]]);
    expect(wrapper.find('[data-date="2026-11-20"]').exists()).toBe(true);
    wrapper.unmount();
  });
  describe("opens on today, wherever the data and the size settle", () => {
    const DAYS_FROM_TODAY = DAYS.filter((day) => day.date >= TODAY);

    /** Where today sits when the chart mounts with every day already there. */
    async function centredTodayClientX() {
      const wrapper = mountChart();
      await wrapper.vm.$nextTick();
      const centredX = todayClientX(wrapper);
      wrapper.unmount();
      return centredX;
    }

    it("re-centres on today when earlier days arrive after the chart mounted", async () => {
      const centredX = await centredTodayClientX();
      const wrapper = mountChart({ days: DAYS_FROM_TODAY });
      await wrapper.vm.$nextTick();
      await wrapper.setProps({ days: DAYS });
      expect(todayClientX(wrapper)).toBe(centredX);
      expect(wrapper.find('[data-testid="chart.today-edge-chip"]').exists()).toBe(false);
      wrapper.unmount();
    });

    it("centres on today once the days load, when it mounted with none", async () => {
      const centredX = await centredTodayClientX();
      const wrapper = mountChart({ days: [] });
      await wrapper.vm.$nextTick();
      await wrapper.setProps({ days: DAYS });
      expect(todayClientX(wrapper)).toBe(centredX);
      wrapper.unmount();
    });

    it("stops following today once the user scrolls", async () => {
      const wrapper = mountChart({ days: DAYS_FROM_TODAY });
      await wrapper.vm.$nextTick();
      await wrapper.get('[data-testid="chart.svg"]').trigger("wheel", { deltaY: 5000 });
      await wrapper.setProps({ days: DAYS });
      expect(wrapper.find('[data-testid="chart.today-edge-chip"]').exists()).toBe(true);
      wrapper.unmount();
    });
  });
});
