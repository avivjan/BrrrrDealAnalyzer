// @vitest-environment jsdom
/**
 * Characterization of `TimelineChart`'s behavioural contract, written against
 * the v1 canvas implementation *before* the v2 SVG rewrite. Everything a
 * caller or spec can observe from outside is pinned here; the drawing is not.
 *
 *  - props `days`, `globalMin`, `globalMinDates`, `firstNegativeDate`
 *  - one emit, `selectDay`, whose payload is a bare ISO date string
 *  - `defineExpose({ centerOnToday })`
 *  - `data-testid="chart.container"` on a `tabindex="0"` element that handles
 *    keydown itself: ArrowRight/ArrowLeft move the selection (first press with
 *    nothing selected lands on index 0, both directions), clamp at the ends and
 *    emit on every press; Enter re-emits the current day; the arrows call
 *    `preventDefault`, nothing else does.
 */
import { describe, expect, it } from "vitest";
import { mount } from "@vue/test-utils";

import TimelineChart from "./TimelineChart.vue";
import type { DayBucket } from "../../types/liquidity";

const day = (date: string, balance_k: number, net_k = 0): DayBucket => ({
  date,
  transactions: [],
  net_k,
  balance_k,
});

const DAYS: DayBucket[] = [
  day("2026-09-01", 40),
  day("2026-09-02", 38, -2),
  day("2026-09-03", 45, 7),
  day("2026-09-04", 45),
  day("2026-09-05", -3, -48),
  day("2026-09-06", 10, 13),
];

function mountChart(days = DAYS) {
  return mount(TimelineChart, {
    props: { days, globalMin: -3, globalMinDates: ["2026-09-05"], firstNegativeDate: "2026-09-05" },
    attachTo: document.body,
  });
}

const container = (wrapper: ReturnType<typeof mountChart>) => wrapper.get('[data-testid="chart.container"]');

async function press(wrapper: ReturnType<typeof mountChart>, key: string) {
  const event = new KeyboardEvent("keydown", { key, bubbles: true, cancelable: true });
  container(wrapper).element.dispatchEvent(event);
  await wrapper.vm.$nextTick();
  return event;
}

describe("TimelineChart contract", () => {
  it("renders a focusable container that carries the hook", () => {
    const wrapper = mountChart();
    expect(container(wrapper).attributes("tabindex")).toBe("0");
    wrapper.unmount();
  });

  it("exposes centerOnToday as a zero-argument function", () => {
    const wrapper = mountChart();
    expect(typeof (wrapper.vm as unknown as { centerOnToday: unknown }).centerOnToday).toBe("function");
    expect(() => (wrapper.vm as unknown as { centerOnToday: () => void }).centerOnToday()).not.toThrow();
    wrapper.unmount();
  });

  it("ArrowRight with nothing selected lands on the first day and emits it", async () => {
    const wrapper = mountChart();
    const event = await press(wrapper, "ArrowRight");
    expect(wrapper.emitted("selectDay")).toEqual([["2026-09-01"]]);
    expect(event.defaultPrevented).toBe(true);
    wrapper.unmount();
  });

  it("ArrowLeft with nothing selected also lands on the first day", async () => {
    const wrapper = mountChart();
    await press(wrapper, "ArrowLeft");
    expect(wrapper.emitted("selectDay")).toEqual([["2026-09-01"]]);
    wrapper.unmount();
  });

  it("walks forward and back, emitting on every press, and clamps at both ends", async () => {
    const wrapper = mountChart();
    await press(wrapper, "ArrowRight"); // 0
    await press(wrapper, "ArrowRight"); // 1
    await press(wrapper, "ArrowRight"); // 2
    await press(wrapper, "ArrowLeft"); // 1
    await press(wrapper, "ArrowLeft"); // 0
    await press(wrapper, "ArrowLeft"); // clamps at 0
    expect(wrapper.emitted("selectDay")!.map((e) => e[0])).toEqual([
      "2026-09-01",
      "2026-09-02",
      "2026-09-03",
      "2026-09-02",
      "2026-09-01",
      "2026-09-01",
    ]);
    for (let i = 0; i < 10; i += 1) await press(wrapper, "ArrowRight");
    const all = wrapper.emitted("selectDay")!.map((e) => e[0]);
    expect(all[all.length - 1]).toBe("2026-09-06");
    expect(all.length).toBe(16);
    wrapper.unmount();
  });

  it("Enter re-emits the current day and does nothing with no selection", async () => {
    const wrapper = mountChart();
    const idle = await press(wrapper, "Enter");
    expect(wrapper.emitted("selectDay")).toBeUndefined();
    expect(idle.defaultPrevented).toBe(false);
    await press(wrapper, "ArrowRight");
    await press(wrapper, "Enter");
    expect(wrapper.emitted("selectDay")!.map((e) => e[0])).toEqual(["2026-09-01", "2026-09-01"]);
    wrapper.unmount();
  });

  it("ignores other keys without preventing their default", async () => {
    const wrapper = mountChart();
    const tab = await press(wrapper, "Tab");
    expect(tab.defaultPrevented).toBe(false);
    expect(wrapper.emitted("selectDay")).toBeUndefined();
    wrapper.unmount();
  });

  it("emits a bare ISO date string, never an object", async () => {
    const wrapper = mountChart();
    await press(wrapper, "ArrowRight");
    const [payload] = wrapper.emitted("selectDay")![0]!;
    expect(typeof payload).toBe("string");
    expect(payload).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    wrapper.unmount();
  });

  it("survives an empty series: arrows emit nothing and nothing throws", async () => {
    const wrapper = mountChart([]);
    await press(wrapper, "ArrowRight");
    expect(wrapper.emitted("selectDay") ?? []).toEqual([]);
    wrapper.unmount();
  });

  it("updates when the days prop changes (no stale emit target)", async () => {
    const wrapper = mountChart();
    await wrapper.setProps({ days: [day("2026-10-01", 1), day("2026-10-02", 2)] });
    await press(wrapper, "ArrowRight");
    expect(wrapper.emitted("selectDay")).toEqual([["2026-10-01"]]);
    wrapper.unmount();
  });
});
