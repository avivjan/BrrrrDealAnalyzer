// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { enableAutoUnmount, mount } from "@vue/test-utils";

import DealImpactChart from "./DealImpactChart.vue";

/** 120 days from Nov 1, 2026: the deal takes 80k on Nov 10 and the refi brings 60k back on Jan 5. */
const DATES = Array.from({ length: 120 }, (_, index) => new Date(Date.UTC(2026, 10, 1 + index)).toISOString().slice(0, 10));
const BEFORE = DATES.map(() => 50_000);
const AFTER = DATES.map((date) => (date < "2026-11-10" ? 50_000 : date < "2027-01-05" ? -30_000 : 30_000));

const proto = HTMLElement.prototype;
function setSize(name: "clientWidth" | "clientHeight", value: number) {
  Object.defineProperty(proto, name, { configurable: true, get: () => value });
}

function mountChart(over: Record<string, unknown> = {}) {
  return mount(DealImpactChart, {
    props: {
      dates: DATES, balancesBefore: BEFORE, balancesAfter: AFTER, reserveDollars: 5_000, todayIsoDate: "2026-11-03",
      dealColorHex: "#2a78d6", beforeLabel: "Current", afterLabel: "With this deal",
      lowestAfter: { date: "2026-11-10", amountDollars: -30_000 }, backAboveReserveDate: "2027-01-05", refiDate: "2027-01-05",
      keyDates: [
        { key: "purchase_closed", date: "2026-11-10", description: "Purchase closing" },
        { key: "refi_closed", date: "2027-01-05", description: "Refi closing" },
      ],
      dealRowsByDate: { "2026-11-10": [{ description: "Cash to close", amountDollars: -80_000 }] },
      ...over,
    },
    attachTo: document.body,
  });
}

async function pointer(wrapper: ReturnType<typeof mountChart>, type: string, clientX: number, pointerType: "mouse" | "touch") {
  const event = new MouseEvent(type, { clientX, bubbles: true });
  Object.defineProperty(event, "pointerType", { value: pointerType });
  wrapper.get("svg").element.dispatchEvent(event);
  await wrapper.vm.$nextTick();
}

enableAutoUnmount(afterEach);

describe("DealImpactChart", () => {
  beforeEach(() => {
    setSize("clientWidth", 800);
    setSize("clientHeight", 400);
  });
  afterEach(() => {
    Reflect.deleteProperty(proto, "clientWidth");
    Reflect.deleteProperty(proto, "clientHeight");
  });

  it("draws both lines, the difference between them, and the zones only where the deal goes under", async () => {
    const wrapper = mountChart();
    await wrapper.vm.$nextTick();
    expect(wrapper.find('[data-part="before-line"]').attributes("d")).toMatch(/^M/);
    expect(wrapper.find('[data-part="after-line"]').attributes("stroke")).toBe("#2a78d6");
    expect(wrapper.find('[data-part="gap"]').attributes("d")).toMatch(/Z$/);
    expect(wrapper.findAll('[data-part="below-reserve-zone"]')).toHaveLength(1);
    expect(wrapper.findAll('[data-part="below-zero-zone"]')).toHaveLength(1);

    const safe = mountChart({ balancesAfter: DATES.map(() => 40_000), lowestAfter: { date: "2026-11-10", amountDollars: 40_000 }, backAboveReserveDate: null });
    await safe.vm.$nextTick();
    expect(safe.findAll('[data-part="below-reserve-zone"]')).toHaveLength(0);
    expect(safe.find('[data-part="recovery-pin"]').exists()).toBe(false);
  });

  it("calls out the low point, the key dates and the day back above the reserve", async () => {
    const wrapper = mountChart();
    await wrapper.vm.$nextTick();
    expect(wrapper.get('[data-part="lowest-pin"]').text()).toBe("Lowest -$30,000 · Nov 10");
    expect(wrapper.findAll('[data-part="key-date-flag"]').map((flag) => flag.text())).toEqual(["Closing", "Refi"]);
    expect(wrapper.get('[data-part="recovery-pin"]').text()).toBe("Back above reserve · Jan 5");
  });

  it("shows both balances, the difference and the day's deal rows on hover", async () => {
    const wrapper = mountChart();
    await wrapper.vm.$nextTick();
    // The window starts on Oct 27 (clamped to Nov 1, index 0); find the x of Nov 10.
    let tooltipText = "";
    for (let clientX = 60; clientX < 790 && !tooltipText.includes("Nov 10, 2026"); clientX += 2) {
      await pointer(wrapper, "pointermove", clientX, "mouse");
      tooltipText = wrapper.find('[data-testid="deal-impact.tooltip"]').text();
    }
    expect(tooltipText).toContain("Current+$50,000");
    expect(tooltipText).toContain("With this deal-$30,000");
    expect(wrapper.get('[data-testid="deal-impact.tooltip.delta"]').text()).toContain("-$80,000");
    expect(tooltipText).toContain("Cash to close");
  });

  it("pins the tooltip on a tap (no hover from a finger), and the arrow keys step days", async () => {
    const wrapper = mountChart();
    await wrapper.vm.$nextTick();
    await pointer(wrapper, "pointermove", 300, "touch");
    expect(wrapper.find('[data-testid="deal-impact.tooltip"]').exists()).toBe(false);
    await pointer(wrapper, "pointerdown", 300, "touch");
    expect(wrapper.find('[data-testid="deal-impact.tooltip"]').exists()).toBe(true);
    const firstDate = wrapper.get('[data-testid="deal-impact.tooltip"] div').text();
    await wrapper.get('[data-testid="deal-impact.plot"]').trigger("keydown", { key: "ArrowRight" });
    expect(wrapper.get('[data-testid="deal-impact.tooltip"] div').text()).not.toBe(firstDate);
  });

  it("changes the window with the range chips", async () => {
    // No refi in view: the lifecycle ends 60 days after today, well before the series does.
    const wrapper = mountChart({ refiDate: null, backAboveReserveDate: null });
    await wrapper.vm.$nextTick();
    const lifecyclePath = wrapper.get('[data-part="after-line"]').attributes("d");
    await wrapper.get('[data-testid="deal-impact.range.all"]').trigger("click");
    expect(wrapper.get('[data-testid="deal-impact.range.all"]').attributes("aria-pressed")).toBe("true");
    expect(wrapper.get('[data-part="after-line"]').attributes("d")).not.toBe(lifecyclePath);
  });
});
