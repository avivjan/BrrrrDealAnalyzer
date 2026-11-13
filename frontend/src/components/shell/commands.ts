/**
 * What the command palette can do. Client-side only: navigation and
 * appearance. No command fetches, writes data or opens a flow that would
 * change the network contract — those stay on the pages that own them.
 * The deal commands are built from a list the palette reads once when it
 * first opens (tasks/todo/ConstructionAccountPerRehab.md, Step C0).
 */
import type { Router, RouteLocationRaw } from "vue-router";

import { LOOKS, type LookId } from "../../design/looks";
import {
  constructionAccountOfDeal, constructionAccountSettings, dealOnItsBoard, dealOnTheLiquidityTimeline, liquiditySettings,
} from "../../navigation/appLinks";
import { NAV_ITEMS } from "./nav";

export interface Command {
  id: string;
  label: string;
  group: "Navigate" | "Deals" | "Appearance" | "Settings";
  /** A primeicons class. */
  icon: string;
  /** Shown on the right; a keyboard hint or a category. */
  hint?: string;
  /** Extra words the filter also matches. */
  keywords?: string;
  run: () => void;
}

export interface CommandDeps {
  router: Pick<Router, "push">;
  setTheme: (choice: "light" | "dark" | "system") => void;
  setLook: (id: LookId) => void;
  toggleTheme: () => void;
  openSettings: () => void;
}

export function buildCommands(deps: CommandDeps): Command[] {
  const navigate: Command[] = NAV_ITEMS.map((item) => ({
    id: `go-${item.name}`,
    label: item.title,
    group: "Navigate",
    icon: item.icon,
    hint: `g ${item.goToKey}`,
    keywords: `${item.label} ${item.to}`,
    run: () => void deps.router.push(item.to),
  }));

  const looks: Command[] = LOOKS.map((look) => ({
    id: `look-${look.id}`,
    label: `Look: ${look.name}`,
    group: "Appearance",
    icon: "pi pi-palette",
    keywords: look.tagline,
    run: () => deps.setLook(look.id),
  }));

  const modes: Command[] = [
    { id: "theme-toggle", label: "Toggle light / dark", group: "Appearance", icon: "pi pi-sun", keywords: "theme mode", run: deps.toggleTheme },
    { id: "theme-light", label: "Mode: Light", group: "Appearance", icon: "pi pi-sun", keywords: "theme", run: () => deps.setTheme("light") },
    { id: "theme-dark", label: "Mode: Dark", group: "Appearance", icon: "pi pi-moon", keywords: "theme", run: () => deps.setTheme("dark") },
    { id: "theme-system", label: "Mode: System", group: "Appearance", icon: "pi pi-desktop", keywords: "theme auto", run: () => deps.setTheme("system") },
  ];

  const settings: Command[] = [
    { id: "settings", label: "Open appearance settings", group: "Settings", icon: "pi pi-sliders-h", keywords: "preferences look mode motion", run: deps.openSettings },
    { id: "liquidity-settings", label: "Liquidity settings", group: "Settings", icon: "pi pi-cog", keywords: "opening balance reserve mercury accounts cash",
      run: () => void deps.router.push(liquiditySettings()) },
    { id: "construction-account-settings", label: "Construction account settings", group: "Settings", icon: "pi pi-building-columns",
      keywords: "mercury tokens refresh polling transfers limits instant updates webhook", run: () => void deps.router.push(constructionAccountSettings()) },
  ];

  return [...navigate, ...looks, ...modes, ...settings];
}

/** One deal as the palette knows it: from the compact `GET /deals` list. */
export interface PaletteDeal {
  id: string;
  board: "active" | "bought";
  deal_type: "BRRRR" | "FLIP";
  address: string;
}

/**
 * Per deal: open it on its board; for a BRRRR deal in the liquidity timeline, its rows there; for a Bought BRRRR
 * deal, its construction account. `isInTheLiquidityTimeline` answers for a deal's board and id.
 */
export function buildDealCommands(deals: PaletteDeal[], router: Pick<Router, "push">,
  isInTheLiquidityTimeline: (board: "my_deals" | "bought", dealId: string) => boolean): Command[] {
  const commands: Command[] = [];
  const go = (to: RouteLocationRaw) => () => void router.push(to);
  for (const deal of deals) {
    const board = deal.board === "bought" ? "bought" : "my_deals";
    const where = board === "bought" ? "Bought" : "My Deals";
    commands.push({ id: `deal-${deal.id}`, label: `Open ${deal.address}`, group: "Deals", icon: "pi pi-home", hint: `${where} · ${deal.deal_type}`,
      keywords: "deal open", run: go(dealOnItsBoard(board, deal.id, deal.deal_type)) });
    if (deal.deal_type === "BRRRR" && isInTheLiquidityTimeline(board, deal.id)) {
      commands.push({ id: `deal-${deal.id}-timeline`, label: `${deal.address} on the timeline`, group: "Deals", icon: "pi pi-chart-line",
        hint: "Liquidity", keywords: "liquidity timeline rows", run: go(dealOnTheLiquidityTimeline(board, deal.id)) });
    }
    if (deal.deal_type === "BRRRR" && board === "bought") {
      commands.push({ id: `deal-${deal.id}-construction-account`, label: `${deal.address} construction account`, group: "Deals",
        icon: "pi pi-building-columns", hint: "Construction", keywords: "construction account mercury rehab draws steal deposit",
        run: go(constructionAccountOfDeal(deal.id)) });
    }
  }
  return commands;
}

/** Case-insensitive substring match on label, keywords and group; empty query keeps everything. */
export function filterCommands(commands: Command[], query: string): Command[] {
  const needle = query.trim().toLowerCase();
  if (!needle) return commands;
  return commands.filter((command) =>
    `${command.label} ${command.keywords ?? ""} ${command.group}`.toLowerCase().includes(needle),
  );
}
