import { describe, expect, it, vi } from "vitest";

import { LOOKS } from "../../design/looks";
import { constructionAccountOfDeal, dealOnItsBoard, dealOnTheLiquidityTimeline } from "../../navigation/appLinks";
import { buildCommands, buildDealCommands, filterCommands } from "./commands";
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
    expect(filterCommands(commands, "LIQUID").map((c) => c.id)).toEqual(["go-liquidity", "go-construction-accounts", "liquidity-settings"]);
    expect(filterCommands(commands, "aurora").map((c) => c.id)).toEqual(["look-aurora"]);
    expect(filterCommands(commands, "appearance").length).toBeGreaterThan(4);
    expect(filterCommands(commands, "zzz")).toEqual([]);
  });
});

describe("the deal commands", () => {
  const deals = [
    { id: "bought-1", board: "bought" as const, deal_type: "BRRRR" as const, address: "12 Oak St" },
    { id: "active-1", board: "active" as const, deal_type: "BRRRR" as const, address: "40 Elm Ave" },
    { id: "flip-1", board: "bought" as const, deal_type: "FLIP" as const, address: "7 Pine Rd" },
  ];

  it("offers Open for each deal, the timeline only when imported, and the construction account for a Bought BRRRR", () => {
    const commands = buildDealCommands(deals, { push: vi.fn() }, (board, dealId) => board === "bought" && dealId === "bought-1");
    expect(commands.map((c) => c.id)).toEqual([
      "deal-bought-1", "deal-bought-1-timeline", "deal-bought-1-construction-account", "deal-active-1", "deal-flip-1",
    ]);
    expect(commands.every((c) => c.group === "Deals")).toBe(true);
  });

  it("each command goes where the page reads it", () => {
    const router = { push: vi.fn() };
    const commands = buildDealCommands(deals, router, () => true);
    commands.find((c) => c.id === "deal-bought-1-construction-account")!.run();
    commands.find((c) => c.id === "deal-active-1-timeline")!.run();
    commands.find((c) => c.id === "deal-flip-1")!.run();
    expect(router.push).toHaveBeenNthCalledWith(1, constructionAccountOfDeal("bought-1"));
    expect(router.push).toHaveBeenNthCalledWith(2, dealOnTheLiquidityTimeline("my_deals", "active-1"));
    expect(router.push).toHaveBeenNthCalledWith(3, dealOnItsBoard("bought", "flip-1", "FLIP"));
  });

  it("finds a deal by its address and by 'construction'", () => {
    const commands = buildDealCommands(deals, { push: vi.fn() }, () => false);
    expect(filterCommands(commands, "oak").map((c) => c.id)).toEqual(["deal-bought-1", "deal-bought-1-construction-account"]);
    expect(filterCommands(commands, "construction").map((c) => c.id)).toEqual(["deal-bought-1-construction-account"]);
  });
});
