// @vitest-environment jsdom
import { describe, expect, it } from "vitest";
import { mount } from "@vue/test-utils";

import ResultTileWithCalculationButton from "./ResultTileWithCalculationButton.vue";

const mountTile = () =>
  mount(ResultTileWithCalculationButton, {
    props: { metricLabel: "Cash Flow", metricKey: "cash_flow" },
    slots: {
      default: '<div data-testid="mydeals.modal.result.cash_flow" class="text-positive">$350</div>',
    },
  });

describe("ResultTileWithCalculationButton", () => {
  it("renders the caption with a calculator hint and the slotted value element untouched", () => {
    const wrapper = mountTile();
    expect(wrapper.get('[data-part="label"]').text()).toBe("Cash Flow");
    expect(wrapper.find('[data-part="label"] .pi-calculator').exists()).toBe(true);
    const value = wrapper.get('[data-testid="mydeals.modal.result.cash_flow"]');
    expect(value.text()).toBe("$350");
    expect(value.classes()).toContain("text-positive");
  });

  it("exposes one type=button named after the metric, laid over the tile", () => {
    const wrapper = mountTile();
    const button = wrapper.get('[data-testid="result-tile.cash_flow.show-calculation"]');
    expect(button.element.tagName).toBe("BUTTON");
    expect(button.attributes("type")).toBe("button");
    expect(button.attributes("aria-label")).toBe("Show how Cash Flow is calculated");
    expect(button.classes()).toContain("absolute");
    // The button is a sibling of the tile, never its parent: a <div> may not live inside a <button>.
    expect(button.find('[data-ui="stat-tile"]').exists()).toBe(false);
  });

  it("emits showCalculation with the metric key and label when pressed", async () => {
    const wrapper = mountTile();
    await wrapper.get('[data-testid="result-tile.cash_flow.show-calculation"]').trigger("click");
    expect(wrapper.emitted("showCalculation")).toEqual([
      [{ metricKey: "cash_flow", metricLabel: "Cash Flow" }],
    ]);
  });
});
