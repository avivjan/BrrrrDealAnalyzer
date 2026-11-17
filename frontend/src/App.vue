<script setup lang="ts">
import { RouterView } from "vue-router";
import { useConnectionStore } from "./stores/connectionStore";
import { useDealStore } from "./stores/dealStore";
import { useAuthStore } from "./stores/authStore";
import { onMounted, watch } from "vue";
import { apiClient } from "./api";
import router from "./router";
import AppShell from "./components/shell/AppShell.vue";
import AppKeyGate from "./components/shell/AppKeyGate.vue";
import SecurityBar from "./components/shell/SecurityBar.vue";
import LiquidityTimelineChangePrompt from "./components/liquidity/LiquidityTimelineChangePrompt.vue";
import LiquidityRowsChangedNotice from "./components/liquidity/LiquidityRowsChangedNotice.vue";

const connectionStore = useConnectionStore();
const dealStore = useDealStore();
const authStore = useAuthStore();

/** Auth statuses where the API answers data routes; `anon` and `pending` are sent to /login or /pending instead. */
const AUTH_STATUSES_THAT_CAN_READ_DEALS = ["off", "trusted"];

onMounted(async () => {
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

  // Fetch deals globally so portfolio stats are available on all pages --
  // except on a public inspection page, where a visitor may not be logged in.
  // The route is resolved from the address bar now, so the request order is unchanged.
  if (router.resolve(window.location.pathname).meta.public === true) return;
  // Wait for the first navigation: its guard runs `auth.load()`, which renews a
  // session whose 15-minute access cookie expired while the site was closed.
  // Fetching before that answered 401 and left the dashboard empty until a reload.
  // When the visitor has to sign in (or wait for device approval) first, the
  // deals load the moment the session becomes usable, once.
  await router.isReady();
  let haveDealsBeenFetchedForThisSession = false;
  watch(
    () => authStore.status,
    (authStatus) => {
      if (haveDealsBeenFetchedForThisSession || !AUTH_STATUSES_THAT_CAN_READ_DEALS.includes(authStatus)) return;
      haveDealsBeenFetchedForThisSession = true;
      dealStore.fetchDeals();
    },
    { immediate: true },
  );
});
</script>

<template>
  <!--
    UI v2: the persistent shell (sidebar, topbar, one <main> scroller, bottom
    nav, command palette, Appearance settings) frames every route. The stats
    bar moved into the dashboard view, inside a height-reserved slot, so its
    arrival after `fetchDeals` no longer shifts every page. `app.status` lives
    in the topbar now, with the same hook, role and strings.

    `page` is opacity-only and has no `leave` hook, so a route change is never
    held back by an animation and a modal opened from a deep link is never
    positioned relative to a transformed ancestor.
  -->
  <AppShell>
    <SecurityBar />
    <RouterView v-slot="{ Component }"><UiTransition preset="page" appear><component :is="Component" /></UiTransition></RouterView>
  </AppShell>
  <AppKeyGate />
  <!-- "This changes the liquidity timeline" and its one notice: any page can ask (tasks/todo/ConstructionAccountPerRehab.md). -->
  <LiquidityTimelineChangePrompt />
  <LiquidityRowsChangedNotice />
</template>
