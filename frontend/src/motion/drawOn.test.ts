// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const state = { motionOn: false };
vi.mock("./gsap", async (importOriginal) => {
  const actual = await importOriginal<typeof import("./gsap")>();
  return { ...actual, motionEnabled: () => state.motionOn };
});

import { gsap } from "./gsap";
import { vDrawOn } from "./directives";

function path(length: number | null): SVGPathElement {
  const el = document.createElementNS("http://www.w3.org/2000/svg", "path") as SVGPathElement;
  if (length !== null) {
    (el as unknown as { getTotalLength: () => number }).getTotalLength = () => length;
  }
  return el;
}

beforeEach(() => {
  state.motionOn = false;
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("v-draw-on", () => {
  it("does nothing with motion off, and nothing without a measurable path", () => {
    const to = vi.spyOn(gsap, "to");
    vDrawOn.mounted!(path(120), {} as never, {} as never, null as never);
    state.motionOn = true;
    vDrawOn.mounted!(path(null), {} as never, {} as never, null as never);
    expect(to).not.toHaveBeenCalled();
  });

  it("dashes the path to its length and tweens the offset to zero over DUR.slow", () => {
    state.motionOn = true;
    const to = vi.spyOn(gsap, "to").mockImplementation(() => ({ kill: vi.fn() }) as never);
    const el = path(120);
    vDrawOn.mounted!(el, {} as never, {} as never, null as never);
    expect(el.getAttribute("stroke-dasharray")).toBe("120");
    expect(el.getAttribute("stroke-dashoffset")).toBe("120");
    const vars = to.mock.calls[0]![1] as { attr: Record<string, number>; duration: number; onComplete: () => void };
    expect(vars.attr["stroke-dashoffset"]).toBe(0);
    expect(vars.duration).toBeGreaterThan(0);
    vars.onComplete();
    expect(el.getAttribute("stroke-dasharray")).toBeNull();
    expect(el.getAttribute("stroke-dashoffset")).toBeNull();
  });

  it("kills the tween and clears the attributes on unmount", () => {
    state.motionOn = true;
    const kill = vi.fn();
    vi.spyOn(gsap, "to").mockImplementation(() => ({ kill }) as never);
    const el = path(80);
    vDrawOn.mounted!(el, {} as never, {} as never, null as never);
    vDrawOn.unmounted!(el, {} as never, {} as never, null as never);
    expect(kill).toHaveBeenCalledTimes(1);
    expect(el.getAttribute("stroke-dasharray")).toBeNull();
  });
});
