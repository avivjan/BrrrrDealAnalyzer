<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import SendOfferModal from "../components/SendOfferModal.vue";
import { useDealStore } from "../stores/dealStore";

console.log("View: LandingPage setup");

const isOfferModalOpen = ref(false);
const dealStore = useDealStore();

const hasPortfolioBar = computed(
  () => dealStore.portfolioStats.numDoors > 0
);

onMounted(() => {
  console.log("View: LandingPage mounted");
});

type CardAction = "internal" | "external";

interface FeatureCard {
  title: string;
  subtitle: string;
  icon: string;
  action: CardAction;
  route?: string;
  url?: string;
  gradient: string;
  iconBg: string;
}

const cards: FeatureCard[] = [
  {
    title: "REPS Tracker",
    subtitle: "Log hours",
    icon: "pi pi-clock",
    action: "internal",
    route: "/reps",
    gradient: "from-rose-500 via-pink-500 to-amber-500",
    iconBg: "from-rose-400 to-amber-400",
  },
  {
    title: "Daily Tasks",
    subtitle: "Stay on track",
    icon: "pi pi-check-square",
    action: "external",
    url: "https://docs.google.com/document/d/1xW8KKv-mrJlHxcFwuibhVr685R_CE7BhkJcIECHiI8k/edit?tab=t.0",
    gradient: "from-emerald-500 via-teal-500 to-cyan-500",
    iconBg: "from-emerald-400 to-teal-400",
  },
  {
    title: "Stessa",
    subtitle: "Bookkeeping",
    icon: "pi pi-database",
    action: "external",
    url: "https://app.stessa.com/web3/dashboard",
    gradient: "from-yellow-500 via-orange-500 to-amber-600",
    iconBg: "from-yellow-400 to-orange-400",
  },
  {
    title: "Analyze Deal",
    subtitle: "Run the numbers",
    icon: "pi pi-calculator",
    action: "internal",
    route: "/analyze",
    gradient: "from-blue-500 via-indigo-500 to-violet-600",
    iconBg: "from-blue-400 to-indigo-400",
  },
  {
    title: "My Deals",
    subtitle: "Pipeline",
    icon: "pi pi-trello",
    action: "internal",
    route: "/my-deals",
    gradient: "from-purple-500 via-fuchsia-500 to-pink-600",
    iconBg: "from-purple-400 to-fuchsia-400",
  },
  {
    title: "Bought Deals",
    subtitle: "Portfolio",
    icon: "pi pi-check-circle",
    action: "internal",
    route: "/bought-deals",
    gradient: "from-emerald-500 via-green-500 to-lime-500",
    iconBg: "from-emerald-400 to-green-400",
  },
  {
    title: "Liquidity",
    subtitle: "Cash flow",
    icon: "pi pi-chart-line",
    action: "internal",
    route: "/liquidity",
    gradient: "from-slate-700 via-indigo-700 to-blue-800",
    iconBg: "from-slate-500 to-indigo-500",
  },
];

interface ResourceLink {
  title: string;
  icon: string;
  url: string;
  gradient: string;
}

const resources: ResourceLink[] = [
  {
    title: "Contractors",
    icon: "pi pi-users",
    url: "https://docs.google.com/document/d/1U5ryt5Rrmo70FcAzvxo-i_Ra6nZazI0xsIQ7zSA0yCw/edit?tab=t.0",
    gradient: "from-amber-500 to-orange-600",
  },
  {
    title: "Lenders",
    icon: "pi pi-wallet",
    url: "https://docs.google.com/document/d/1z81cSxV0_R-hPX811XjxPWuiV-tgUrXWq7X6bZ3ZHas/edit?tab=t.0",
    gradient: "from-green-500 to-emerald-600",
  },
  {
    title: "PM",
    icon: "pi pi-building",
    url: "https://docs.google.com/document/d/1qbzRvgt7zIYnZaHUIgxhMXHi7Fi1wZ1uIky-VkIfJXk/edit?tab=t.0",
    gradient: "from-cyan-500 to-blue-600",
  },
  {
    title: "Wholesalers",
    icon: "pi pi-shopping-bag",
    url: "https://docs.google.com/document/d/1-foWzLM6xjeGVVEyLqNk8AdCg-s3j9TC6cZ15GIvFZI/edit?tab=t.0",
    gradient: "from-rose-500 to-pink-600",
  },
];

