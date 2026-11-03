// @vitest-environment jsdom
import { describe, expect, it } from "vitest";
import { mount } from "@vue/test-utils";

import PercentOfRentOrMonthlyDollarsInput from "./PercentOfRentOrMonthlyDollarsInput.vue";

const fieldStub = (name: string) => ({
  name,
  props: ["modelValue", "label", "suffix", "info", "errorMessage"],
  emits: ["update:modelValue"],
  template: `<div :data-label="label" />`,
});
const stubs = { NumberInput: fieldStub("NumberInput"), MoneyInput: fieldStub("MoneyInput") };

const mountReserve = (props: { percentOfRent: number | null; monthlyDollars: number | null; monthlyRentDollars: number | null }) =>
  mount(PercentOfRentOrMonthlyDollarsInput, { props: { label: "Vacancy", ...props }, global: { stubs } });
const unitButton = (wrapper: ReturnType<typeof mountReserve>, unit: "percentOfRent" | "monthlyDollars") =>
  wrapper.find(`[data-part="unit-toggle"] [data-unit="${unit}"]`);

describe("PercentOfRentOrMonthlyDollarsInput", () => {
  it("is a percentage of the rent while no dollars are typed, with the dollars shown under it", () => {
    const wrapper = mountReserve({ percentOfRent: 5, monthlyDollars: null, monthlyRentDollars: 1500 });
    expect(wrapper.attributes("data-unit")).toBe("percentOfRent");
    expect(wrapper.findComponent({ name: "NumberInput" }).props()).toMatchObject({ modelValue: 5, label: "Vacancy", suffix: "%" });
    expect(wrapper.findComponent({ name: "MoneyInput" }).exists()).toBe(false);
    expect(unitButton(wrapper, "percentOfRent").attributes("aria-checked")).toBe("true");
    expect(wrapper.find('[data-part="other-unit"]').text()).toBe("of rent · ≈ $75/mo");
  });

  it("is dollars per month once they are typed, with the percentage shown under it", () => {
    const wrapper = mountReserve({ percentOfRent: 5, monthlyDollars: 90, monthlyRentDollars: 1500 });
    expect(wrapper.attributes("data-unit")).toBe("monthlyDollars");
    expect(wrapper.findComponent({ name: "MoneyInput" }).props("modelValue")).toBe(90);
    expect(unitButton(wrapper, "monthlyDollars").attributes("aria-checked")).toBe("true");
    expect(wrapper.find('[data-part="other-unit"]').text()).toBe("per month · ≈ 6% of rent");
  });

  it("switching to $ seeds the dollars with what the percentage gives today", async () => {
    const wrapper = mountReserve({ percentOfRent: 5, monthlyDollars: null, monthlyRentDollars: 1525 });
    await unitButton(wrapper, "monthlyDollars").trigger("click");
    expect(wrapper.emitted("update:monthlyDollars")).toEqual([[76.25]]);
    expect(wrapper.emitted("update:percentOfRent")).toBeUndefined();
  });

  it("switching back to % clears the dollars and seeds the percentage from them", async () => {
    const wrapper = mountReserve({ percentOfRent: 5, monthlyDollars: 120, monthlyRentDollars: 1500 });
    await unitButton(wrapper, "percentOfRent").trigger("click");
    expect(wrapper.emitted("update:percentOfRent")).toEqual([[8]]);
    expect(wrapper.emitted("update:monthlyDollars")).toEqual([[null]]);
  });

  it("without a rent, $ starts at $0 and % keeps its own value", async () => {
    const withoutRent = mountReserve({ percentOfRent: 5, monthlyDollars: null, monthlyRentDollars: 0 });
    expect(withoutRent.find('[data-part="other-unit"]').text()).toBe("of the monthly rent");
    await unitButton(withoutRent, "monthlyDollars").trigger("click");
    expect(withoutRent.emitted("update:monthlyDollars")).toEqual([[0]]);

    const backToPercent = mountReserve({ percentOfRent: 5, monthlyDollars: 50, monthlyRentDollars: null });
    await unitButton(backToPercent, "percentOfRent").trigger("click");
    expect(backToPercent.emitted("update:percentOfRent")).toBeUndefined();
    expect(backToPercent.emitted("update:monthlyDollars")).toEqual([[null]]);
  });

  it("clicking the unit already chosen does nothing, and the arrow keys switch it", async () => {
    const wrapper = mountReserve({ percentOfRent: 5, monthlyDollars: null, monthlyRentDollars: 1500 });
    await unitButton(wrapper, "percentOfRent").trigger("click");
    expect(wrapper.emitted("update:monthlyDollars")).toBeUndefined();
    await wrapper.find('[data-part="unit-toggle"]').trigger("keydown", { key: "ArrowRight" });
    expect(wrapper.emitted("update:monthlyDollars")).toEqual([[75]]);
  });

  it("is an accessible radiogroup with labelled options", () => {
    const toggle = mountReserve({ percentOfRent: 5, monthlyDollars: null, monthlyRentDollars: 1500 }).find('[data-part="unit-toggle"]');
    expect(toggle.attributes("role")).toBe("radiogroup");
    expect(toggle.attributes("aria-label")).toBe("Vacancy: percent of rent or dollars per month");
    expect(toggle.findAll('[role="radio"]').map((radio) => radio.attributes("aria-label"))).toEqual(["Percent of rent", "Dollars per month"]);
  });

  it("hands each field its own error message", () => {
    const wrapper = mount(PercentOfRentOrMonthlyDollarsInput, {
      props: { label: "Vacancy", percentOfRent: 5, monthlyDollars: -1, monthlyRentDollars: 1500, dollarsErrorMessage: "Monthly vacancy reserve cannot be negative." },
      global: { stubs },
    });
    expect(wrapper.findComponent({ name: "MoneyInput" }).props("errorMessage")).toBe("Monthly vacancy reserve cannot be negative.");
  });
});
