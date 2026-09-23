// @vitest-environment jsdom
import { describe, expect, it } from "vitest";
import { flushPromises, mount } from "@vue/test-utils";

import MoneyInput from "./MoneyInput.vue";

function mountInput(props: Record<string, unknown> = {}) {
  return mount(MoneyInput, {
    props: { modelValue: null, label: "Purchase Price", ...props },
  });
}

/** Focus, type, blur — the full commit cycle the component is built around. */
async function type(wrapper: ReturnType<typeof mountInput>, text: string) {
  const input = wrapper.find("input");
  await input.trigger("focus");
  await input.setValue(text);
  await input.trigger("blur");
  const events = wrapper.emitted("update:modelValue");
  return events ? events[events.length - 1]![0] : undefined;
}

describe("MoneyInput", () => {
  describe("a field stored in thousands", () => {
    it("shows the stored thousands value as real dollars", () => {
      const wrapper = mountInput({ modelValue: 200, inThousands: true });
      expect(wrapper.find("input").element.value).toBe("$200,000");
    });

    it("emits thousands back, so the stored unit never changes", async () => {
      const wrapper = mountInput({ modelValue: 0, inThousands: true });
      // 50,500 dollars is 50.5 thousand — the exact value the old field could
      // not represent, because it rounded to whole thousands.
      expect(await type(wrapper, "50500")).toBe(50.5);
    });

    it("keeps the fast path: a bare number under 1,000 means thousands", async () => {
      const wrapper = mountInput({ modelValue: 0, inThousands: true });
      expect(await type(wrapper, "50")).toBe(50);
    });

    it("accepts k/m shorthand", async () => {
      expect(await type(mountInput({ inThousands: true }), "50k")).toBe(50);
      expect(await type(mountInput({ inThousands: true }), "1.2m")).toBe(1200);
    });

    it("takes an explicit $ as a literal small amount", async () => {
      const wrapper = mountInput({ modelValue: 0, inThousands: true });
      expect(await type(wrapper, "$800")).toBe(0.8);
    });
  });

  describe("a field stored in dollars", () => {
    it("neither scales the display nor the emitted value", async () => {
      const wrapper = mountInput({ modelValue: 2600, label: "Monthly Rent" });
      expect(wrapper.find("input").element.value).toBe("$2,600");
      // The shorthand must stay off here: a $50 HOA is $50, not $50,000.
      expect(await type(wrapper, "50")).toBe(50);
    });
  });

  describe("editing", () => {
    it("swaps the currency mask for plain digits while focused", async () => {
      const wrapper = mountInput({ modelValue: 50.5, inThousands: true });
      const input = wrapper.find("input");
      expect(input.element.value).toBe("$50,500");

      await input.trigger("focus");
      // Plain digits: no $, no commas, nothing for the caret to trip over.
      expect(input.element.value).toBe("50500");
    });

    it("emits null when cleared, rather than a default or a zero", async () => {
      const wrapper = mountInput({ modelValue: 200, inThousands: true });
      expect(await type(wrapper, "")).toBeNull();
    });

    it("abandons the edit on Escape", async () => {
      const wrapper = mountInput({ modelValue: 200, inThousands: true });
      const input = wrapper.find("input");
      await input.trigger("focus");
      await input.setValue("999");
      await input.trigger("keydown", { key: "Escape" });

      expect(wrapper.emitted("update:modelValue")).toBeUndefined();
    });

    it("emits nothing when focused and left without an edit", async () => {
      const wrapper = mountInput({ modelValue: 288, inThousands: true });
      const input = wrapper.find("input");
      await input.trigger("focus");
      await input.trigger("blur");

      expect(wrapper.emitted("update:modelValue")).toBeUndefined();
    });

    it("selects the whole editable value after the focus re-render, so typing replaces it", async () => {
      const wrapper = mount(MoneyInput, {
        props: { modelValue: 288, label: "Lowest ARV", inThousands: true },
        attachTo: document.body,
      });
      const inputElement = wrapper.find("input").element;
      inputElement.focus();
      await flushPromises();

      expect(inputElement.value).toBe("288000");
      expect([inputElement.selectionStart, inputElement.selectionEnd]).toEqual([0, "288000".length]);
      wrapper.unmount();
    });

    it("re-formats once focus leaves", async () => {
      const wrapper = mountInput({ modelValue: 0, inThousands: true });
      await type(wrapper, "50500");
      await wrapper.setProps({ modelValue: 50.5 });
      expect(wrapper.find("input").element.value).toBe("$50,500");
    });
  });

  it("hints at the reading only when it reinterpreted the number", async () => {
    const wrapper = mountInput({ modelValue: 0, inThousands: true });
    const input = wrapper.find("input");

    await input.trigger("focus");
    await input.setValue("50");
    expect(wrapper.text()).toContain("= $50,000");

    // Typed in full — echoing it back would be noise.
    await input.setValue("50500");
    expect(wrapper.text()).not.toContain("=");
  });

  it("renders the label without the old ($000s) qualifier", () => {
    // The field shows real dollars now, so the unit note would be a lie.
    const wrapper = mountInput({ inThousands: true });
    expect(wrapper.find("label").text()).toBe("Purchase Price");
  });

  describe("the field anatomy", () => {
    it("draws the label in the shared 20px row, with the hint beside it", async () => {
      const wrapper = mountInput({ modelValue: 0, inThousands: true });
      const row = wrapper.get('[data-part="label-row"]');
      expect(row.classes()).toContain("h-5");

      const input = wrapper.find("input");
      await input.trigger("focus");
      await input.setValue("50");
      // The hint shares the row rather than taking one of its own, so the
      // box below never moves when it appears.
      expect(row.find('[data-part="hint"]').exists()).toBe(true);
    });

    it("marks a required field with an asterisk for the eye and a word for the ear", () => {
      const wrapper = mountInput({ required: true });
      const marker = wrapper.get('label [data-part="required"]');
      expect(marker.text()).toBe("*");
      expect(marker.attributes("aria-hidden")).toBe("true");
      expect(wrapper.get("label .sr-only").text()).toBe("required");
    });

    it("shows no required marker when the field is optional", () => {
      const wrapper = mountInput();
      expect(wrapper.find('[data-part="required"]').exists()).toBe(false);
      expect(wrapper.find("label .sr-only").exists()).toBe(false);
    });

    it("emphasises a field the analysis cannot run without: bold primary label, primary border", () => {
      const wrapper = mountInput({ neededToRunAnalysis: true });
      const label = wrapper.get("label");
      expect(label.classes()).toContain("font-semibold");
      expect(label.classes()).toContain("text-primary");
      expect(label.attributes("data-needed")).toBe("true");
      expect(wrapper.get("input").classes()).toContain("border-primary/60");
    });

    it("keeps the emphasis and the required asterisk independent", () => {
      const plainRequired = mountInput({ required: true });
      expect(plainRequired.get("label").classes()).not.toContain("text-primary");
      expect(plainRequired.get("label").attributes("data-needed")).toBeUndefined();
      expect(plainRequired.get("input").classes()).not.toContain("border-primary/60");

      const neededButNotRequired = mountInput({ neededToRunAnalysis: true });
      expect(neededButNotRequired.find('[data-part="required"]').exists()).toBe(false);
    });
  });
});
