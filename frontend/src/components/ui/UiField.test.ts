// @vitest-environment jsdom
import { describe, expect, it } from "vitest";
import { h, nextTick, ref, type VNode } from "vue";
import { mount } from "@vue/test-utils";

import UiField from "./UiField.vue";

/** What the default slot is handed. Mirrors the component's scoped props. */
interface ControlProps {
  id: string;
  describedBy?: string;
  invalid: boolean;
}

/** The control the *parent* renders — the shape every real call site has. */
function control(props: ControlProps): VNode {
  return h("input", {
    id: props.id,
    "aria-describedby": props.describedBy,
    "aria-invalid": props.invalid ? "true" : undefined,
  });
}

function mountField(
  props: Record<string, unknown> = {},
  slots: Record<string, unknown> = {},
  attrs: Record<string, unknown> = {},
) {
  return mount(UiField, {
    props,
    attrs,
    slots: { label: "Purchase price", default: control, ...slots },
  });
}

describe("UiField", () => {
  describe("the label and the control it names", () => {
    it("points the label at the id the control was handed", () => {
      const wrapper = mountField();
      const id = wrapper.get("input").attributes("id");
      expect(id).toBeTruthy();
      expect(wrapper.get("label").attributes("for")).toBe(id);
    });

    it("uses an explicit id when one is given", () => {
      const wrapper = mountField({ id: "purchase-price" });
      expect(wrapper.get("label").attributes("for")).toBe("purchase-price");
      expect(wrapper.get("input").attributes("id")).toBe("purchase-price");
    });

    // `useId()` counts per app, so two fields on the same page — the case that
    // actually matters — must not collide. Two separate `mount()` calls are two
    // apps and legitimately restart the counter.
    it("generates a different id for every field on a page", () => {
      const page = mount({
        render: () => [
          h(UiField, null, { label: () => "Price", default: control }),
          h(UiField, null, { label: () => "Rate", default: control }),
        ],
      });
      const ids = page.findAll("input").map((input) => input.attributes("id"));
      expect(ids).toHaveLength(2);
      expect(ids[0]).toBeTruthy();
      expect(new Set(ids).size).toBe(2);
    });

    it("renders no label element when the slot is absent", () => {
      const wrapper = mount(UiField, { slots: { default: control } });
      expect(wrapper.find("label").exists()).toBe(false);
    });

    it("renders no control of its own", () => {
      const wrapper = mount(UiField, { slots: { label: "Price" } });
      expect(wrapper.find("input").exists()).toBe(false);
      expect(wrapper.find("select").exists()).toBe(false);
      expect(wrapper.find("textarea").exists()).toBe(false);
    });
  });

  describe("the required marker", () => {
    it("hides the asterisk from assistive tech and spells the word out", () => {
      const wrapper = mountField({ required: true });
      const marker = wrapper.get('[data-part="required"]');
      expect(marker.text()).toBe("*");
      expect(marker.attributes("aria-hidden")).toBe("true");
      expect(wrapper.get("label .sr-only").text()).toBe("required");
    });

    it("shows neither when the field is optional", () => {
      const wrapper = mountField();
      expect(wrapper.find('[data-part="required"]').exists()).toBe(false);
      expect(wrapper.find("label .sr-only").exists()).toBe(false);
    });
  });

  describe("the messages and what describes the control", () => {
    it("describes the control with the helper text", () => {
      const wrapper = mountField({}, { helper: "Before closing costs" });
      const helper = wrapper.get("p");
      expect(helper.text()).toBe("Before closing costs");
      expect(helper.classes()).toContain("text-fg-muted");
      expect(wrapper.get("input").attributes("aria-describedby")).toBe(helper.attributes("id"));
    });

    it("announces the error and lists it after the helper", () => {
      const wrapper = mountField({}, { helper: "Before closing costs", error: "Required" });
      const helperId = wrapper.get("p").attributes("id");
      const error = wrapper.get('p[role="alert"]');
      expect(error.classes()).toContain("text-negative");
      expect(wrapper.get("input").attributes("aria-describedby")).toBe(
        `${helperId} ${error.attributes("id")}`,
      );
    });

    it("describes the control with the error alone when there is no helper", () => {
      const wrapper = mountField({}, { error: "Required" });
      expect(wrapper.get("input").attributes("aria-describedby")).toBe(
        wrapper.get("p").attributes("id"),
      );
    });

    it("leaves aria-describedby off when neither message is given", () => {
      expect(mountField().get("input").attributes("aria-describedby")).toBeUndefined();
    });

    it("renders no error paragraph unless the slot is passed", () => {
      expect(mountField().findAll("p")).toHaveLength(0);
    });

    it("keeps the message ids inside the field's own namespace", () => {
      const wrapper = mountField({ id: "loan-term" }, { helper: "Years", error: "Required" });
      const ids = wrapper.findAll("p").map((p) => p.attributes("id"));
      expect(ids.every((id) => id?.startsWith("loan-term"))).toBe(true);
      expect(new Set(ids).size).toBe(2);
    });
  });

  describe("what the scoped slot carries", () => {
    /**
     * The regression this guards: slots are a plain object that Vue mutates in
     * place, so nothing reading `useSlots()` is reactive. Behind a `computed`,
     * `describedBy` froze at whatever the first render saw — an error that
     * appeared later never reached `aria-describedby`, and a field mounted with
     * an error already showing kept pointing at it after it cleared.
     */
    it("follows an error slot that appears and disappears after mount", async () => {
      const showError = ref(false);
      const page = mount({
        render: () =>
          h(UiField, null, {
            label: () => "Price",
            default: control,
            ...(showError.value ? { error: () => "Required" } : {}),
          }),
      });

      expect(page.get("input").attributes("aria-describedby")).toBeUndefined();

      showError.value = true;
      await nextTick();
      const error = page.get('p[role="alert"]');
      expect(page.get("input").attributes("aria-describedby")).toBe(error.attributes("id"));

      showError.value = false;
      await nextTick();
      expect(page.find('p[role="alert"]').exists()).toBe(false);
      expect(page.get("input").attributes("aria-describedby")).toBeUndefined();
    });

    it("hands the control its invalid state", () => {
      expect(mountField({ invalid: true }).get("input").attributes("aria-invalid")).toBe("true");
      expect(mountField().get("input").attributes("aria-invalid")).toBeUndefined();
    });
  });

  describe("presentation", () => {
    it("hard-codes no copy beyond the visually hidden required word", () => {
      expect(mountField().text()).toBe("Purchase price");
    });

    it("lays the label beside the control only when inline", () => {
      expect(mountField({ inline: true }).classes()).toContain("flex");
      expect(mountField().classes()).not.toContain("flex");
    });

    it("uses tokens for every colour it sets", () => {
      const wrapper = mountField({}, { helper: "Hint", error: "Bad" });
      expect(wrapper.html()).not.toMatch(/\b(bg|text|border)-(gray|slate|blue|indigo|red|amber)-\d/);
    });

    it("leaves the class attribute off entirely when it has nothing to say", () => {
      // A block field composes to no classes at all; `:class=""` would still
      // render a bare `class=""` into every snapshot and devtools tree.
      expect(mountField().attributes("class")).toBeUndefined();
      expect(mountField().html()).not.toContain('class=""');
    });

    it("passes attrs through to the root and merges class through cn()", () => {
      const wrapper = mountField({}, {}, { "data-testid": "deal.price", class: "col-span-2" });
      expect(wrapper.attributes("data-ui")).toBe("field");
      expect(wrapper.attributes("data-testid")).toBe("deal.price");
      expect(wrapper.classes()).toContain("col-span-2");
    });
  });
});
