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
  // Wraps every `hover:` utility in `@media (hover: hover)`, so a phone no
  // longer fires hover styles on the first tap and then keeps them until the
  // next one. Turned on at the end of Phase 3, after the `G-HOVER` gate
  // (`scripts/audit/hover-pairs.mjs`, run by `npm run verify:ui`) proved that
  // every hover-only reveal in `src/**/*.vue` has a `touch:` counterpart.
  future: { hoverOnlyWhenSupported: true },
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
        'chart-7': token('chart-7'),
        'chart-8': token('chart-8'),
        // v2 vocabulary: elevation tiers, secondary accents, glass
        'surface-2': token('surface-2'),
        'surface-3': token('surface-3'),
        accent: token('accent'),
        'accent-2': token('accent-2'),
        glass: token('glass'),
        'glass-line': token('glass-line'),
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
        4: 'var(--shadow-4)',
        // Glow is a shadow the look may zero out; reserved for the primary
        // CTA, the active nav item and a focused KPI.
        'glow-primary': 'var(--glow-primary)',
        'glow-accent': 'var(--glow-accent)',
        'glow-negative': 'var(--glow-negative)',
      },
      // Focus rings sit on the page colour, not Tailwind's white default — the
      // default mode is dark, so a white offset would read as a halo.
      ringOffsetColor: {
        DEFAULT: 'rgb(var(--color-page) / <alpha-value>)',
      },
      // `border-ui`: the look's border weight (1px hairline, 2px brutalist).
      borderWidth: {
        ui: 'var(--border-w)',
      },
      backdropBlur: {
        glass: 'var(--blur-glass)',
      },
      backgroundImage: {
        brand: 'var(--gradient-brand)',
        surface: 'var(--gradient-surface)',
      },
      fontFamily: {
        // Body copy is always Inter, whatever the look.
        sans: ['Inter Variable', 'Inter', 'system-ui', 'sans-serif'],
        // Headings, KPI numerals and the wordmark take the look's display face;
        // money and percent cells its mono face. Both resolve through tokens
        // so a look can swap them without a component change.
        display: ['var(--font-display)'],
        mono: ['var(--font-mono)'],
      },
      letterSpacing: {
        display: 'var(--track-display)',
      },
      spacing: {
        'safe-t': 'env(safe-area-inset-top)',
        'safe-b': 'env(safe-area-inset-bottom)',
        'safe-l': 'env(safe-area-inset-left)',
        'safe-r': 'env(safe-area-inset-right)',
        sidebar: 'var(--sidebar-w)',
        'sidebar-collapsed': 'var(--sidebar-w-collapsed)',
        topbar: 'var(--topbar-h)',
        'stats-bar': 'var(--stats-bar-h)',
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
  plugins: [
    plugin(({ addVariant }) => {
      // `touch:` — the complement of `hover:`. With `hoverOnlyWhenSupported`
      // on, this is the only way a hover-only style reaches a touch device, so
      // it carries the 10 `group-hover:opacity-100` reveals (DealCard,
      // BoughtDealCard, DayDetail, LiquiditySidebar, MyDeals x3,
      // BoughtDeals x3) and the 44 px `touch:min-h-11` floor on the small
      // buttons that are a primary action. `G-HOVER` fails the build if a new
      // reveal ever lands without its `touch:opacity-100` counterpart.
      addVariant('touch', '@media (hover: none)')
    }),
  ],
}
