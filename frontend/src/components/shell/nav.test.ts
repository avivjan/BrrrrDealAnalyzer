import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

import { NAV_ITEMS, navItemForPath } from "./nav";

/** The frozen router, read as text: its `path`/`name` pairs are the truth this file mirrors. */
const routerSource = readFileSync(new URL("../../router/index.ts", import.meta.url), "utf8");
const routes = [...routerSource.matchAll(/path:\s*['"]([^'"]+)['"],\s*name:\s*['"]([^'"]+)['"]/g)].map((m) => ({ path: m[1]!, name: m[2]! }));

describe("the primary navigation", () => {
  it("mirrors every route the frozen router declares, by path and name", () => {
    expect(routes.length).toBe(6);
    expect(NAV_ITEMS.map((item) => ({ path: item.to, name: item.name }))).toEqual(routes);
  });

  it("finds an item by path and nothing for an unknown path", () => {
    expect(navItemForPath("/liquidity")?.title).toBe("Liquidity");
    expect(navItemForPath("/nope")).toBeUndefined();
  });

  it("gives every item an icon and distinct labels", () => {
    for (const item of NAV_ITEMS) expect(item.icon).toMatch(/^pi pi-/);
    expect(new Set(NAV_ITEMS.map((item) => item.label)).size).toBe(NAV_ITEMS.length);
  });
});
