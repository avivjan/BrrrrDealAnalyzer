import plugin from 'tailwindcss/plugin'

/**
 * Semantic theme. Every colour is a `--color-*` triplet from
 * `src/assets/tokens.css`, wrapped so Tailwind can still apply its own alpha
 * modifier (`bg-surface/70`). Nothing here removes a default: the templates
 * still use `gray-*`/`slate-*`/`blue-*` until Phase 3 migrates them.
 */
const token = (name) => `rgb(var(--color-${name}) / <alpha-value>)`

/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class', // Enable dark mode by class
  content: [
    "./index.html",
    "./src/**/*.{vue,js,ts,jsx,tsx}",
    // Class names written inside a test are assertions, not markup: without
    // this a `expect(cn(...)).toBe('rotate-[13deg]')` ships a live rule. The
    // `scripts/audit/*.test.mjs` suites need no row — they are outside `src/`.
    "!./src/**/*.test.ts",
  ],
  theme: {
    extend: {
      colors: {
        page: token('page'),
        surface: token('surface'),
        'surface-muted': token('surface-muted'),
        line: token('line'),
        fg: token('fg'),
        'fg-muted': token('fg-muted'),
        primary: token('primary'),
        'primary-hover': token('primary-hover'),
        'primary-fg': token('primary-fg'),
        positive: token('positive'),
        negative: token('negative'),
        warning: token('warning'),
        ring: token('ring'),
        'chart-1': token('chart-1'),
        'chart-2': token('chart-2'),
        'chart-3': token('chart-3'),
        'chart-4': token('chart-4'),
        'chart-5': token('chart-5'),
        'chart-6': token('chart-6'),
      },
      borderRadius: {
        // Deliberately not `sm`/`md`/`lg`: those are Tailwind defaults the
        // templates already use in ~150 places, and overriding them would
        // restyle every existing corner. `rounded-ctl` / `rounded-card` /
        // `rounded-panel` reach the tokens without touching them.
        ctl: 'var(--radius-sm)',
        card: 'var(--radius-md)',
        panel: 'var(--radius-lg)',
      },
      boxShadow: {
        1: 'var(--shadow-1)',
        2: 'var(--shadow-2)',
        3: 'var(--shadow-3)',
      },
      fontFamily: {
        // `Inter Variable` is the self-hosted @fontsource face (Task 1.3);
        // until it is installed the system stack renders, as today.
        sans: ['Inter Variable', 'Inter', 'system-ui', 'sans-serif'],
      },
      spacing: {
        'safe-t': 'env(safe-area-inset-top)',
        'safe-b': 'env(safe-area-inset-bottom)',
        'safe-l': 'env(safe-area-inset-left)',
        'safe-r': 'env(safe-area-inset-right)',
      },
      transitionDuration: {
        fast: 'var(--dur-fast)',
        base: 'var(--dur-base)',
        slow: 'var(--dur-slow)',
      },
      transitionTimingFunction: {
        standard: 'var(--ease-standard)',
        emphasized: 'var(--ease-emphasized)',
        exit: 'var(--ease-exit)',
      },
      keyframes: {
        // Mirrors the scoped keyframes in PortfolioStatsBar / LandingPage, so
        // Phase 3 can delete those `<style>` blocks without a visual change.
        shimmer: {
          '0%, 100%': { transform: 'translateX(-100%)' },
          '50%': { transform: 'translateX(100%)' },
        },
        float: {
          '0%, 100%': { transform: 'translate(0, 0) scale(1)' },
          '33%': { transform: 'translate(20px, -30px) scale(1.05)' },
          '66%': { transform: 'translate(-25px, 25px) scale(0.97)' },
        },
      },
      animation: {
        shimmer: 'shimmer 8s ease-in-out infinite',
        float: 'float 18s ease-in-out infinite',
      },
    },
  },
  // `future.hoverOnlyWhenSupported` is deliberately NOT enabled yet. It wraps
  // every `hover:` utility in `@media (hover: hover)`, which would hide the 14
  // controls this app reveals only on hover from every touch device (DealCard
  // x4, BoughtDealCard x2, MyDeals x3, BoughtDeals x3, DayDetail x1,
  // LiquiditySidebar x1). It is enabled at the end of Phase 3, once every
  // `group-hover:opacity-100` reveal has a `touch:opacity-100` counterpart.
  plugins: [
    plugin(({ addVariant }) => {
      // `touch:` — the complement of `hover:`, and the counterpart each of
      // those 14 reveals needs before the flag can be turned on.
      addVariant('touch', '@media (hover: none)')
    }),
  ],
}
