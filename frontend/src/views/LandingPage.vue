<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import PortfolioStatsBar from "../components/PortfolioStatsBar.vue";
import SendOfferModal from "../components/SendOfferModal.vue";
import { useDealStore } from "../stores/dealStore";

console.log("View: LandingPage setup");

const isOfferModalOpen = ref(false);
const dealStore = useDealStore();

const hasPortfolioBar = computed(
  () => dealStore.portfolioStats.numDoors > 0
);

/** Figures for the tiles that have one, from data App.vue already fetched. */
const figures = computed<Record<NonNullable<FeatureCard["figure"]>, string>>(() => ({
  active: String(dealStore.deals.length),
  doors: String(dealStore.portfolioStats.numDoors),
}));

const greeting = computed(() => {
  const hour = new Date().getHours();
  return hour < 12 ? "Good morning" : hour < 18 ? "Good afternoon" : "Good evening";
});

const today = computed(() =>
  new Date().toLocaleDateString(undefined, { weekday: "long", month: "long", day: "numeric" })
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
  /** Dashboard tile: the store figure shown beside the title, if any. */
  figure?: "active" | "doors";
}

const cards: FeatureCard[] = [
  {
    title: "REPS Tracker",
    subtitle: "Log hours",
    icon: "pi pi-clock",
    action: "internal",
    route: "/reps",
  },
  {
    title: "Daily Tasks",
    subtitle: "Stay on track",
    icon: "pi pi-check-square",
    action: "external",
    url: "https://docs.google.com/document/d/1xW8KKv-mrJlHxcFwuibhVr685R_CE7BhkJcIECHiI8k/edit?tab=t.0",
  },
  {
    title: "Stessa",
    subtitle: "Bookkeeping",
    icon: "pi pi-database",
    action: "external",
    url: "https://app.stessa.com/web3/dashboard",
  },
  {
    title: "Analyze Deal",
    subtitle: "Run the numbers",
    icon: "pi pi-calculator",
    action: "internal",
    route: "/analyze",
  },
  {
    title: "My Deals",
    subtitle: "Pipeline",
    icon: "pi pi-objects-column",
    action: "internal",
    route: "/my-deals",
    figure: "active",
  },
  {
    title: "Bought Deals",
    subtitle: "Portfolio",
    icon: "pi pi-check-circle",
    action: "internal",
    route: "/bought-deals",
    figure: "doors",
  },
  {
    title: "Liquidity",
    subtitle: "Cash flow",
    icon: "pi pi-chart-line",
    action: "internal",
    route: "/liquidity",
  },
];

interface ResourceLink {
  title: string;
  icon: string;
  url: string;
}

const resources: ResourceLink[] = [
  {
    title: "Contractors",
    icon: "pi pi-users",
    url: "https://docs.google.com/document/d/1U5ryt5Rrmo70FcAzvxo-i_Ra6nZazI0xsIQ7zSA0yCw/edit?tab=t.0",
  },
  {
    title: "Lenders",
    icon: "pi pi-wallet",
    url: "https://docs.google.com/document/d/1z81cSxV0_R-hPX811XjxPWuiV-tgUrXWq7X6bZ3ZHas/edit?tab=t.0",
  },
  {
    title: "PM",
    icon: "pi pi-building",
    url: "https://docs.google.com/document/d/1qbzRvgt7zIYnZaHUIgxhMXHi7Fi1wZ1uIky-VkIfJXk/edit?tab=t.0",
  },
  {
    title: "Wholesalers",
    icon: "pi pi-shopping-bag",
    url: "https://docs.google.com/document/d/1-foWzLM6xjeGVVEyLqNk8AdCg-s3j9TC6cZ15GIvFZI/edit?tab=t.0",
  },
];

const logExternal = (card: FeatureCard) => {
  console.log("View: LandingPage - Opening link:", card.title, card.url);
};
</script>

