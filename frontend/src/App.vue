<script setup lang="ts">
import { RouterView } from "vue-router";
import { useConnectionStore } from "./stores/connectionStore";
import { useDealStore } from "./stores/dealStore";
import { onMounted } from "vue";
import { apiClient } from "./api";
import AppShell from "./components/shell/AppShell.vue";
import AppKeyGate from "./components/shell/AppKeyGate.vue";
import SecurityBar from "./components/shell/SecurityBar.vue";

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
</template>
