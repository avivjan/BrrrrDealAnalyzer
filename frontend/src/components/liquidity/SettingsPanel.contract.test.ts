// @vitest-environment jsdom
import { afterEach, describe, expect, it } from "vitest";
import { DOMWrapper, mount } from "@vue/test-utils";

import SettingsPanel from "./SettingsPanel.vue";
import type { LiquiditySettings } from "../../types/liquidity";

const SETTINGS: LiquiditySettings = {
  opening_balance_k: 49,
  opening_balance_date: "2026-01-01",
  reserve_k: 5,
};

/** Teleports to `<body>`, and the seeding watcher hangs off `open`. */
async function openPanel(settings: LiquiditySettings = SETTINGS) {
  const wrapper = mount(SettingsPanel, { props: { open: false, settings } });
  await wrapper.setProps({ open: true });
  return wrapper;
}

function at(testid: string): DOMWrapper<HTMLElement> {
  const el = document.querySelector(`[data-testid="${testid}"]`);
  expect(el, `no element with data-testid="${testid}"`).toBeTruthy();
  return new DOMWrapper(el as HTMLElement);
}

const value = (testid: string) => (at(testid).element as HTMLInputElement).value;

function lastSave(wrapper: Awaited<ReturnType<typeof openPanel>>) {
  const events = wrapper.emitted("save");
  return events ? events[events.length - 1]![0] : undefined;
}

describe("SettingsPanel", () => {
  afterEach(() => {
    document.body.innerHTML = "";
  });

  it("renders nothing while closed", () => {
    mount(SettingsPanel, { props: { open: false, settings: SETTINGS } });
    expect(document.querySelector('[data-testid="settings.root"]')).toBeNull();
  });

  it("seeds the three fields from the current settings", async () => {
    await openPanel({
      opening_balance_k: 123.5,
      opening_balance_date: "2026-03-09",
      reserve_k: 7.25,
    });

    expect(value("settings.balance")).toBe("123.5");
    expect(value("settings.date")).toBe("2026-03-09");
    expect(value("settings.reserve")).toBe("7.25");
  });

  it("saves exactly what is in the three fields", async () => {
    const wrapper = await openPanel();
    await at("settings.balance").setValue("80.5");
    await at("settings.date").setValue("2026-02-01");
    await at("settings.reserve").setValue("10");

    await at("settings.save").trigger("click");

    expect(lastSave(wrapper)).toEqual({
      opening_balance_k: 80.5,
      opening_balance_date: "2026-02-01",
      reserve_k: 10,
    });
  });

  it("accepts a negative opening balance", async () => {
    const wrapper = await openPanel();
    await at("settings.balance").setValue("-12");

    await at("settings.save").trigger("click");

    expect(lastSave(wrapper)).toMatchObject({ opening_balance_k: -12 });
  });

  describe("refusing to save", () => {
    it("emits nothing when the balance is not a number", async () => {
      const wrapper = await openPanel();
      await at("settings.balance").setValue("");

      await at("settings.save").trigger("click");

      expect(wrapper.emitted("save")).toBeUndefined();
    });

    it("emits nothing when the date is empty", async () => {
      const wrapper = await openPanel();
      await at("settings.date").setValue("");

      await at("settings.save").trigger("click");

      expect(wrapper.emitted("save")).toBeUndefined();
    });
  });

  it("falls back to a 5k reserve when the reserve box is emptied", async () => {
    const wrapper = await openPanel();
    await at("settings.reserve").setValue("");

    await at("settings.save").trigger("click");

    expect(lastSave(wrapper)).toMatchObject({ reserve_k: 5 });
  });

  it("keeps a deliberate zero reserve rather than defaulting it", async () => {
    const wrapper = await openPanel();
    await at("settings.reserve").setValue("0");

    await at("settings.save").trigger("click");

    expect(lastSave(wrapper)).toMatchObject({ reserve_k: 0 });
  });

  it("closes from Cancel and from the backdrop without saving", async () => {
    const wrapper = await openPanel();
    await at("settings.cancel").trigger("click");
    await at("settings.backdrop").trigger("click");

    expect(wrapper.emitted("close")).toHaveLength(2);
    expect(wrapper.emitted("save")).toBeUndefined();
  });
});