const logExternal = (card: FeatureCard) => {
  console.log("View: LandingPage - Opening link:", card.title, card.url);
};
</script>

<template>
  <div class="landing-root" :class="{ 'has-bar': hasPortfolioBar }">
    <!-- Ambient background -->
    <div class="bg-decor" aria-hidden="true">
      <div class="blob blob-1"></div>
      <div class="blob blob-2"></div>
      <div class="blob blob-3"></div>
      <div class="grid-overlay"></div>
    </div>

    <!-- Page content -->
    <div class="landing-content">
      <!-- Header: title + send offer -->
      <header class="landing-header">
        <div class="title-block">
          <h1 class="title">
            <span class="title-gradient">Big Whales</span>
            <span class="title-accent">Deal Analyzer</span>
          </h1>
          <p class="subtitle">Your real-estate command center</p>
        </div>

        <UiButton
          data-testid="landing.offer"
          variant="primary"
          size="lg"
          class="offer-btn rounded-full"
          @click="isOfferModalOpen = true"
        >
          <span class="offer-btn-glow"></span>
          <i class="pi pi-send offer-btn-icon"></i>
          <span class="offer-btn-text">Send Market Offer</span>
        </UiButton>
      </header>

      <!-- Main feature grid (7 cards: 4 + 3) -->
      <div class="feature-grid">
        <component
          v-for="(card, idx) in cards"
          :key="card.title"
          :data-testid="`landing.card.${card.title}`"
          :is="card.action === 'internal' ? 'RouterLink' : 'a'"
          :to="card.action === 'internal' ? card.route : undefined"
          :href="card.action === 'external' ? card.url : undefined"
          :target="card.action === 'external' ? '_blank' : undefined"
          :rel="card.action === 'external' ? 'noopener' : undefined"
          class="feature-card"
          :class="[idx < 4 ? 'tile' : 'wide', `idx-${idx}`]"
          @click="card.action === 'external' ? logExternal(card) : null"
        >
          <div :class="['card-gradient', 'bg-gradient-to-br', card.gradient]"></div>
          <div class="card-inner">
            <!-- Decorative ghost icon -->
            <i :class="[card.icon, 'card-ghost-icon']" aria-hidden="true"></i>

            <div class="card-body">
              <div :class="['card-icon-wrap', 'bg-gradient-to-br', card.iconBg]">
                <i :class="[card.icon, 'card-icon']"></i>
              </div>
              <div class="card-text">
                <h2 class="card-title">{{ card.title }}</h2>
                <p class="card-subtitle">{{ card.subtitle }}</p>
              </div>
            </div>

            <i class="pi pi-arrow-up-right card-arrow"></i>
          </div>
        </component>
      </div>

      <!-- Professional resources -->
      <div class="resources">
        <div class="resources-label">
          <i class="pi pi-bookmark text-xs text-warning"></i>
          <span>Professional Resources</span>
        </div>
        <div class="resources-grid">
          <a
            v-for="r in resources"
            :key="r.title"
            :data-testid="`landing.resource.${r.title}`"
            :href="r.url"
            target="_blank"
            rel="noopener"
            class="resource-pill"
          >
            <div :class="['resource-icon', 'bg-gradient-to-br', r.gradient]">
              <i :class="[r.icon]"></i>
            </div>
            <span class="resource-title">{{ r.title }}</span>
            <i class="pi pi-external-link resource-ext"></i>
          </a>
        </div>
      </div>
    </div>

    <SendOfferModal :isOpen="isOfferModalOpen" @close="isOfferModalOpen = false" />
  </div>