<template>
  <!--
    The dashboard (route `/`). Same hooks and hrefs as the v1 landing page —
    `landing.offer`, the seven `landing.card.<title>` tiles, the four
    `landing.resource.<title>` links — and the same network contract (nothing
    here fetches; the figures come from what App.vue already loaded). The
    portfolio strip renders inside a slot with its height reserved, so the
    layout does not shift when the deals arrive.
  -->
  <div class="landing-root relative mx-auto flex w-full max-w-7xl flex-col gap-6 px-4 py-5 sm:px-6 lg:gap-8 lg:px-8 lg:py-8">
    <!-- Ambient background: the look's `--ambient` keyframes, CSS only. -->
    <div class="bg-decor pointer-events-none absolute inset-0 -z-10 overflow-hidden" aria-hidden="true">
      <div class="blob blob-1" />
      <div class="blob blob-2" />
    </div>

    <header class="flex flex-wrap items-end justify-between gap-4">
      <div class="min-w-0">
        <p class="numeric text-xs uppercase tracking-[0.14em] text-fg-muted">{{ today }}</p>
        <h2 class="mt-1 font-display text-3xl font-bold leading-tight tracking-display text-fg sm:text-4xl">
          {{ greeting }}
        </h2>
        <p class="mt-1 text-sm text-fg-muted">Your real-estate command center.</p>
      </div>

      <UiButton
        data-testid="landing.offer"
        variant="primary"
        size="lg"
        class="shadow-glow-primary"
        @click="isOfferModalOpen = true"
      >
        <i class="pi pi-send" aria-hidden="true" />
        <span>Send Market Offer</span>
      </UiButton>
    </header>

    <!-- Reserved height: the bar mounts after fetchDeals and must not push the tiles. -->
    <div class="min-h-stats-bar" :class="{ 'has-bar': hasPortfolioBar }">
      <PortfolioStatsBar />
    </div>

    <section aria-labelledby="dashboard-tools" class="flex flex-col gap-3">
      <UiSectionHeader as="h3" id="dashboard-tools">
        <template #default>Tools</template>
      </UiSectionHeader>
      <div v-reveal.stagger class="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-4">
        <component
          v-for="card in cards"
          :key="card.title"
          :is="card.action === 'internal' ? 'RouterLink' : 'a'"
          :to="card.action === 'internal' ? card.route : undefined"
          :href="card.action === 'external' ? card.url : undefined"
          :target="card.action === 'external' ? '_blank' : undefined"
          :rel="card.action === 'external' ? 'noopener' : undefined"
          :data-testid="`landing.card.${card.title}`"
          data-reveal
          class="group relative flex min-h-[8.5rem] flex-col justify-between overflow-hidden rounded-card border-ui border-line bg-surface p-4 text-fg no-underline shadow-1 transition-[transform,box-shadow,border-color] duration-fast ease-standard hover:-translate-y-0.5 hover:border-primary/40 hover:shadow-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-page"
          @click="card.action === 'external' ? logExternal(card) : null"
        >
          <div class="flex items-start justify-between gap-2">
            <span class="grid h-10 w-10 place-items-center rounded-ctl bg-primary/12 text-primary" aria-hidden="true">
              <i :class="[card.icon, 'text-base']" />
            </span>
            <i
              :class="[card.action === 'external' ? 'pi pi-external-link' : 'pi pi-arrow-right', 'text-xs text-fg-muted transition-transform duration-fast ease-standard group-hover:translate-x-0.5']"
              aria-hidden="true"
            />
          </div>
          <div class="flex items-end justify-between gap-2">
            <div class="min-w-0">
              <h4 class="truncate font-display text-base font-semibold tracking-display text-fg">{{ card.title }}</h4>
              <p class="text-xs text-fg-muted">{{ card.subtitle }}</p>
            </div>
            <span v-if="card.figure" class="numeric text-2xl font-semibold leading-none text-fg">{{ figures[card.figure] }}</span>
          </div>
        </component>
      </div>
    </section>

    <section aria-labelledby="dashboard-resources" class="flex flex-col gap-3">
      <UiSectionHeader as="h3" id="dashboard-resources">
        <template #default>Professional resources</template>
      </UiSectionHeader>
      <div class="flex flex-wrap gap-2">
        <UiChip
          v-for="r in resources"
          :key="r.title"
          :data-testid="`landing.resource.${r.title}`"
          :href="r.url"
          target="_blank"
          rel="noopener"
          tone="neutral"
          size="md"
          :icon="r.icon"
        >
          {{ r.title }}
          <i class="pi pi-external-link text-[0.7em] text-fg-muted" aria-hidden="true" />
        </UiChip>
      </div>
    </section>

    <SendOfferModal :isOpen="isOfferModalOpen" @close="isOfferModalOpen = false" />
  </div>
</template>

<style scoped>
/*
 * Ambient blobs, driven by the look: `--ambient` is `gradient-drift` in Aurora
 * Glass, `shimmer` in Quiet Luxury, `none` elsewhere. CSS keyframes only —
 * never GSAP, which the e2e no-live-tweens guard would catch. The global
 * reduced-motion rules neutralise the animation; `(hover: none)` pauses it on
 * phones to spare the GPU.
 */
.blob {
  position: absolute;
  width: 34rem;
  height: 34rem;
  border-radius: 9999px;
  filter: blur(80px);
  opacity: 0.35;
  background: var(--gradient-brand);
  animation: float 18s ease-in-out infinite;
  animation-play-state: var(--ambient-play, running);
}

.blob-1 {
  top: -12rem;
  left: -8rem;
}

.blob-2 {
  right: -10rem;
  bottom: -14rem;
  animation-delay: -9s;
}

/* Looks without an ambient effect show a still, faint wash. */
.landing-root {
  --ambient-play: running;
}

:global([data-look="obsidian"]) .landing-root,
:global([data-look="brutal"]) .landing-root {
  --ambient-play: paused;
}

:global([data-look="obsidian"]) .blob,
:global([data-look="brutal"]) .blob {
  opacity: 0.12;
}

@media (hover: none), (prefers-reduced-motion: reduce) {
  .blob {
    animation-play-state: paused;
  }
}
</style>
