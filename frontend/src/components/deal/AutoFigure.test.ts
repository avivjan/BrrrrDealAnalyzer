// @vitest-environment jsdom
import { describe, expect, it } from "vitest";
import { mount } from "@vue/test-utils";

import AutoFigure from "./AutoFigure.vue";

const mountFigure = (props: Partial<InstanceType<typeof AutoFigure>["$props"]> = {}) =>
  mount(AutoFigure, { props: { label: "Seller Tax Credit", value: 88.77, ...props } });

describe("AutoFigure", () => {
  it("is a read-only figure by default", () => {
    const wrapper = mountFigure();
    expect(wrapper.find('[data-part="value"]').text()).toBe("$88.77");
    expect(wrapper.find('[data-part="edit"]').exists()).toBe(false);
    expect(wrapper.find('[data-part="edit-input"]').exists()).toBe(false);
  });

  it("renders nothing while the value is missing, even when editable", () => {
    expect(mountFigure({ value: null, editable: true }).find('[data-ui="auto-figure"]').exists()).toBe(false);
  });

  it("shows a named pencil only when editable", () => {
    const pencil = mountFigure({ editable: true, editAriaLabel: "Type the credit received at closing" }).find('[data-part="edit"]');
    expect(pencil.exists()).toBe(true);
    expect(pencil.attributes("aria-label")).toBe("Type the credit received at closing");
    expect(mountFigure({ editable: true }).find('[data-part="edit"]').attributes("aria-label")).toBe("Edit Seller Tax Credit");
  });

  it("opens a box seeded with the value and commits the typed dollars on Enter, once", async () => {
    const wrapper = mountFigure({ editable: true });
    await wrapper.find('[data-part="edit"]').trigger("click");
    const box = wrapper.find('[data-part="edit-input"]');
    expect(box.exists()).toBe(true);
    expect((box.element as HTMLInputElement).value).toBe("88.77");
    expect(box.attributes("aria-label")).toBe("Edit Seller Tax Credit");
    expect(wrapper.find('[data-part="value"]').exists()).toBe(false);

    await box.setValue("177.53");
    await box.trigger("keydown", { key: "Enter" });
    await box.trigger("blur"); // the browser blurs after Enter; it must not commit a second time
    expect(wrapper.emitted("commitEditedValue")).toEqual([[177.53]]);
    expect(wrapper.find('[data-part="edit-input"]').exists()).toBe(false);
    expect(wrapper.find('[data-part="value"]').exists()).toBe(true);
  });

  it("commits on blur and reads the typed amount as plain dollars, not thousands", async () => {
    const wrapper = mountFigure({ editable: true });
    await wrapper.find('[data-part="edit"]').trigger("click");
    const box = wrapper.find('[data-part="edit-input"]');
    await box.setValue("250");
    await box.trigger("blur");
    expect(wrapper.emitted("commitEditedValue")).toEqual([[250]]);
  });

  it("abandons the edit on Escape or an empty box without emitting", async () => {
    const wrapper = mountFigure({ editable: true });
    await wrapper.find('[data-part="edit"]').trigger("click");
    let box = wrapper.find('[data-part="edit-input"]');
    await box.setValue("999");
    await box.trigger("keydown", { key: "Escape" });
    await box.trigger("blur");
    expect(wrapper.emitted("commitEditedValue")).toBeUndefined();
    expect(wrapper.find('[data-part="value"]').text()).toBe("$88.77");

    await wrapper.find('[data-part="edit"]').trigger("click");
    box = wrapper.find('[data-part="edit-input"]');
    await box.setValue("");
    await box.trigger("keydown", { key: "Enter" });
    expect(wrapper.emitted("commitEditedValue")).toBeUndefined();
  });
});
