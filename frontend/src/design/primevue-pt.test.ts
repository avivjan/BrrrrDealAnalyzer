// @vitest-environment jsdom
import { describe, expect, it } from "vitest";
import { mount, type VueWrapper } from "@vue/test-utils";
import PrimeVue from "primevue/config";
import type { Plugin } from "vue";
import InputNumber from "primevue/inputnumber";
import Slider from "primevue/slider";
import ToggleSwitch from "primevue/toggleswitch";

import { primevuePt } from "./primevue-pt";

/** The app's own PrimeVue registration, so the tests style what ships. */
const plugins: [Plugin, ...unknown[]][] = [
  [
    PrimeVue,
    {
      unstyled: true,
      pt: primevuePt,
      ptOptions: { mergeSections: true, mergeProps: true },
    },
  ],
];

/** The classes PrimeVue put on one pass-through section of a component. */
const classesOf = (wrapper: VueWrapper, section: string): string[] =>
  wrapper.find(`[data-pc-section="${section}"]`).classes();

describe("the global PrimeVue pass-through preset", () => {
  describe("slider", () => {
    const mountSlider = () =>
      mount(Slider, { props: { modelValue: 60, min: 0, max: 100 }, global: { plugins } });

    it("paints the filled range with the primary token", () => {
      expect(classesOf(mountSlider(), "range")).toEqual(
        "bg-primary h-full rounded-full absolute top-0 left-0".split(" "),
      );
    });

    it("gives the handle a 24 px target, the WCAG 2.5.8 minimum", () => {
      // w-6/h-6 = 24 px, with the negative margins halved to match so the
      // thumb stays centred on the track.
      const handle = classesOf(mountSlider(), "handle");
      expect(handle).toContain("w-6");
      expect(handle).toContain("h-6");
      expect(handle).toContain("-mt-3");
      expect(handle).toContain("-ml-3");
    });

    it("outlines the handle with the primary token and rings on focus-visible", () => {
      const handle = classesOf(mountSlider(), "handle");
      expect(handle).toContain("border-primary");
      expect(handle).toContain("focus-visible:ring-2");
      expect(handle).toContain("focus-visible:ring-ring");
      // Keyboard-only ring: a pointer drag must not light it up.
      expect(handle).not.toContain("focus:ring-2");
    });

    it("keeps the shape and affordance the handle had before the preset", () => {
      const handle = classesOf(mountSlider(), "handle");
      for (const kept of [
        "bg-white",
        "border-2",
        "rounded-full",
        "absolute",
        "top-1/2",
        "shadow-md",
        "hover:scale-110",
        "transition-transform",
        "focus:outline-none",
      ]) {
        expect(handle).toContain(kept);
      }
    });

    it("carries no blue-500 literal anywhere", () => {
      const html = mountSlider().html();
      expect(html).not.toContain("blue-500");
      expect(html).not.toContain("blue-300");
    });
  });

  describe("toggleswitch", () => {
    const mountToggle = (modelValue: boolean) =>
      mount(ToggleSwitch, { props: { modelValue }, global: { plugins } });

    it("is muted when off", () => {
      expect(classesOf(mountToggle(false), "slider")).toContain("bg-fg-muted/60");
    });

    it("is primary when on", () => {
      expect(classesOf(mountToggle(true), "slider")).toContain("bg-primary");
    });

    it("flips as the bound value changes", async () => {
      const wrapper = mountToggle(false);
      expect(classesOf(wrapper, "slider")).toContain("bg-fg-muted/60");
      await wrapper.setProps({ modelValue: true });
      expect(classesOf(wrapper, "slider")).toContain("bg-primary");
      await wrapper.setProps({ modelValue: false });
      expect(classesOf(wrapper, "slider")).toContain("bg-fg-muted/60");
    });

    it("gives the root the 44x24 box the switch is drawn in", () => {
      // Without this the control was a bare native checkbox: `slider` was the
      // only themed section and it had no size to fill.
      const root = classesOf(mountToggle(true), "root");
      for (const kept of ["relative", "inline-flex", "h-6", "w-11", "rounded-full"]) {
        expect(root).toContain(kept);
      }
    });

    it("keeps the native checkbox over the whole control, invisible", () => {
      // Transparent rather than removed: the input still owns the click, the
      // keyboard and the `role=switch` announcement.
      const input = classesOf(mountToggle(true), "input");
      for (const kept of ["peer", "absolute", "inset-0", "h-full", "w-full", "opacity-0"]) {
        expect(input).toContain(kept);
      }
    });

    it("rings the track when the input behind it takes keyboard focus", () => {
      const slider = classesOf(mountToggle(false), "slider");
      expect(slider).toContain("peer-focus-visible:ring-2");
      expect(slider).toContain("peer-focus-visible:ring-ring");
      // A pointer press must not light it up.
      expect(slider).not.toContain("ring-2");
    });

    it("slides the handle across as the value flips", async () => {
      const wrapper = mountToggle(false);
      expect(classesOf(wrapper, "handle")).toContain("translate-x-0.5");
      await wrapper.setProps({ modelValue: true });
      expect(classesOf(wrapper, "handle")).toContain("translate-x-[1.375rem]");
      // 22px = the 44px track less the 20px knob less its 2px inset.
      expect(classesOf(wrapper, "handle")).toContain("w-5");
      expect(classesOf(wrapper, "handle")).toContain("h-5");
    });

    it("carries no gray or blue literal anywhere", () => {
      const html = mountToggle(true).html();
      expect(html).not.toContain("blue-");
      expect(html).not.toContain("gray-");
    });
  });

  describe("inputnumber", () => {
    const input = (wrapper: VueWrapper) =>
      wrapper.find('[data-pc-section="root"][data-pc-name="pcinputtext"]');

    it("defaults a bare InputNumber to the token field styling", () => {
      const classes = input(
        mount(InputNumber, { props: { modelValue: 12 }, global: { plugins } }),
      ).classes();
      expect(classes).toEqual(
        [
          "w-full",
          "bg-surface",
          "border",
          "border-line",
          "rounded-ctl",
          "px-3",
          "py-2",
          "text-fg",
          "placeholder:text-fg-muted",
          "focus:outline-none",
          "focus-visible:ring-2",
          "focus-visible:ring-ring",
          "transition-all",
          "hover:bg-surface-muted",
        ],
      );
    });

    it("stands aside entirely when the call site brings its own inputClass", () => {
      // Both of this app's InputNumber call sites do, which is why wiring the
      // preset left their markup byte-identical.
      const own = "w-full text-right border border-gray-300";
      const classes = input(
        mount(InputNumber, {
          props: { modelValue: 12, inputClass: own },
          global: { plugins },
        }),
      ).classes();
      expect(classes).toEqual(own.split(" "));
    });
  });
});
