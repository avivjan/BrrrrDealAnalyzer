// @vitest-environment jsdom
import { describe, expect, it } from "vitest";
import { mount } from "@vue/test-utils";

import UiTooltip from "./UiTooltip.vue";

describe("UiTooltip", () => {
  const mountTip = (props: Record<string, unknown> = {}) =>
    mount(UiTooltip, {
      props: { content: "Cash left in the deal after refinance", ...props },
      slots: {
        default: `<template #default="{ describedBy }"><button :aria-describedby="describedBy">?</button></template>`,
      },
    });

  it("renders the content in a role=tooltip bubble the trigger is described by", () => {
    const wrapper = mountTip();
    const bubble = wrapper.get('[role="tooltip"]');
    expect(bubble.text()).toBe("Cash left in the deal after refinance");
    expect(bubble.attributes("id")).toBeTruthy();
    expect(wrapper.get("button").attributes("aria-describedby")).toBe(bubble.attributes("id"));
  });

  it("is hidden until hover or focus, and not rendered at all on touch", () => {
    const classes = mountTip().get('[data-part="bubble"]').classes();
    expect(classes).toContain("opacity-0");
    expect(classes).toContain("group-hover:opacity-100");
    expect(classes).toContain("group-focus-within:opacity-100");
    expect(classes).toContain("touch:hidden");
    // G-HOVER pairing, inert on touch because of the line above.
    expect(classes).toContain("touch:opacity-100");
    expect(classes).toContain("pointer-events-none");
  });

  it("places above by default and below on request", () => {
    expect(mountTip().get('[data-part="bubble"]').classes()).toContain("bottom-full");
    expect(mountTip({ placement: "bottom" }).get('[data-part="bubble"]').classes()).toContain("top-full");
  });

  it("gives distinct ids to two tooltips in the same app", () => {
    // Two separate `mount()`s are two apps, and `useId` restarts per app; the
    // real page is one app, so the pair is mounted together here.
    const page = mount({
      components: { UiTooltip },
      template: `<div><UiTooltip content="a"><button>a</button></UiTooltip><UiTooltip content="b"><button>b</button></UiTooltip></div>`,
    });
    const ids = page.findAll('[role="tooltip"]').map((el) => el.attributes("id"));
    expect(ids).toHaveLength(2);
    expect(new Set(ids).size).toBe(2);
  });
});