</template>

<style scoped>
/* ===== Layout shell =====
 *
 * The height is the App shell's now: its root is a `min-h-dvh` column and the
 * `RouterView` column is `flex-1`, so this fills what is left after the
 * portfolio bar instead of guessing at it. That is what retired the
 * `.has-bar { height: calc(100dvh - 60px) }` hack — the bar is 65 px tall, not
 * 60, so the page used to overflow by five pixels whenever it was shown.
 *
 * `has-bar` still lands on the element as a state hook; nothing styles it.
 */
.landing-root {
  position: relative;
  height: 100%;
  min-height: 560px;
  overflow: hidden;
  background:
    radial-gradient(
      1200px 600px at 10% -10%,
      rgb(var(--color-primary) / 0.16),
      transparent 60%
    ),
    radial-gradient(
      1000px 600px at 110% 10%,
      rgb(var(--color-chart-4) / 0.16),
      transparent 60%
    ),
    linear-gradient(
      180deg,
      rgb(var(--color-primary) / 0) 0%,
      rgb(var(--color-primary) / 0.07) 100%
    ),
    linear-gradient(rgb(var(--color-page)), rgb(var(--color-page)));
  isolation: isolate;
}

/*
 * `max()` on every inline edge, and the bottom inset added to the padding
 * rather than replacing it, so the home indicator never sits on the resource
 * row on a notched phone (`index.html` sets `viewport-fit=cover`).
 */
.landing-content {
  position: relative;
  z-index: 1;
  height: 100%;
  width: 100%;
  max-width: 87.5rem;
  margin: 0 auto;
  padding: var(--space-4) max(var(--space-5), env(safe-area-inset-right))
    calc(var(--space-4) + env(safe-area-inset-bottom))
    max(var(--space-5), env(safe-area-inset-left));
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

/* ===== Background decor ===== */
.bg-decor {
  position: absolute;
  inset: 0;
  pointer-events: none;
  overflow: hidden;
}

/*
 * 60 px is the cap: `blur()` is the most expensive filter on the page and a
 * larger radius costs a bigger offscreen buffer for no visible difference at
 * this scale.
 */
.blob {
  position: absolute;
  border-radius: 9999px;
  filter: blur(60px);
  opacity: 0.5;
  animation: float 18s ease-in-out infinite;
}

.blob-1 {
  top: -120px;
  left: -120px;
  width: 460px;
  height: 460px;
  background: radial-gradient(circle, rgb(var(--color-primary)), transparent 60%);
}
.blob-2 {
  bottom: -160px;
  right: -120px;
  width: 520px;
  height: 520px;
  background: radial-gradient(circle, rgb(var(--color-chart-4)), transparent 60%);
  animation-delay: -6s;
}
.blob-3 {
  top: 40%;
  left: 45%;
  width: 320px;
  height: 320px;
  background: radial-gradient(circle, rgb(var(--color-chart-6)), transparent 60%);
  opacity: 0.25;
  animation-delay: -12s;
}

.grid-overlay {
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(rgb(var(--color-fg) / 0.04) 1px, transparent 1px),
    linear-gradient(90deg, rgb(var(--color-fg) / 0.04) 1px, transparent 1px);
  background-size: 48px 48px;
  /* Unprefixed `mask-image` only lands in Safari 15.4; iOS 15.0 is in scope. */
  -webkit-mask-image: radial-gradient(ellipse at center, black 40%, transparent 80%);
  mask-image: radial-gradient(ellipse at center, black 40%, transparent 80%);
}

@keyframes float {
  0%,
  100% {
    transform: translate(0, 0) scale(1);
  }
  33% {
    transform: translate(20px, -30px) scale(1.05);
  }
  66% {
    transform: translate(-25px, 25px) scale(0.97);
  }
}

/*
 * Three 460-520 px blurred layers animating forever is the page's whole GPU
 * budget. It buys nothing where the decor is mostly off-screen (narrow) or
 * where the device is likely to be battery-bound (coarse pointer), so it is
 * spent only on a wide pointer-driven screen. `prefers-reduced-motion` is
 * handled globally in `main.css`.
 */
@media (hover: none), (max-width: 900px) {
  .blob {
    animation: none;
  }
}

/* ===== Header ===== */
.landing-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
  flex-shrink: 0;
}

