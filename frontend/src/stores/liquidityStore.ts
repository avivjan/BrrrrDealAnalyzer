import { defineStore } from 'pinia';
import api from '@/api';
import type { LiquiditySettings } from '@/types';

export const useLiquidityStore = defineStore('liquidity', {
  state: () => ({
    bigWhale: 0,
    miniWhale: 0,
    loading: false,
    error: null as string | null,
  }),
  getters: {
    totalLiquidity: (state) => {
      return 2 * Math.min(state.bigWhale, state.miniWhale);
    },
  },
  actions: {
    async fetchLiquidity() {
      this.loading = true;
      try {
        const data = await api.getLiquidity();
        this.bigWhale = data.big_whale_amount;
        this.miniWhale = data.mini_whale_amount;
        this.error = null;
      } catch (err: any) {
        this.error = err.message || 'Failed to fetch liquidity settings';
        console.error('Liquidity Store Error:', err);
      } finally {
        this.loading = false;
      }
    },
    async updateLiquidity(bigWhale: number, miniWhale: number) {
      // Optimistic update
      this.bigWhale = bigWhale;
      this.miniWhale = miniWhale;
      
      try {
        const payload: LiquiditySettings = {
            big_whale_amount: bigWhale,
            mini_whale_amount: miniWhale
        };
        await api.updateLiquidity(payload);
        this.error = null;
      } catch (err: any) {
        this.error = err.message || 'Failed to update liquidity settings';
        console.error('Liquidity Store Error:', err);
        // Revert on failure? Or just show error.
        // For now, let's just log it. A real app might want to revert state.
        await this.fetchLiquidity(); // Revert to server state
      }
    },
    async updateBigWhale(amount: number) {
        await this.updateLiquidity(amount, this.miniWhale);
    },
    async updateMiniWhale(amount: number) {
        await this.updateLiquidity(this.bigWhale, amount);
    }
  },
});

