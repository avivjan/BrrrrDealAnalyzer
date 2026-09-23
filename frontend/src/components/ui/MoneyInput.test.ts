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

    describe("a field the analysis cannot run without", () => {
      it("while empty: no '$0', a placeholder, a NEEDED pill and a strong tinted border", () => {
        for (const modelValue of [null, 0]) {
          const wrapper = mountInput({ neededToRunAnalysis: true, modelValue, inThousands: true });
          const input = wrapper.get("input");
          expect(input.element.value).toBe("");
          expect(input.attributes("placeholder")).toBe("Type to get a first result");
          expect(input.classes()).toContain("border-primary");
          expect(input.classes()).toContain("bg-primary/5");
          const label = wrapper.get("label");
          expect(label.classes()).toContain("font-semibold");
          expect(label.classes()).toContain("text-primary");
          expect(label.attributes("data-needed")).toBe("missing");
          expect(wrapper.get('[data-part="needed"]').text()).toMatch(/needed/i);
          expect(wrapper.find('[data-part="needed-done"]').exists()).toBe(false);
        }
      });

      it("once a value is in: the amount, a check instead of the pill, and a calm border", () => {
        const wrapper = mountInput({ neededToRunAnalysis: true, modelValue: 200, inThousands: true });
        const input = wrapper.get("input");
        expect(input.element.value).toBe("$200,000");
        expect(input.classes()).toContain("border-primary/40");
        expect(input.classes()).not.toContain("bg-primary/5");
        expect(wrapper.get("label").attributes("data-needed")).toBe("filled");
        expect(wrapper.find('[data-part="needed"]').exists()).toBe(false);
        expect(wrapper.get('[data-part="needed-done"]').find("i.pi-check-circle").exists()).toBe(true);
      });

      it("keeps a caller's placeholder and still commits what is typed", async () => {
        const wrapper = mountInput({ neededToRunAnalysis: true, modelValue: 0, inThousands: true, placeholder: "Custom" });
        expect(wrapper.get("input").attributes("placeholder")).toBe("Custom");
        expect(await type(wrapper, "200000")).toBe(200);
      });

      it("leaves a plain field alone: '$0' stays, no pill, no tint", () => {
        const wrapper = mountInput({ modelValue: 0, label: "Monthly HOA" });
        expect(wrapper.get("input").element.value).toBe("$0");
        expect(wrapper.get("input").attributes("placeholder")).toBeUndefined();
        expect(wrapper.find('[data-part="needed"]').exists()).toBe(false);
        expect(wrapper.get("label").attributes("data-needed")).toBeUndefined();
        expect(wrapper.get("input").classes()).not.toContain("bg-primary/5");
      });

      it("keeps the emphasis and the required asterisk independent", () => {
        const plainRequired = mountInput({ required: true });
        expect(plainRequired.get("label").classes()).not.toContain("text-primary");
        expect(plainRequired.get("label").attributes("data-needed")).toBeUndefined();

        const neededButNotRequired = mountInput({ neededToRunAnalysis: true });
        expect(neededButNotRequired.find('[data-part="required"]').exists()).toBe(false);
      });
    });
  });
});
