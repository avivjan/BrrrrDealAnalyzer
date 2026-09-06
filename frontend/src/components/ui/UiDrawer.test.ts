// @vitest-environment jsdom
import { afterEach, describe, expect, it } from "vitest";
import { mount, type VueWrapper } from "@vue/test-utils";
import { nextTick } from "vue";

import UiDrawer from "./UiDrawer.vue";

let wrapper: VueWrapper | null = null;

afterEach(() => {
  wrapper?.unmount();
  wrapper = null;
  document.body.innerHTML = "";
});

const mountDrawer = (props: Record<string, unknown> = {}, slots: Record<string, string> = {}) =>
  mount(UiDrawer, {
    attachTo: document.body,
    props: { open: true, ...props },
    slots: { header: "Appearance", default: '<button id="first">Look</button>', ...slots },
  });

const drawer = () => document.querySelector('[data-ui="drawer"]');
const dialog = () => document.querySelector('[role="dialog"]');

describe("UiDrawer", () => {
  it("teleports a modal dialog to body, named by its header, on the requested side", async () => {
    wrapper = mountDrawer();
    await nextTick();
    expect(drawer()).not.toBeNull();
    expect(dialog()!.getAttribute("aria-modal")).toBe("true");
    const heading = document.querySelector("h2")!;
    expect(heading.textContent).toBe("Appearance");
    expect(dialog()!.getAttribute("aria-labelledby")).toBe(heading.id);
    expect(drawer()!.className).toContain("justify-end");
    expect(dialog()!.getAttribute("data-ui")).toBe("modal-panel");
  });

  it("renders nothing while closed and defers to an external labelledby", async () => {
    wrapper = mountDrawer({ open: false });
    await nextTick();
    expect(drawer()).toBeNull();
    wrapper.unmount();
    wrapper = mountDrawer({ labelledby: "settings-title", side: "left" });
    await nextTick();
    expect(dialog()!.getAttribute("aria-labelledby")).toBe("settings-title");
    expect(document.querySelector("h2")).toBeNull();
    expect(drawer()!.className).toContain("justify-start");
  });

  it("closes on Escape, on the scrim, and from its close button — and only then", async () => {
    wrapper = mountDrawer();
    await nextTick();
    (drawer() as HTMLElement).dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
    (drawer() as HTMLElement).click();
    (document.querySelector('[data-part="close"]') as HTMLElement).click();
    (dialog() as HTMLElement).click(); // inside the panel: not a close
    await nextTick();
    expect(wrapper.emitted("close")).toHaveLength(3);
  });

  it("moves focus into the panel on open and restores it on close", async () => {
    const trigger = document.createElement("button");
    trigger.id = "trigger";
    document.body.appendChild(trigger);
    trigger.focus();
    wrapper = mountDrawer({ open: false });
    await wrapper.setProps({ open: true });
    await nextTick();
    await nextTick();
    expect(document.activeElement?.id).toBe("first");
    await wrapper.setProps({ open: false });
    await nextTick();
    expect(document.activeElement?.id).toBe("trigger");
  });

  it("has the body as its only scroller and a safe-area footer", async () => {
    wrapper = mountDrawer({}, { footer: "Saved automatically" });
    await nextTick();
    const scrollers = [...document.querySelectorAll('[data-ui="drawer"] *')].filter((el) =>
      [...el.classList].some((c) => c.startsWith("overflow-y-")),
    );
    expect(scrollers).toHaveLength(1);
    expect(scrollers[0]!.getAttribute("data-part")).toBe("body");
    expect(document.querySelector('[data-part="footer"]')!.className).toContain("pb-safe-b");
  });
});

describe("UiDrawer attrs", () => {
  it("forwards data-* and aria-* to the drawer element and class to the panel", async () => {
    wrapper = mount(UiDrawer, {
      attachTo: document.body,
      props: { open: true },
      attrs: { "data-testid": "shell.settings", class: "max-w-none" },
      slots: { header: "H", default: "x" },
    });
    await nextTick();
    expect(document.querySelector('[data-ui="drawer"]')!.getAttribute("data-testid")).toBe("shell.settings");
    expect(document.querySelector('[role="dialog"]')!.className).toContain("max-w-none");
  });
});
