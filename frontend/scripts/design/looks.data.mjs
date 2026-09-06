/**
 * The four looks, as data. `build-looks.mjs` turns each entry into
 * `src/assets/looks/<id>.css`; `src/design/looks.ts` mirrors the ids, names
 * and taglines for the Settings drawer.
 *
 * Every colour is a hex string here and becomes an `R G B` triplet in the
 * sheet, so Tailwind can add alpha. The 32 `--chart-*` literals are *derived*
 * from each palette by `chartLiterals()` in the builder — the same mapping the
 * v1 light palette used — so a look never has to hand-tune the chart and the
 * light and dark charts always differ.
 *
 * Tempo budget: every entrance — a modal's open, a route fade, a staggered
 * reveal from first to last child — must finish within 500 ms in every look,
 * because the frozen e2e motion guard (`e2e/fixtures/motion.ts`) measures an
 * overlay at +500 ms and then requires that no GSAP tween is still alive. So
 * `--dur-slow` stays at or below 440 ms; a look's "slowness" is its eases and
 * the ratio between fast/base/slow, not a longer wall-clock.
 *
 * Values come from the board the user reviewed on 2026-09-05
 * (https://claude.ai/code/artifact/4554ee25-5912-42b8-9694-19957ac0ae9c),
 * adjusted only where `npm run audit:contrast` demanded a step within the
 * same family. The rules for what a colour may be used for are in
 * `design-system/brrrr-deal-analyzer/MASTER.md` ("Looks").
 */