.title-block {
  display: flex;
  flex-direction: column;
  gap: 0.125rem;
}

/* 24 -> 32 px: the top two steps of the approved type scale. */
.title {
  display: flex;
  align-items: baseline;
  gap: var(--space-2);
  font-size: clamp(1.5rem, 3vw, 2rem);
  font-weight: 700;
  letter-spacing: -0.02em;
  line-height: 1.1;
  margin: 0;
}

.title-gradient {
  background: linear-gradient(
    135deg,
    rgb(var(--color-primary)) 0%,
    rgb(var(--color-ring)) 55%,
    rgb(var(--color-chart-6)) 100%
  );
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.title-accent {
  color: rgb(var(--color-fg));
  font-weight: 600;
}

/* slate-500 -> `fg-muted` (slate-600): 4.8:1 -> 7.5:1 on this ground. */
.subtitle {
  font-size: 0.875rem;
  font-weight: 500;
  color: rgb(var(--color-fg-muted));
  letter-spacing: 0.01em;
  margin: 0;
}

/*
 * `UiButton variant="primary" size="lg"` owns the fill, the ink, the padding,
 * the focus ring and the pressed scale. Only the pill radius (a class, so
 * `tailwind-merge` drops `rounded-ctl`), the elevation and the sweep are left.
 */
.offer-btn {
  overflow: hidden;
  white-space: nowrap;
  box-shadow: var(--shadow-3);
}

.offer-btn-glow {
  position: absolute;
  inset: 0;
  pointer-events: none;
  background: linear-gradient(
    120deg,
    rgb(var(--color-primary-fg) / 0) 30%,
    rgb(var(--color-primary-fg) / 0.35) 50%,
    rgb(var(--color-primary-fg) / 0) 70%
  );
  transform: translateX(-100%);
  transition: transform var(--dur-slow) var(--ease-standard);
}

.offer-btn-icon {
  font-size: 1em;
}

/* Positioned, and after the glow, so the sweep passes *under* the label. */
.offer-btn-text {
  position: relative;
}

/* ===== Feature grid (7 cards: 4 + 3) ===== */
.feature-grid {
  flex: 1;
  min-height: 0;
  display: grid;
  grid-template-columns: repeat(12, minmax(0, 1fr));
  grid-template-rows: 1fr 1fr;
  gap: var(--space-3);
}

.feature-card {
  position: relative;
  border-radius: var(--radius-lg);
  padding: 2px;
  cursor: pointer;
  text-decoration: none;
  color: inherit;
  overflow: hidden;
  min-height: 0;
  box-shadow: var(--shadow-2);
  transition:
    transform var(--dur-base) var(--ease-standard),
    box-shadow var(--dur-base) var(--ease-standard);
}

.feature-card.tile {
  grid-column: span 3;
}

.feature-card.wide {
  grid-column: span 4;
}

.card-gradient {
  position: absolute;
  inset: 0;
  border-radius: inherit;
  opacity: 1;
  transition: transform var(--dur-slow) var(--ease-standard);
}

/*
 * `isolation: isolate` because this box combines a backdrop filter, a radius
 * and `overflow: hidden` — the combination WebKit is happy to render one frame
 * behind unless the element owns its stacking context outright.
 */
.card-inner {
  position: relative;
  z-index: 1;
  isolation: isolate;
  height: 100%;
  width: 100%;
  background: rgb(var(--color-surface));
  border-radius: calc(var(--radius-lg) - 2px);
  padding: var(--space-4);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  gap: var(--space-2);
  box-shadow:
    inset 0 1px 0 rgb(var(--color-surface) / 0.8),
    var(--shadow-1);
  transition: background var(--dur-base) var(--ease-standard);
  overflow: hidden;
}

/*
 * The blur is an enhancement from `md` up; the solid wash above is what every
 * narrower (and every unsupporting) viewport gets. A phone paints seven of
 * these at once, which is where a backdrop filter actually costs frames.
 */
@media (min-width: 768px) {
  .card-inner {
    background: rgb(var(--color-surface) / 0.88);
    -webkit-backdrop-filter: blur(8px);
    backdrop-filter: blur(8px);
  }
}

.card-ghost-icon {
  position: absolute;
  bottom: -22px;
  right: -18px;
  font-size: 7rem;
  color: rgb(var(--color-fg) / 0.045);
  pointer-events: none;
  transform: rotate(-12deg);
  transition:
    transform var(--dur-slow) var(--ease-standard),
    color var(--dur-base) var(--ease-standard);
}

.card-body {
  position: relative;
  z-index: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-2);
}

