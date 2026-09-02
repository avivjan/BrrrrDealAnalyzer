// @vitest-environment jsdom
import { describe, expect, it } from "vitest";
import { mount } from "@vue/test-utils";

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
});
