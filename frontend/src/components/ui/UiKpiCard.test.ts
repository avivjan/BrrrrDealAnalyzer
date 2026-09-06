// @vitest-environment jsdom
import { describe, expect, it } from "vitest";
import { mount } from "@vue/test-utils";

import UiKpiCard from "./UiKpiCard.vue";

describe("UiKpiCard", () => {
  it("renders label, value and delta from props in their regions", () => {
    const wrapper = mount(UiKpiCard, { props: { label: "Equity", value: "$1.23M", delta: "▲ +8.4%", tone: "positive" } });
    expect(wrapper.attributes("data-ui")).toBe("kpi-card");
    expect(wrapper.get('[data-part="label"]').text()).toBe("Equity");
    expect(wrapper.get('[data-part="value"]').text()).toBe("$1.23M");
    const delta = wrapper.get('[data-part="delta"]');
    expect(delta.text()).toBe("▲ +8.4%");
    expect(delta.classes()).toContain("text-positive");
  });

  it("sets the numeral in the display face with tabular digits", () => {
    const value = mount(UiKpiCard, { props: { label: "Doors", value: 12 } }).get('[data-part="value"]');
    expect(value.classes()).toEqual(expect.arrayContaining(["font-display", "numeric"]));
    expect(value.text()).toBe("12");
  });

  it("lets slots replace the props and adds a chart region only when given one", () => {
    const withChart = mount(UiKpiCard, {
      props: { label: "x", value: "1" },
      slots: { label: "<em>Doors</em>", value: "<b>12</b>", default: '<svg data-testid="spark" />', footer: "since Jan" },
    });
    expect(withChart.get('[data-part="label"]').html()).toContain("<em>Doors</em>");
    expect(withChart.get('[data-part="value"]').html()).toContain("<b>12</b>");
    expect(withChart.find('[data-part="chart"] [data-testid="spark"]').exists()).toBe(true);
    expect(withChart.get('[data-part="footer"]').text()).toBe("since Jan");

    const bare = mount(UiKpiCard, { props: { label: "x", value: "1" } });
    expect(bare.find('[data-part="chart"]').exists()).toBe(false);
    expect(bare.find('[data-part="delta"]').exists()).toBe(false);
    expect(bare.find('[data-part="footer"]').exists()).toBe(false);
  });

  it("colours only the delta, never the value, and uses tokens only", () => {
    const wrapper = mount(UiKpiCard, { props: { label: "Debt", value: "$2.9M", delta: "▼ −0.8%", tone: "negative" } });
    expect(wrapper.get('[data-part="value"]').classes()).not.toContain("text-negative");
    expect(wrapper.get('[data-part="delta"]').classes()).toContain("text-negative");
    expect(wrapper.html()).not.toMatch(/\b(bg|text|border)-(gray|slate|blue|indigo|red|amber)-\d/);
  });

  it("renders a decorative icon and forwards attrs", () => {
    const wrapper = mount(UiKpiCard, { props: { label: "x", value: 1, icon: "pi pi-home" }, attrs: { "data-testid": "kpi.doors" } });
    expect(wrapper.get("i").attributes("aria-hidden")).toBe("true");
    expect(wrapper.attributes("data-testid")).toBe("kpi.doors");
  });
});
