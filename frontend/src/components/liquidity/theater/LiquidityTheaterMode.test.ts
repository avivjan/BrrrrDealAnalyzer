// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { mount, RouterLinkStub } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";

import LiquidityTheaterMode from "./LiquidityTheaterMode.vue";
import { useLiquidityStore } from "../../../stores/liquidityStore";

const HEADLINE_FIGURES = {
  balance: "$42,106", balanceTone: "neutral", min: "$6,470", minTone: "positive", minDate: "2028-12-01",
  daysToNegative: "None", daysTone: "positive", reserve: "$5,000",
};

function mountTheater(props: Partial<{ open: boolean; isAnotherDialogOpen: boolean }> = {}) {
  return mount(LiquidityTheaterMode, {
    props: { open: true, headlineFigures: HEADLINE_FIGURES, isAnotherDialogOpen: false, ...props },
    global: { stubs: { teleport: true, RouterLink: RouterLinkStub } },
    attachTo: document.body,
  });
}

function pressKey(key: string, target: EventTarget = window) {
  const event = new KeyboardEvent("keydown", { key, bubbles: true, cancelable: true });
  target.dispatchEvent(event);
  return event;
}

describe("LiquidityTheaterMode", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.useFakeTimers();
    vi.setSystemTime(new Date(2026, 10, 3, 12));
    try { localStorage.removeItem("bw.liquidity.theater.legend-open"); } catch { /* none */ }
  });
  afterEach(() => vi.useRealTimers());

  it("renders nothing while closed, and the full-screen frame while open", () => {
    const closed = mountTheater({ open: false });
    expect(closed.find('[data-testid="theater.root"]').exists()).toBe(false);
    closed.unmount();
    const open = mountTheater();
    expect(open.get('[data-testid="theater.root"]').attributes("aria-modal")).toBe("true");
    expect(open.get('[data-testid="theater.figure.balance"]').text()).toContain("$42,106");
    open.unmount();
  });

  it("leaves on × and on Esc", async () => {
    const wrapper = mountTheater();
    await wrapper.get('[data-testid="theater.close"]').trigger("click");
    pressKey("Escape");
    expect(wrapper.emitted("close")).toHaveLength(2);
    wrapper.unmount();
  });

  it("closes the deals sheet with Esc before leaving", async () => {
    const wrapper = mountTheater();
    await wrapper.get('[data-testid="theater.sheet.toggle"]').trigger("click");
    expect(wrapper.get('[data-testid="theater.sheet.toggle"]').attributes("aria-expanded")).toBe("true");
    pressKey("Escape");
    await wrapper.vm.$nextTick();
    expect(wrapper.get('[data-testid="theater.sheet.toggle"]').attributes("aria-expanded")).toBe("false");
    expect(wrapper.emitted("close")).toBeUndefined();
    pressKey("Escape");
    expect(wrapper.emitted("close")).toHaveLength(1);
    wrapper.unmount();
  });

  it("leaves Esc and the shortcuts to another open dialog", () => {
    const wrapper = mountTheater({ isAnotherDialogOpen: true });
    pressKey("Escape");
    pressKey("t");
    expect(wrapper.emitted("close")).toBeUndefined();
    wrapper.unmount();
  });

  it("opens on T from the page, and ignores T typed into a field", () => {
    const wrapper = mountTheater({ open: false });
    const input = document.createElement("input");
    document.body.appendChild(input);
    pressKey("t", input);
    expect(wrapper.emitted("open")).toBeUndefined();
    pressKey("t");
    expect(wrapper.emitted("open")).toHaveLength(1);
    input.remove();
    wrapper.unmount();
  });

  it("toggles the legend on L and the deals sheet on D", async () => {
    const wrapper = mountTheater();
    const legendOpenAtFirst = wrapper.find('[data-testid="theater.legend"]').exists();
    pressKey("l");
    await wrapper.vm.$nextTick();
    expect(wrapper.find('[data-testid="theater.legend"]').exists()).toBe(!legendOpenAtFirst);
    pressKey("d");
    await wrapper.vm.$nextTick();
    expect(wrapper.get('[data-testid="theater.sheet.toggle"]').attributes("aria-expanded")).toBe("true");
    wrapper.unmount();
  });

  it("shows the overdue chip and its popover from the store's overdue rows", async () => {
    const store = useLiquidityStore();
    store.transactions = [{ id: "u", effective_date: "2026-11-01", description: "Utilities", amount_dollars: -80 }];
    store.settings = { opening_balance_dollars: 42106, opening_balance_date: "2026-11-03", reserve_dollars: 5000 };
    const wrapper = mountTheater();
    const chip = wrapper.get('[data-testid="theater.figure.overdue"]');
    expect(chip.text()).toContain("1 overdue");
    await chip.trigger("click");
    expect(wrapper.get('[data-testid="theater.overdue-popover"]').text()).toContain("Utilities");
    wrapper.unmount();
  });
});
