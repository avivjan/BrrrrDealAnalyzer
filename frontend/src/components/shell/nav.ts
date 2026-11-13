/**
 * The primary navigation, as data: one entry per route the router declares.
 *
 * The router itself is frozen (`src/router/index.ts`), so this file mirrors
 * its eight routes for the sidebar, the bottom nav and the command palette, and
 * `shell/nav.test.ts` holds the two in step. `name` doubles as the hook suffix
 * (`shell.nav.<name>`) and as the title the topbar shows for the route.
 */
export interface NavItemData {
  /** Matches the router's route name. */
  name: "home" | "analyze" | "my-deals" | "bought-deals" | "liquidity" | "construction-accounts" | "reps" | "inspections";
  label: string;
  to: string;
  /** A primeicons class. */
  icon: string;
  /** The topbar title while this route is active. */
  title: string;
  /** The phone's bottom bar holds seven tabs; the others are in the sidebar, the palette and the go-to keys. */
  shownInThePhoneBottomBar: boolean;
  /** The key after `g` that opens it from anywhere (outside a text field). */
  goToKey: string;
}

export const NAV_ITEMS: readonly NavItemData[] = [
  { name: "home", label: "Dashboard", to: "/", icon: "pi pi-th-large", title: "Dashboard", shownInThePhoneBottomBar: true, goToKey: "d" },
  { name: "analyze", label: "Analyze", to: "/analyze", icon: "pi pi-calculator", title: "Analyze a deal", shownInThePhoneBottomBar: true, goToKey: "a" },
  { name: "my-deals", label: "My Deals", to: "/my-deals", icon: "pi pi-objects-column", title: "My Deals", shownInThePhoneBottomBar: true, goToKey: "m" },
  { name: "bought-deals", label: "Bought", to: "/bought-deals", icon: "pi pi-check-circle", title: "Bought Deals", shownInThePhoneBottomBar: true, goToKey: "b" },
  { name: "liquidity", label: "Liquidity", to: "/liquidity", icon: "pi pi-chart-line", title: "Liquidity", shownInThePhoneBottomBar: true, goToKey: "l" },
  {
    name: "construction-accounts", label: "Construction", to: "/liquidity/construction-accounts", icon: "pi pi-building-columns",
    title: "Construction accounts", shownInThePhoneBottomBar: false, goToKey: "c",
  },
  { name: "reps", label: "REPS", to: "/reps", icon: "pi pi-clock", title: "REPS Tracker", shownInThePhoneBottomBar: true, goToKey: "r" },
  { name: "inspections", label: "Inspect", to: "/inspections", icon: "pi pi-check-square", title: "Inspections", shownInThePhoneBottomBar: true, goToKey: "i" },
];

export function navItemForPath(path: string): NavItemData | undefined {
  return NAV_ITEMS.find((item) => item.to === path);
}

/** The seven tabs of the phone's bottom bar. */
export const PHONE_BOTTOM_BAR_ITEMS: readonly NavItemData[] = NAV_ITEMS.filter((item) => item.shownInThePhoneBottomBar);
