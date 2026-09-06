import { describe, expect, it, vi } from "vitest";

import { LOOKS } from "../../design/looks";
import { buildCommands, filterCommands } from "./commands";
import { NAV_ITEMS } from "./nav";

function deps() {
  return {
    router: { push: vi.fn() },
    setTheme: vi.fn(),
    setLook: vi.fn(),
    toggleTheme: vi.fn(),
    openSettings: vi.fn(),
  };
}

describe("the command list", () => {
  it("offers every route, every look, the modes and settings, with unique ids", () => {
    const commands = buildCommands(deps());
    expect(commands.filter((c) => c.group === "Navigate")).toHaveLength(NAV_ITEMS.length);
    expect(commands.filter((c) => c.id.startsWith("look-"))).toHaveLength(LOOKS.length);
    expect(commands.map((c) => c.id)).toEqual(expect.arrayContaining(["theme-toggle", "theme-light", "theme-dark", "theme-system", "settings"]));
    expect(new Set(commands.map((c) => c.id)).size).toBe(commands.length);
  });

  it("runs each kind of command through the right dependency", () => {
    const d = deps();
    const commands = buildCommands(d);
    commands.find((c) => c.id === "go-liquidity")!.run();
    commands.find((c) => c.id === "look-brutal")!.run();
    commands.find((c) => c.id === "theme-system")!.run();
    commands.find((c) => c.id === "theme-toggle")!.run();
    commands.find((c) => c.id === "settings")!.run();
    expect(d.router.push).toHaveBeenCalledWith("/liquidity");
    expect(d.setLook).toHaveBeenCalledWith("brutal");
    expect(d.setTheme).toHaveBeenCalledWith("system");
    expect(d.toggleTheme).toHaveBeenCalledTimes(1);
    expect(d.openSettings).toHaveBeenCalledTimes(1);
  });

  it("filters by substring on label, keywords and group, case-insensitively", () => {
    const commands = buildCommands(deps());
    expect(filterCommands(commands, "").length).toBe(commands.length);
    expect(filterCommands(commands, "LIQUID").map((c) => c.id)).toEqual(["go-liquidity"]);
    expect(filterCommands(commands, "aurora").map((c) => c.id)).toEqual(["look-aurora"]);
    expect(filterCommands(commands, "appearance").length).toBeGreaterThan(4);
    expect(filterCommands(commands, "zzz")).toEqual([]);
  });
});