/** Ordered as the Settings drawer lists them. */
export const LOOKS = [
  {
    id: 'obsidian',
    name: 'Obsidian Terminal',
    tagline: 'Near-black, one cyan accent, mono numerals. Dense and fast.',
    shape: {
      radius: ['4px', '6px', '8px'],
      borderW: '1px',
      blur: '0px',
      trackDisplay: '-0.01em',
      fontDisplay: "'JetBrains Mono Variable', ui-monospace, SFMono-Regular, Menlo, monospace",
      fontMono: "'JetBrains Mono Variable', ui-monospace, SFMono-Regular, Menlo, monospace",
      dur: ['120ms', '180ms', '280ms'],
      ease: {
        standard: 'cubic-bezier(0.3, 0, 0.2, 1)',
        emphasized: 'cubic-bezier(0.4, 0, 0.2, 1)',
        exit: 'cubic-bezier(0.4, 0, 1, 1)',
      },
      gsap: { standard: 'power2.out', emphasized: 'power2.inOut', exit: 'power1.in' },
      shadows: 'flat',
      glow: false,
      ambient: 'none',
    },
    light: {
      page: '#f4f6f8', surface: '#ffffff', surfaceMuted: '#eef1f5', surface2: '#eef1f5', surface3: '#e3e8ee',
      line: '#d3d9e1', fg: '#0b0d10', fgMuted: '#434b57',
      primary: '#0e7490', primaryHover: '#155e75', primaryFg: '#ffffff', accent: '#0e7490', accent2: '#6d28d9',
      positive: '#047857', negative: '#b91c1c', warning: '#92400e', ring: '#0e7490',
      glass: '#ffffff', glassLine: '#0b0d10',
      chart: ['#0e7490', '#047857', '#b45309', '#1d4ed8', '#be185d', '#6d28d9', '#c2410c', '#0f766e'],
    },
    dark: {
      page: '#0b0d10', surface: '#12151a', surfaceMuted: '#171b21', surface2: '#171b21', surface3: '#1d222a',
      line: '#222831', fg: '#e6e9ef', fgMuted: '#bac2cd',
      primary: '#22d3ee', primaryHover: '#67e8f9', primaryFg: '#06181c', accent: '#22d3ee', accent2: '#a78bfa',
      positive: '#34d399', negative: '#f87171', warning: '#fbbf24', ring: '#22d3ee',
      glass: '#12151a', glassLine: '#e6e9ef',
      chart: ['#22d3ee', '#34d399', '#fbbf24', '#60a5fa', '#f472b6', '#a78bfa', '#fb923c', '#2dd4bf'],
    },
  },
  {
    id: 'aurora',
    name: 'Aurora Glass',
    tagline: 'Deep indigo gradients, frosted glass, violet and cyan. Springy.',
    shape: {
      radius: ['12px', '16px', '20px'],
      borderW: '1px',
      blur: '14px',
      trackDisplay: '-0.02em',
      fontDisplay: "'Space Grotesk Variable', 'Inter Variable', Inter, system-ui, sans-serif",
      fontMono: "'JetBrains Mono Variable', ui-monospace, SFMono-Regular, Menlo, monospace",
      dur: ['180ms', '300ms', '420ms'],
      ease: {
        standard: 'cubic-bezier(0.22, 1, 0.36, 1)',
        emphasized: 'cubic-bezier(0.34, 1.56, 0.64, 1)',
        exit: 'cubic-bezier(0.55, 0.085, 0.68, 0.53)',
      },
      gsap: { standard: 'power3.out', emphasized: 'back.out(1.4)', exit: 'power1.in' },
      shadows: 'soft-deep',
      glow: true,
      ambient: 'gradient-drift',
    },
    light: {
      page: '#f3f4ff', surface: '#ffffff', surfaceMuted: '#eef0fc', surface2: '#eef0fc', surface3: '#e2e6fa',
      line: '#d6daf3', fg: '#14163a', fgMuted: '#474c74',
      primary: '#5b4ee6', primaryHover: '#4a3fd0', primaryFg: '#ffffff', accent: '#4a3fd0', accent2: '#0e7490',
      positive: '#047857', negative: '#be123c', warning: '#92400e', ring: '#5b4ee6',
      glass: '#ffffff', glassLine: '#14163a',
      chart: ['#5b4ee6', '#0e7490', '#be185d', '#047857', '#92400e', '#1d4ed8', '#c2410c', '#7e22ce'],
    },
    dark: {
      page: '#070b1a', surface: '#111a3a', surfaceMuted: '#172246', surface2: '#172246', surface3: '#1e2c56',
      line: '#2a3566', fg: '#eef0ff', fgMuted: '#c5c9e2',
      primary: '#8b7cff', primaryHover: '#a99dff', primaryFg: '#0c0a24', accent: '#a99dff', accent2: '#22d3ee',
      positive: '#3ddc97', negative: '#ff7f9c', warning: '#ffc857', ring: '#8b7cff',
      glass: '#111a3a', glassLine: '#eef0ff',
      chart: ['#8b7cff', '#22d3ee', '#f472b6', '#3ddc97', '#ffc857', '#60a5fa', '#fb923c', '#c084fc'],
    },
  },
  {
    id: 'brutal',
    name: 'Neo-Brutal Fintech',
    tagline: 'Flat blocks, thick borders, hard shadows, lime on black. Loud.',
    shape: {
      radius: ['2px', '2px', '2px'],
      borderW: '2px',
      blur: '0px',
      trackDisplay: '-0.03em',
      fontDisplay: "Unbounded, 'Inter Variable', Inter, system-ui, sans-serif",
      fontMono: "'JetBrains Mono Variable', ui-monospace, SFMono-Regular, Menlo, monospace",
      dur: ['120ms', '200ms', '300ms'],
      ease: {
        standard: 'cubic-bezier(0.2, 0.9, 0.2, 1)',
        emphasized: 'cubic-bezier(0.2, 0.9, 0.2, 1)',
        exit: 'cubic-bezier(0.4, 0, 1, 1)',
      },
      gsap: { standard: 'power4.out', emphasized: 'expo.out', exit: 'power2.in' },
      shadows: 'hard',
      glow: false,
      ambient: 'none',
    },
    light: {
      page: '#f4f1ea', surface: '#ffffff', surfaceMuted: '#ece8de', surface2: '#ece8de', surface3: '#e2ddd0',
      line: '#111111', fg: '#111111', fgMuted: '#4a4842',
      primary: '#111111', primaryHover: '#333333', primaryFg: '#c6ff3d', accent: '#3f6212', accent2: '#c6ff3d',
      positive: '#166534', negative: '#b91c1c', warning: '#92400e', ring: '#111111',
      glass: '#ffffff', glassLine: '#111111',
      chart: ['#3f6212', '#166534', '#92400e', '#1d4ed8', '#b91c1c', '#6d28d9', '#c2410c', '#0f766e'],
    },
    dark: {
      page: '#0f0f0f', surface: '#181818', surfaceMuted: '#222222', surface2: '#222222', surface3: '#2a2a2a',
      line: '#f2efe6', fg: '#f4f1ea', fgMuted: '#c6c2b6',
      primary: '#c6ff3d', primaryHover: '#d9ff70', primaryFg: '#0f0f0f', accent: '#c6ff3d', accent2: '#ff7a7e',
      positive: '#4ade80', negative: '#ff7a7e', warning: '#ffb020', ring: '#c6ff3d',
      glass: '#181818', glassLine: '#f2efe6',
      chart: ['#c6ff3d', '#4ade80', '#ffb020', '#38bdf8', '#ff7a7e', '#c084fc', '#fb923c', '#2dd4bf'],
    },
  },
  {
    id: 'luxury',
    name: 'Quiet Luxury',
    tagline: 'Warm charcoal, champagne gold, serif headlines, room to breathe.',
    shape: {
      radius: ['10px', '12px', '16px'],
      borderW: '1px',
      blur: '0px',
      trackDisplay: '-0.015em',
      fontDisplay: "'Fraunces Variable', Fraunces, Georgia, 'Times New Roman', serif",
      fontMono: "'JetBrains Mono Variable', ui-monospace, SFMono-Regular, Menlo, monospace",
      dur: ['200ms', '340ms', '440ms'],
      ease: {
        standard: 'cubic-bezier(0.25, 0.1, 0.25, 1)',
        emphasized: 'cubic-bezier(0.45, 0, 0.15, 1)',
        exit: 'cubic-bezier(0.55, 0.085, 0.68, 0.53)',
      },
      gsap: { standard: 'power1.out', emphasized: 'power2.inOut', exit: 'power1.in' },
      shadows: 'soft',
      glow: false,
      ambient: 'shimmer',
    },
    light: {
      page: '#f7f4ee', surface: '#ffffff', surfaceMuted: '#f1ede4', surface2: '#f1ede4', surface3: '#e8e2d6',
      line: '#dcd6ca', fg: '#1d1c1a', fgMuted: '#524e46',
      primary: '#7d5f27', primaryHover: '#644b1f', primaryFg: '#ffffff', accent: '#7d5f27', accent2: '#3f5a7a',
      positive: '#2f6f3a', negative: '#a33a3a', warning: '#7f5311', ring: '#7d5f27',
      glass: '#ffffff', glassLine: '#1d1c1a',
      chart: ['#7d5f27', '#2f6f3a', '#7f5311', '#3f5a7a', '#a33a3a', '#6b4fa0', '#a05a2c', '#2f6f6a'],
    },
    dark: {
      page: '#14151a', surface: '#1b1d24', surfaceMuted: '#21242c', surface2: '#21242c', surface3: '#282b34',
      line: '#2f323d', fg: '#ece7dd', fgMuted: '#c9c5bb',
      primary: '#d4b483', primaryHover: '#e2c99c', primaryFg: '#1a1508', accent: '#d4b483', accent2: '#8fa3bf',
      positive: '#8fbf8a', negative: '#e09595', warning: '#e0b96a', ring: '#d4b483',
      glass: '#1b1d24', glassLine: '#ece7dd',
      chart: ['#d4b483', '#8fbf8a', '#e0b96a', '#8fa3bf', '#e09595', '#b39ddb', '#e0a16a', '#7fb6b0'],
    },
  },
];

export const DEFAULT_LOOK = 'luxury';