.card-icon-wrap {
  width: 52px;
  height: 52px;
  border-radius: var(--radius-lg);
  display: flex;
  align-items: center;
  justify-content: center;
  color: rgb(var(--color-primary-fg));
  box-shadow:
    var(--shadow-2),
    inset 0 1px 0 rgb(var(--color-surface) / 0.45);
  transition: transform var(--dur-base) var(--ease-standard);
}

.card-icon {
  font-size: 1.5rem;
}

.card-text {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.125rem;
}

.card-title {
  font-size: 1.125rem;
  font-weight: 700;
  color: rgb(var(--color-fg));
  letter-spacing: -0.015em;
  margin: 0;
  line-height: 1.2;
}

.card-subtitle {
  font-size: 0.75rem;
  color: rgb(var(--color-fg-muted));
  font-weight: 500;
  margin: 0;
  letter-spacing: 0.02em;
  text-transform: uppercase;
}

.card-arrow {
  position: absolute;
  top: var(--space-3);
  right: var(--space-3);
  font-size: 0.875rem;
  color: rgb(var(--color-fg-muted));
  opacity: 0;
  transform: translate(-4px, 4px);
  transition:
    opacity var(--dur-fast) var(--ease-standard),
    transform var(--dur-fast) var(--ease-standard),
    color var(--dur-fast) var(--ease-standard);
  z-index: 2;
}

/* ===== Resources ===== */
.resources {
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.resources-label {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: 0.75rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.14em;
  color: rgb(var(--color-fg-muted));
  padding-left: var(--space-1);
}

.resources-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: var(--space-2);
}

/* 44 px is the WCAG 2.2 target-size floor; the old pill measured 41. */
.resource-pill {
  position: relative;
  display: flex;
  align-items: center;
  gap: var(--space-2);
  min-height: 2.75rem;
  padding: var(--space-2) var(--space-3);
  background: rgb(var(--color-surface));
  border: 1px solid rgb(var(--color-line));
  border-radius: var(--radius-md);
  text-decoration: none;
  color: rgb(var(--color-fg));
  font-weight: 600;
  font-size: 0.875rem;
  box-shadow: var(--shadow-1);
  transition:
    transform var(--dur-fast) var(--ease-standard),
    background-color var(--dur-fast) var(--ease-standard),
    box-shadow var(--dur-base) var(--ease-standard),
    border-color var(--dur-base) var(--ease-standard);
  overflow: hidden;
  isolation: isolate;
}

@media (min-width: 768px) {
  .resource-pill {
    background: rgb(var(--color-surface) / 0.8);
    -webkit-backdrop-filter: blur(8px);
    backdrop-filter: blur(8px);
  }
}

.resource-pill::before {
  content: "";
  position: absolute;
  inset: 0;
  pointer-events: none;
  background: linear-gradient(
    120deg,
    rgb(var(--color-primary) / 0) 35%,
    rgb(var(--color-primary) / 0.1) 50%,
    rgb(var(--color-primary) / 0) 65%
  );
  transform: translateX(-100%);
  transition: transform var(--dur-slow) var(--ease-standard);
}

