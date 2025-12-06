<script setup lang="ts">
import { RouterView } from "vue-router";
import { useConnectionStore } from "./stores/connectionStore";
import { onMounted, onUnmounted } from "vue";

const connectionStore = useConnectionStore();

onMounted(() => {
  connectionStore.startKeepAlive();
});

onUnmounted(() => {
  connectionStore.stopKeepAlive();
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

    <RouterView />
  </div>
</template>
