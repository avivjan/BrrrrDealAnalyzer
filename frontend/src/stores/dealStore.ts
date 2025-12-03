import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import api from '../api';
import type { ActiveDealRes, ActiveDealCreate, AnalyzeDealReq, AnalyzeDealRes } from '../types';

export const useDealStore = defineStore('deals', () => {
  const deals = ref<ActiveDealRes[]>([]);
  const currentAnalysisResult = ref<AnalyzeDealRes | null>(null);
  const isLoading = ref(false);
  const error = ref<string | null>(null);

  const dealsBySection = computed(() => {
    return {
      wholesale: deals.value.filter(d => d.section === 1),
      market: deals.value.filter(d => d.section === 2),
      offMarket: deals.value.filter(d => d.section === 3),
    };
  });

  async function fetchDeals() {
    isLoading.value = true;
    try {
      deals.value = await api.getActiveDeals();
    } catch (err) {
      error.value = 'Failed to fetch deals';
      console.error(err);
    } finally {
      isLoading.value = false;
    }
  }

  async function analyze(data: AnalyzeDealReq) {
    // Don't set global loading for debounce calc, but we could track "calculating" state
    try {
      const result = await api.analyzeDeal(data);
      currentAnalysisResult.value = result;
      return result;
    } catch (err) {
      console.error(err);
      throw err;
    }
  }

  async function saveDeal(deal: ActiveDealCreate) {
    isLoading.value = true;
    try {
      const newDeal = await api.saveActiveDeal(deal);
      deals.value.push(newDeal);
      return newDeal;
    } catch (err) {
      error.value = 'Failed to save deal';
      console.error(err);
      throw err;
    } finally {
      isLoading.value = false;
    }
  }

  async function updateDeal(deal: ActiveDealRes) {
    isLoading.value = true;
    try {
      const updatedDeal = await api.updateActiveDeal(deal);
      const index = deals.value.findIndex(d => d.id === deal.id);
      if (index !== -1) {
        deals.value[index] = updatedDeal;
      }
      return updatedDeal;
    } catch (err) {
      error.value = 'Failed to update deal';
      console.error(err);
      throw err;
    } finally {
      isLoading.value = false;
    }
  }

  async function updateDealStage(dealId: number, newStage: number) {
    // Optimistic update
    const deal = deals.value.find(d => d.id === dealId);
    if (deal) {
      const oldStage = deal.stage;
      deal.stage = newStage;
      
      try {
        await api.updateActiveDeal(deal);
      } catch (err) {
        // Revert on failure
        deal.stage = oldStage;
        console.error('Failed to update stage', err);
      }
    }
  }

  async function deleteDeal(dealId: number) {
    isLoading.value = true;
    try {
      await api.deleteActiveDeal(dealId);
      deals.value = deals.value.filter(d => d.id !== dealId);
    } catch (err) {
      error.value = 'Failed to delete deal';
      console.error(err);
      throw err;
    } finally {
      isLoading.value = false;
    }
  }

  return {
    deals,
    currentAnalysisResult,
    isLoading,
    error,
    dealsBySection,
    fetchDeals,
    analyze,
    saveDeal,
    updateDeal,
    updateDealStage,
    deleteDeal,
  };
});


