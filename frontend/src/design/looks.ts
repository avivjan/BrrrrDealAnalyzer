/**
 * The looks a user can pick in Settings → Appearance.
 *
 * A look is a token sheet (`src/assets/looks/<id>.css`, generated from
 * `scripts/design/looks.data.mjs`) plus the display fonts it needs. This file
 * is the runtime mirror of that data: ids, names, taglines and a lazy font
 * loader per look, so the first paint downloads Inter plus only the active
 * look's faces. `src/design/looks.test.ts` holds the two lists together.
 *
 * Adding a look: one entry in `looks.data.mjs`, `node scripts/design/build-looks.mjs`,
 * one entry here (and its fonts in `package.json`). Nothing else in the app
 * names a look.
 */

export type LookId = "obsidian" | "aurora" | "brutal" | "luxury";

export interface Look {
  id: LookId;
  name: string;
  tagline: string;
  /** Loads the look's display faces. Inter is always loaded by `main.ts`. */
  loadFonts: () => Promise<unknown>;
}

/** The look a browser that has never chosen one gets. */
export const DEFAULT_LOOK: LookId = "luxury";

export const LOOKS: readonly Look[] = [
  {
    id: "obsidian",
    name: "Obsidian Terminal",
    tagline: "Near-black, one cyan accent, mono numerals. Dense and fast.",
    loadFonts: () => import("@fontsource-variable/jetbrains-mono"),
  },
  {
    id: "aurora",
    name: "Aurora Glass",
    tagline: "Deep indigo gradients, frosted glass, violet and cyan. Springy.",
    loadFonts: () =>
      Promise.all([
        import("@fontsource-variable/space-grotesk"),
        import("@fontsource-variable/jetbrains-mono"),
      ]),
  },
  {
    id: "brutal",
    name: "Neo-Brutal Fintech",
    tagline: "Flat blocks, thick borders, hard shadows, lime on black. Loud.",
    loadFonts: () =>
      Promise.all([
        import("@fontsource/unbounded/700.css"),
        import("@fontsource/unbounded/900.css"),
        import("@fontsource-variable/jetbrains-mono"),
      ]),
  },
  {
    id: "luxury",
    name: "Quiet Luxury",
    tagline: "Warm charcoal, champagne gold, serif headlines, room to breathe.",
    loadFonts: () =>
      Promise.all([
        import("@fontsource-variable/fraunces"),
        import("@fontsource-variable/jetbrains-mono"),
      ]),
  },
];

export function isLookId(value: unknown): value is LookId {
  return typeof value === "string" && LOOKS.some((look) => look.id === value);
}
