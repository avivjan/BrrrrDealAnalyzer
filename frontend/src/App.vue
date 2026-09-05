<script setup lang="ts">
import { RouterView } from "vue-router";
import { useConnectionStore } from "./stores/connectionStore";
import { useDealStore } from "./stores/dealStore";
import { onMounted } from "vue";
import { apiClient } from "./api";
import PortfolioStatsBar from "./components/PortfolioStatsBar.vue";

const connectionStore = useConnectionStore();
const dealStore = useDealStore();

onMounted(() => {
  // Setup global interceptors to track connection status
  apiClient.interceptors.request.use((config) => {
    connectionStore.isChecking = true;
    return config;
  });

  apiClient.interceptors.response.use(
    (response) => {
      connectionStore.isChecking = false;
      connectionStore.isConnected = true;
      return response;
    },
    (error) => {
      connectionStore.isChecking = false;
      if (error.response) {
        // Server responded with an error status code (e.g. 400, 500)
        // This means the server IS connected/awake
        connectionStore.isConnected = true;
      } else if (error.request) {
        // Request made but no response received (Network Error / Server Down)
        connectionStore.isConnected = false;
      }
      return Promise.reject(error);
    },
  );

  // Wake up the backend immediately
  connectionStore.checkConnection();

  // Fetch deals globally so portfolio stats are available on all pages
  dealStore.fetchDeals();
});
</script>

<template>
  <!--
    The app shell: a one-screen column where the stats bar takes the height it
    needs and the routed view takes the rest. `dvh` excludes the iOS toolbars,
    so the column is one screen rather than one screen plus browser chrome.
    `h-dvh`, not `min-h-dvh`: a `min-height` leaves the column's height
    *indefinite*, and then `height: 100%` inside a routed view — which is how
    the landing page fills what the bar leaves — resolves to `auto` and the page
    collapses to its content. A view taller than the screen still overflows and
    still scrolls the document (measured on every route), and each view paints
    its own background over its own box, so nothing is left unpainted.
    The `vh` fallback is in the style block below rather than a second utility:
    Tailwind emits `.h-screen` *after* `.h-dvh`, so the pair would resolve the
    wrong way round.
  -->
  <div
    class="app-shell relative flex h-dvh flex-col bg-page font-sans text-fg selection:bg-primary selection:text-primary-fg"
  >
    <!--
      Server Status Indicator. A live region rather than a bare dot: colour was
      its only channel, and `aria-label` mirrors the tooltip so the state is
      readable without a pointer. Inset with `max()` because `index.html` sets
      `viewport-fit=cover`, so the notch would otherwise sit on top of it.
    -->
    <div
      data-testid="app.status"
      role="status"
      aria-live="polite"
      class="fixed right-[max(0.5rem,env(safe-area-inset-right))] top-[max(0.5rem,env(safe-area-inset-top))] z-50 h-3 w-3 rounded-full shadow-1 transition-colors duration-base ease-standard"
      :class="
        connectionStore.isChecking || !connectionStore.isConnected
          ? 'bg-negative animate-pulse'
          : 'bg-positive'
      "
      :title="
        connectionStore.isChecking
          ? 'Connecting to server...'
          : connectionStore.isConnected
            ? 'Server Connected'
            : 'Disconnected'
      "
      :aria-label="
        connectionStore.isChecking
          ? 'Connecting to server...'
          : connectionStore.isConnected
            ? 'Server Connected'
            : 'Disconnected'
      "
    ></div>

    <div class="flex-none">
      <PortfolioStatsBar />
    </div>

    <!--
      `min-h-0` so a view that scrolls inside itself can, rather than being
      floored at its content height. This column is what replaced the landing
      page's `calc(100dvh - 60px)` guess at the stats bar's height.
    -->
    <!--
      The one `RouterView` rewrite Phase 4 is allowed (allowlist row
      `routerview-transition-slot`): the slot form is the only way to put a
      transition around the routed component without touching this file's
      script. `page` is opacity-only and has no `leave` hook at all, so a route
      change is never held back by an animation and the column's height — which
      the landing page fills — is never transformed.
    -->
    <div class="min-h-0 flex-1">
      <RouterView v-slot="{ Component }"><UiTransition preset="page" appear><component :is="Component" /></UiTransition></RouterView>
    </div>
  </div>
</template>

<style scoped>
/*
 * The `dvh` fallback, and only where it is needed. `h-dvh` on the root leaves
 * engines that do not know the unit (iOS 15.0–15.3, inside this project's
 * browserslist) with no height at all, and then the `flex-1` column has nothing
 * for a view like the landing page to fill. Mirrors the `@supports` pair
 * `main.css` already applies to `body`, inverted so it never competes with the
 * utility it is standing in for.
 */
@supports not (height: 100dvh) {
  .app-shell {
    height: 100vh;
  }
}
</style>
