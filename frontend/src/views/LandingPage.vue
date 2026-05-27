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

        <button class="offer-btn" @click="isOfferModalOpen = true">
          <span class="offer-btn-glow"></span>
          <i class="pi pi-send offer-btn-icon"></i>
          <span class="offer-btn-text">Send Market Offer</span>
        </button>
      </header>

      <!-- Main feature grid (7 cards: 4 + 3) -->
      <div class="feature-grid">
        <component
          v-for="(card, idx) in cards"
          :key="card.title"
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
          <i class="pi pi-bookmark text-amber-300 text-xs"></i>
          <span>Professional Resources</span>
        </div>
        <div class="resources-grid">
          <a
            v-for="r in resources"
            :key="r.title"
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
/* ===== Layout shell ===== */
.landing-root {
  position: relative;
  height: 100dvh;
  min-height: 560px;
  overflow: hidden;
  background:
    radial-gradient(1200px 600px at 10% -10%, rgba(99, 102, 241, 0.18), transparent 60%),
    radial-gradient(1000px 600px at 110% 10%, rgba(56, 189, 248, 0.18), transparent 60%),
    linear-gradient(180deg, #f8fafc 0%, #eef2ff 100%);
  isolation: isolate;
}

/* When the PortfolioStatsBar is visible above, leave room for it */
.landing-root.has-bar {
  height: calc(100dvh - 60px);
}

.landing-content {
  position: relative;
  z-index: 1;
  height: 100%;
  width: 100%;
  max-width: 1400px;
  margin: 0 auto;
  padding: 1rem 1.25rem 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.85rem;
}

/* ===== Background decor ===== */
.bg-decor {
  position: absolute;
  inset: 0;
  pointer-events: none;
  overflow: hidden;
}

.blob {
  position: absolute;
  border-radius: 9999px;
  filter: blur(80px);
  opacity: 0.5;
  animation: float 18s ease-in-out infinite;
}

.blob-1 {
  top: -120px;
  left: -120px;
  width: 460px;
  height: 460px;
  background: radial-gradient(circle, #6366f1, transparent 60%);
}
.blob-2 {
  bottom: -160px;
  right: -120px;
  width: 520px;
  height: 520px;
  background: radial-gradient(circle, #0ea5e9, transparent 60%);
  animation-delay: -6s;
}
.blob-3 {
  top: 40%;
  left: 45%;
  width: 320px;
  height: 320px;
  background: radial-gradient(circle, #a855f7, transparent 60%);
  opacity: 0.25;
  animation-delay: -12s;
}

.grid-overlay {
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(rgba(15, 23, 42, 0.04) 1px, transparent 1px),
    linear-gradient(90deg, rgba(15, 23, 42, 0.04) 1px, transparent 1px);
  background-size: 48px 48px;
  mask-image: radial-gradient(ellipse at center, black 40%, transparent 80%);
}

@keyframes float {
  0%, 100% { transform: translate(0, 0) scale(1); }
  33% { transform: translate(20px, -30px) scale(1.05); }
  66% { transform: translate(-25px, 25px) scale(0.97); }
}

/* ===== Header ===== */
.landing-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  flex-shrink: 0;
}

.title-block {
  display: flex;
  flex-direction: column;
  gap: 0.1rem;
}

.title {
  display: flex;
  align-items: baseline;
  gap: 0.6rem;
  font-size: clamp(1.65rem, 3vw, 2.6rem);
  font-weight: 800;
  letter-spacing: -0.02em;
  line-height: 1;
  margin: 0;
}

.title-gradient {
  background: linear-gradient(135deg, #2563eb 0%, #6366f1 45%, #8b5cf6 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.title-accent {
  color: #0f172a;
  font-weight: 700;
}

.subtitle {
  font-size: 0.78rem;
  font-weight: 500;
  color: #64748b;
  letter-spacing: 0.02em;
  margin: 0;
}

.offer-btn {
  position: relative;
  display: inline-flex;
  align-items: center;
  gap: 0.55rem;
  padding: 0.65rem 1.25rem;
  border-radius: 9999px;
  background: linear-gradient(135deg, #2563eb 0%, #4f46e5 50%, #7c3aed 100%);
  color: #ffffff;
  font-weight: 600;
  font-size: 0.9rem;
  border: 1px solid rgba(255, 255, 255, 0.2);
  box-shadow:
    0 10px 30px -10px rgba(79, 70, 229, 0.6),
    0 2px 6px rgba(79, 70, 229, 0.25),
    inset 0 1px 0 rgba(255, 255, 255, 0.18);
  cursor: pointer;
  transition: transform 0.25s ease, box-shadow 0.25s ease;
  overflow: hidden;
  white-space: nowrap;
}
.offer-btn:hover {
  transform: translateY(-2px);
  box-shadow:
    0 18px 40px -10px rgba(79, 70, 229, 0.7),
    0 6px 14px rgba(79, 70, 229, 0.35),
    inset 0 1px 0 rgba(255, 255, 255, 0.25);
}
.offer-btn-glow {
  position: absolute;
  inset: 0;
  background: linear-gradient(120deg, transparent 30%, rgba(255,255,255,0.35) 50%, transparent 70%);
  transform: translateX(-100%);
  transition: transform 0.7s ease;
}
.offer-btn:hover .offer-btn-glow {
  transform: translateX(100%);
}
.offer-btn-icon {
  font-size: 0.95rem;
}
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
  gap: 0.85rem;
}

.feature-card {
  position: relative;
  border-radius: 1.1rem;
  padding: 2px;
  cursor: pointer;
  text-decoration: none;
  color: inherit;
  overflow: hidden;
  transition: transform 0.3s cubic-bezier(0.22, 1, 0.36, 1), filter 0.3s ease;
  min-height: 0;
}

.feature-card.tile {
  grid-column: span 3;
}

.feature-card.wide {
  grid-column: span 4;
}

.feature-card:hover {
  transform: translateY(-4px) scale(1.015);
  filter: brightness(1.04);
}

.card-gradient {
  position: absolute;
  inset: 0;
  border-radius: inherit;
  opacity: 1;
  transition: opacity 0.3s ease, transform 0.5s ease;
}

.feature-card:hover .card-gradient {
  transform: scale(1.05);
}

.card-inner {
  position: relative;
  z-index: 1;
  height: 100%;
  width: 100%;
  background: rgba(255, 255, 255, 0.96);
  backdrop-filter: blur(8px);
  border-radius: calc(1.1rem - 2px);
  padding: 1.1rem 1.2rem;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  gap: 0.6rem;
  box-shadow:
    0 1px 0 rgba(255, 255, 255, 0.8) inset,
    0 12px 28px -16px rgba(15, 23, 42, 0.18);
  transition: background 0.3s ease;
  overflow: hidden;
}

.feature-card:hover .card-inner {
  background: rgba(255, 255, 255, 0.99);
}

.card-ghost-icon {
  position: absolute;
  bottom: -22px;
  right: -18px;
  font-size: 7rem;
  color: rgba(15, 23, 42, 0.045);
  pointer-events: none;
  transform: rotate(-12deg);
  transition: transform 0.5s cubic-bezier(0.22, 1, 0.36, 1), color 0.4s ease;
}

.feature-card:hover .card-ghost-icon {
  transform: rotate(-6deg) translate(-4px, -4px) scale(1.05);
  color: rgba(79, 70, 229, 0.07);
}

.card-body {
  position: relative;
  z-index: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.7rem;
}

.card-icon-wrap {
  width: 52px;
  height: 52px;
  border-radius: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #ffffff;
  box-shadow:
    0 8px 20px -6px rgba(15, 23, 42, 0.35),
    inset 0 1px 0 rgba(255, 255, 255, 0.45);
  transition: transform 0.35s cubic-bezier(0.22, 1, 0.36, 1);
}

.feature-card:hover .card-icon-wrap {
  transform: scale(1.1) rotate(-4deg);
}

.card-icon {
  font-size: 1.55rem;
  text-shadow: 0 1px 2px rgba(0, 0, 0, 0.18);
}

.card-text {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.15rem;
}

.card-title {
  font-size: 1.1rem;
  font-weight: 800;
  color: #0f172a;
  letter-spacing: -0.015em;
  margin: 0;
  line-height: 1.15;
}

.card-subtitle {
  font-size: 0.73rem;
  color: #64748b;
  font-weight: 500;
  margin: 0;
  letter-spacing: 0.02em;
  text-transform: uppercase;
}

.card-arrow {
  position: absolute;
  top: 0.85rem;
  right: 0.95rem;
  font-size: 0.85rem;
  color: #94a3b8;
  opacity: 0;
  transform: translate(-4px, 4px);
  transition: opacity 0.25s ease, transform 0.25s ease, color 0.25s ease;
  z-index: 2;
}

.feature-card:hover .card-arrow {
  opacity: 1;
  transform: translate(0, 0);
  color: #4f46e5;
}

/* ===== Resources ===== */
.resources {
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}

.resources-label {
  display: flex;
  align-items: center;
  gap: 0.45rem;
  font-size: 0.65rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.18em;
  color: #64748b;
  padding-left: 0.25rem;
}

.resources-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 0.6rem;
}

.resource-pill {
  position: relative;
  display: flex;
  align-items: center;
  gap: 0.65rem;
  padding: 0.6rem 0.85rem;
  background: rgba(255, 255, 255, 0.85);
  border: 1px solid rgba(226, 232, 240, 0.85);
  border-radius: 0.85rem;
  text-decoration: none;
  color: #0f172a;
  font-weight: 600;
  font-size: 0.9rem;
  backdrop-filter: blur(8px);
  box-shadow:
    0 1px 0 rgba(255, 255, 255, 0.8) inset,
    0 8px 18px -12px rgba(15, 23, 42, 0.18);
  transition: transform 0.2s ease, box-shadow 0.25s ease, border-color 0.25s ease;
  overflow: hidden;
}

.resource-pill::before {
  content: "";
  position: absolute;
  inset: 0;
  background: linear-gradient(120deg, transparent 35%, rgba(99, 102, 241, 0.08) 50%, transparent 65%);
  transform: translateX(-100%);
  transition: transform 0.6s ease;
}

.resource-pill:hover {
  transform: translateY(-2px);
  border-color: rgba(99, 102, 241, 0.4);
  box-shadow:
    0 1px 0 rgba(255, 255, 255, 0.8) inset,
    0 14px 26px -14px rgba(79, 70, 229, 0.35);
}

.resource-pill:hover::before {
  transform: translateX(100%);
}

.resource-icon {
  width: 32px;
  height: 32px;
  border-radius: 9px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #ffffff;
  font-size: 0.9rem;
  box-shadow:
    0 4px 10px -3px rgba(15, 23, 42, 0.25),
    inset 0 1px 0 rgba(255, 255, 255, 0.35);
  flex-shrink: 0;
}

.resource-title {
  flex: 1;
}

.resource-ext {
  font-size: 0.72rem;
  color: #94a3b8;
  opacity: 0;
  transform: translate(-4px, 0);
  transition: opacity 0.25s ease, transform 0.25s ease;
}

.resource-pill:hover .resource-ext {
  opacity: 1;
  transform: translate(0, 0);
  color: #4f46e5;
}

/* ===== Responsive tweaks ===== */
@media (max-width: 900px) {
  .landing-root {
    height: auto;
    min-height: calc(100dvh - 60px);
    overflow: visible;
  }
  .landing-content {
    gap: 0.9rem;
  }
  .feature-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    grid-template-rows: auto;
  }
  .feature-card.tile,
  .feature-card.wide {
    grid-column: span 1;
    min-height: 110px;
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
    justify-content: center;
  }
}

@media (min-width: 1280px) {
  .card-title {
    font-size: 1.25rem;
  }
  .card-icon-wrap {
    width: 60px;
    height: 60px;
    border-radius: 16px;
  }
  .card-icon {
    font-size: 1.8rem;
  }
  .card-ghost-icon {
    font-size: 8.5rem;
  }
}
</style>
