import { defineStore } from 'pinia';
import { ref } from 'vue';
import api from '../api';

export const useConnectionStore = defineStore('connection', () => {
  const isConnected = ref(false);
  const isChecking = ref(false);
  const lastCheck = ref<Date | null>(null);

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

  return {
    isConnected,
    isChecking,
    checkConnection
  };
});
