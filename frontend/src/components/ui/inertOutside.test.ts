// @vitest-environment jsdom
import { afterEach, describe, expect, it } from "vitest";

import { inertOutside } from "./inertOutside";

afterEach(() => {
  document.body.innerHTML = "";
});

describe("inertOutside", () => {
  it("makes every other body child inert and releases exactly those", () => {
    document.body.innerHTML = '<div id="app"></div><div id="overlay"></div><div id="other" inert></div><div id="stacked" data-overlay></div>';
    const release = inertOutside(document.getElementById("overlay")!);
    expect(document.getElementById("app")!.hasAttribute("inert")).toBe(true);
    expect(document.getElementById("overlay")!.hasAttribute("inert")).toBe(false);
    expect(document.getElementById("stacked")!.hasAttribute("inert")).toBe(false);
    release();
    expect(document.getElementById("app")!.hasAttribute("inert")).toBe(false);
    // Pre-existing inert is not ours to remove.
    expect(document.getElementById("other")!.hasAttribute("inert")).toBe(true);
  });

  it("skips ancestors of the overlay", () => {
    document.body.innerHTML = '<div id="wrap"><div id="overlay"></div></div><div id="app"></div>';
    const release = inertOutside(document.getElementById("overlay")!);
    expect(document.getElementById("wrap")!.hasAttribute("inert")).toBe(false);
    expect(document.getElementById("app")!.hasAttribute("inert")).toBe(true);
    release();
  });
});
