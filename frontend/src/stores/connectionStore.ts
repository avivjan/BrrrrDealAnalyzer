import { defineStore } from 'pinia';
import { ref } from 'vue';
import api from '../api';

export const useConnectionStore = defineStore('connection', () => {
  const isConnected = ref(false);
  const isChecking = ref(false);
  const lastCheck = ref<Date | null>(null);

  // 14 minutes in milliseconds
  const KEEP_ALIVE_INTERVAL = 60 * 1000;
  let intervalId: ReturnType<typeof setInterval> | null = null;

  async function checkConnection() {
    isChecking.value = true;
    try {
      // Use helloworld as a ping because it's lightweight
      await api.helloWorld();
      isConnected.value = true;
      lastCheck.value = new Date();
    } catch (error) {
      console.error('Connection check failed:', error);
      isConnected.value = false;
    } finally {
      isChecking.value = false;
    }
  }

  function startKeepAlive() {
    // Initial check
    checkConnection();

    // Clear existing interval if any
    if (intervalId) {
      clearInterval(intervalId);
    }

    // Set up periodic keep-alive
    intervalId = setInterval(() => {
      console.log('Keep-alive ping triggered');
      checkConnection();
    }, KEEP_ALIVE_INTERVAL);
  }

  function stopKeepAlive() {
    if (intervalId) {
      clearInterval(intervalId);
      intervalId = null;
    }
  }

  return {
    isConnected,
    isChecking,
    checkConnection,
    startKeepAlive,
    stopKeepAlive
  };
});

