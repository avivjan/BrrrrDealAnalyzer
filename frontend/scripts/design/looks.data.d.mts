/** Types for `looks.data.mjs`, so `src/design/looks.test.ts` can import it under strict TS. */
export interface LookPalette {
  page: string; surface: string; surfaceMuted: string; surface2: string; surface3: string;
  line: string; fg: string; fgMuted: string;
  primary: string; primaryHover: string; primaryFg: string; accent: string; accent2: string;
  positive: string; negative: string; warning: string; ring: string;
  glass: string; glassLine: string;
  chart: string[];
}
export interface LookShape {
  radius: [string, string, string];
  borderW: string;
  blur: string;
  trackDisplay: string;
  fontDisplay: string;
  fontMono: string;
  dur: [string, string, string];
  ease: { standard: string; emphasized: string; exit: string };
  gsap: { standard: string; emphasized: string; exit: string };
  shadows: 'flat' | 'soft' | 'soft-deep' | 'hard';
  glow: boolean;
  ambient: string;
}
export interface LookData {
  id: string;
  name: string;
  tagline: string;
  shape: LookShape;
  light: LookPalette;
  dark: LookPalette;
}
export const LOOKS: LookData[];
export const DEFAULT_LOOK: string;
