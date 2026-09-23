// @vitest-environment jsdom
import { afterEach, describe, expect, it } from "vitest";
import { mount, type VueWrapper } from "@vue/test-utils";
import { nextTick } from "vue";

import GenerateReportResultPickerPopup from "./GenerateReportResultPickerPopup.vue";
import { BRRRR_REPORT_RESULT_TILES, FLIP_REPORT_RESULT_TILES } from "./reportResultTiles";

let wrapper: VueWrapper | null = null;

afterEach(() => {
  wrapper?.unmount();
  wrapper = null;
  document.body.innerHTML = "";
});

const BRRRR_ANALYSIS = { cash_flow: 85.04, cash_on_cash: -1, dscr: 1.3647, total_cash_needed_for_deal: 77542.21 };

const mountPicker = (props: Record<string, unknown> = {}) =>
  mount(GenerateReportResultPickerPopup, {
    attachTo: document.body,
    props: { open: true, dealType: "BRRRR", analysis: BRRRR_ANALYSIS, ...props },
  });

const picker = () => document.querySelector('[data-testid="generate-report-result-picker"]');
const options = () => [...document.querySelectorAll('[data-part="result-option"]')] as HTMLElement[];
const checkboxOf = (resultKey: string) =>
  document.querySelector(`[data-result-key="${resultKey}"] input`) as HTMLInputElement;
const part = (name: string) => document.querySelector(`[data-part="${name}"]`) as HTMLButtonElement;
const checkedKeys = () => options().filter((o) => (o.querySelector("input") as HTMLInputElement).checked).map((o) => o.dataset.resultKey);

describe("GenerateReportResultPickerPopup", () => {
  it("renders nothing while closed", async () => {
    wrapper = mountPicker({ open: false });
    await nextTick();
    expect(picker()).toBeNull();
  });

  it("lists every BRRRR result tile in tile order with its caption and value, all checked", async () => {
    wrapper = mountPicker();
    await nextTick();
    expect(document.querySelector("h2")!.textContent!.trim()).toBe("Generate Report");
    expect(options().map((o) => o.dataset.resultKey)).toEqual(BRRRR_REPORT_RESULT_TILES.map((t) => t.resultKey));
    expect(options().map((o) => o.querySelector('[data-part="result-option-label"]')!.textContent!.trim())).toEqual(
      BRRRR_REPORT_RESULT_TILES.map((t) => t.tileLabel),
    );
    expect(checkedKeys()).toEqual(BRRRR_REPORT_RESULT_TILES.map((t) => t.resultKey));
    const valueOf = (key: string) => document.querySelector(`[data-result-key="${key}"] [data-part="result-option-value"]`)!.textContent!.trim();
    expect(valueOf("cash_flow")).toBe("$85.04");
    expect(valueOf("cash_on_cash")).toBe("∞%");
    expect(valueOf("dscr")).toBe("1.36x");
    expect(valueOf("equity")).toBe("");
    expect(part("selected-count").textContent!.trim()).toBe("12 of 12 selected");
  });

  it("lists the flip tiles for a flip deal", async () => {
    wrapper = mountPicker({ dealType: "FLIP", analysis: {} });
    await nextTick();
    expect(options().map((o) => o.dataset.resultKey)).toEqual(FLIP_REPORT_RESULT_TILES.map((t) => t.resultKey));
  });

  it("emits the checked keys in tile order after unchecking some", async () => {
    wrapper = mountPicker();
    await nextTick();
    checkboxOf("cash_out").click();
    checkboxOf("dscr").click();
    await nextTick();
    expect(part("selected-count").textContent!.trim()).toBe("10 of 12 selected");
    part("generate").click();
    await nextTick();
    const expected = BRRRR_REPORT_RESULT_TILES.map((t) => t.resultKey).filter((k) => k !== "cash_out" && k !== "dscr");
    expect(wrapper.emitted("generate")).toEqual([[expected]]);
  });

  it("Clear all disables Generate; Select all brings every result back", async () => {
    wrapper = mountPicker();
    await nextTick();
    expect(part("select-all").disabled).toBe(true);
    part("clear-all").click();
    await nextTick();
    expect(checkedKeys()).toEqual([]);
    expect(part("generate").disabled).toBe(true);
    part("generate").click();
    await nextTick();
    expect(wrapper.emitted("generate")).toBeUndefined();
    checkboxOf("roi").click();
    await nextTick();
    part("generate").click();
    await nextTick();
    expect(wrapper.emitted("generate")).toEqual([[["roi"]]]);
    part("select-all").click();
    await nextTick();
    expect(checkedKeys()).toHaveLength(12);
  });

  it("re-checks everything each time it opens", async () => {
    wrapper = mountPicker();
    await nextTick();
    part("clear-all").click();
    await wrapper.setProps({ open: false });
    await wrapper.setProps({ open: true });
    await nextTick();
    expect(checkedKeys()).toHaveLength(12);
  });

  it("closes on Cancel, the close button, the scrim and Escape, claiming the Escape", async () => {
    wrapper = mountPicker();
    await nextTick();
    part("cancel").click();
    part("close").click();
    (picker() as HTMLElement).click();
    const escape = new KeyboardEvent("keydown", { key: "Escape", cancelable: true });
    document.dispatchEvent(escape);
    expect(escape.defaultPrevented).toBe(true);
    expect(wrapper.emitted("close")).toHaveLength(4);
  });
});
