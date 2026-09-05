/**
 * The primary navigation, as data: one entry per route the router declares.
 *
 * The router itself is frozen (`src/router/index.ts`), so this file mirrors
 * its six routes for the sidebar, the bottom nav and the command palette, and
 * `shell/nav.test.ts` holds the two in step. `name` doubles as the hook suffix
 * (`shell.nav.<name>`) and as the title the topbar shows for the route.
 */
export interface NavItemData {
  /** Matches the router's route name. */
  name: "home" | "analyze" | "my-deals" | "bought-deals" | "liquidity" | "reps";
  label: string;
  to: string;
  /** A primeicons class. */
  icon: string;
  /** The topbar title while this route is active. */
  title: string;
}

export const NAV_ITEMS: readonly NavItemData[] = [
  { name: "home", label: "Dashboard", to: "/", icon: "pi pi-th-large", title: "Dashboard" },
  { name: "analyze", label: "Analyze", to: "/analyze", icon: "pi pi-calculator", title: "Analyze a deal" },
  { name: "my-deals", label: "My Deals", to: "/my-deals", icon: "pi pi-objects-column", title: "My Deals" },
  { name: "bought-deals", label: "Bought", to: "/bought-deals", icon: "pi pi-check-circle", title: "Bought Deals" },
  { name: "liquidity", label: "Liquidity", to: "/liquidity", icon: "pi pi-chart-line", title: "Liquidity" },
  { name: "reps", label: "REPS", to: "/reps", icon: "pi pi-clock", title: "REPS Tracker" },
];

export function navItemForPath(path: string): NavItemData | undefined {
  return NAV_ITEMS.find((item) => item.to === path);
}
