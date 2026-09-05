/**
 * What the command palette can do. Client-side only: navigation and
 * appearance. No command fetches, writes data or opens a flow that would
 * change the network contract — those stay on the pages that own them.
 */
import type { Router } from "vue-router";

import { LOOKS, type LookId } from "../../design/looks";
import { NAV_ITEMS } from "./nav";

export interface Command {
  id: string;
  label: string;
  group: "Navigate" | "Appearance" | "Settings";
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
    hint: item.to,
    keywords: item.label,
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
  ];

  return [...navigate, ...looks, ...modes, ...settings];
}

/** Case-insensitive substring match on label, keywords and group; empty query keeps everything. */
export function filterCommands(commands: Command[], query: string): Command[] {
  const needle = query.trim().toLowerCase();
  if (!needle) return commands;
  return commands.filter((command) =>
    `${command.label} ${command.keywords ?? ""} ${command.group}`.toLowerCase().includes(needle),
  );
}