.resource-icon {
  width: 32px;
  height: 32px;
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  color: rgb(var(--color-primary-fg));
  font-size: 0.875rem;
  box-shadow:
    var(--shadow-1),
    inset 0 1px 0 rgb(var(--color-surface) / 0.35);
  flex-shrink: 0;
}

.resource-title {
  flex: 1;
}

.resource-ext {
  font-size: 0.75rem;
  color: rgb(var(--color-fg-muted));
  opacity: 0;
  transform: translate(-4px, 0);
  transition:
    opacity var(--dur-fast) var(--ease-standard),
    transform var(--dur-fast) var(--ease-standard),
    color var(--dur-fast) var(--ease-standard);
}

/* ===== Hover choreography =====
 *
 * All of it behind `(hover: hover)`. On a touch device these rules fire on
 * tap-and-hold and then stick until the next tap somewhere else, which reads
 * as a card that got selected — and the two *reveals* below (the arrow and the
 * external-link mark) would simply never appear at all.
 */
@media (hover: hover) {
  .offer-btn:hover {
    box-shadow: 0 18px 40px -10px rgb(var(--color-primary) / 0.55);
  }
  .offer-btn:hover .offer-btn-glow {
    transform: translateX(100%);
  }

  .feature-card:hover {
    transform: translateY(-4px) scale(1.015);
    box-shadow: var(--shadow-3);
  }
  .feature-card:hover .card-gradient {
    transform: scale(1.05);
  }
  .feature-card:hover .card-inner {
    background: rgb(var(--color-surface));
  }
  .feature-card:hover .card-ghost-icon {
    transform: rotate(-6deg) translate(-4px, -4px) scale(1.05);
    color: rgb(var(--color-primary) / 0.07);
  }
  .feature-card:hover .card-icon-wrap {
    transform: scale(1.1) rotate(-4deg);
  }
  .feature-card:hover .card-arrow {
    opacity: 1;
    transform: translate(0, 0);
    color: rgb(var(--color-primary));
  }

  .resource-pill:hover {
    transform: translateY(-2px);
    border-color: rgb(var(--color-primary) / 0.4);
    box-shadow: var(--shadow-2);
  }
  .resource-pill:hover::before {
    transform: translateX(100%);
  }
  .resource-pill:hover .resource-ext {
    opacity: 1;
    transform: translate(0, 0);
    color: rgb(var(--color-primary));
  }
}

/*
 * The touch half of the same bargain: a pressed state a finger can see, and
 * the two hover-only marks shown outright, since there is no hover to reveal
 * them with.
 */
.feature-card:active {
  transform: scale(0.985);
}

.feature-card:active .card-inner {
  background: rgb(var(--color-surface-muted));
}

.resource-pill:active {
  transform: scale(0.985);
  background: rgb(var(--color-surface-muted));
}

@media (hover: none) {
  .card-arrow,
  .resource-ext {
    opacity: 0.7;
    transform: translate(0, 0);
  }
}

/* ===== Responsive tweaks ===== */
@media (max-width: 900px) {
  .landing-root {
    height: auto;
    min-height: 100%;
    overflow: visible;
  }
  .landing-content {
    gap: var(--space-3);
  }
  .feature-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    grid-template-rows: auto;
  }
  .feature-card.tile,
  .feature-card.wide {
    grid-column: span 1;
    min-height: 6.875rem;
  }
  .resources-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .landing-header {
    flex-direction: column;
    align-items: flex-start;
  }
  .offer-btn {
    align-self: stretch;
  }
}

@media (min-width: 1280px) {
  .card-title {
    font-size: 1.25rem;
  }
  .card-icon-wrap {
    width: 60px;
    height: 60px;
  }
  .card-icon {
    font-size: 1.75rem;
  }
  .card-ghost-icon {
    font-size: 8.5rem;
  }
}
</style>
