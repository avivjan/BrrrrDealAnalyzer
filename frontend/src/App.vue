<script setup lang="ts">
import { RouterView } from "vue-router";
import { useConnectionStore } from "./stores/connectionStore";
import { onMounted } from "vue";
import { apiClient } from "./api";
import LiquidityHeader from "./components/LiquidityHeader.vue";

const connectionStore = useConnectionStore();

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
    }
  );

  // Wake up the backend immediately
  connectionStore.checkConnection();
});
</script>

<template>
  <div
    class="min-h-screen bg-gray-50 text-gray-900 font-sans selection:bg-blue-500 selection:text-white relative"
  >
    <!-- Server Status Indicator -->
    <div
      class="fixed top-2 right-2 z-50 w-3 h-3 rounded-full shadow-sm transition-colors duration-300"
      :class="
        connectionStore.isChecking || !connectionStore.isConnected
          ? 'bg-red-500 animate-pulse'
          : 'bg-green-500'
      "
      :title="
        connectionStore.isChecking
          ? 'Connecting to server...'
          : connectionStore.isConnected
          ? 'Server Connected'
          : 'Disconnected'
      "
    ></div>

    <LiquidityHeader />
    <RouterView />
  </div>
</template>
