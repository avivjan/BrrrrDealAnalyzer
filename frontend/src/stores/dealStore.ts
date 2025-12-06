import { defineStore } from 'pinia';
import { ref, computed, toRaw } from 'vue';
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

  const activeDealsCount = computed(() => {
    const activeStages = [1, 2]; // New (1) & Working (2)
    return {
      wholesale: deals.value.filter(d => d.section === 1 && activeStages.includes(d.stage)).length,
      market: deals.value.filter(d => d.section === 2 && activeStages.includes(d.stage)).length,
      offMarket: deals.value.filter(d => d.section === 3 && activeStages.includes(d.stage)).length,
    };
  });

  async function fetchDeals() {
    console.group('Store: fetchDeals');
    console.log('Fetching deals...');
    isLoading.value = true;
    try {
      deals.value = await api.getActiveDeals();
      console.log('Deals updated in store:', deals.value);
    } catch (err) {
      error.value = 'Failed to fetch deals';
      console.error('Store Error:', err);
    } finally {
      isLoading.value = false;
      console.groupEnd();
    }
  }

  async function analyze(data: AnalyzeDealReq, type: 'BRRRR' | 'FLIP') {
    console.group('Store: analyze');
    console.log(`Analyzing deal (${type}) with data:`, data);
    try {
      const result = await api.analyzeDeal(data, type);
      currentAnalysisResult.value = result;
      console.log('Analysis result stored:', result);
      console.groupEnd();
      return result;
    } catch (err) {
      console.error('Store Error:', err);
      console.groupEnd();
      throw err;
    }
  }

  async function saveDeal(deal: ActiveDealCreate) {
    console.group('Store: saveDeal');
    console.log('Saving deal:', deal);
    isLoading.value = true;
    try {
      const newDeal = await api.saveActiveDeal(deal);
      deals.value.push(newDeal);
      console.log('Deal saved and added to store:', newDeal);
      return newDeal;
    } catch (err) {
      error.value = 'Failed to save deal';
      console.error('Store Error:', err);
      throw err;
    } finally {
      isLoading.value = false;
      console.groupEnd();
    }
  }

  async function updateDeal(deal: ActiveDealRes) {
    console.group('Store: updateDeal');
    console.log('Updating deal:', deal);
    isLoading.value = true;
    try {
      const updatedDeal = await api.updateActiveDeal(deal);
      const index = deals.value.findIndex(d => d.id === deal.id && d.deal_type === deal.deal_type);
      // Fallback if deal_type match fails or ID is enough
      // Actually ID might clash, so checking type is important if IDs overlap.
      // But in store they are separate objects.
      
      const realIndex = index !== -1 ? index : deals.value.findIndex(d => d.id === deal.id); // fallback
      
      if (realIndex !== -1) {
        deals.value[realIndex] = updatedDeal;
        console.log('Deal updated in store at index:', realIndex, updatedDeal);
      } else {
        console.warn('Deal not found in local store for update:', deal.id);
      }
      return updatedDeal;
    } catch (err) {
      error.value = 'Failed to update deal';
      console.error('Store Error:', err);
      throw err;
    } finally {
      isLoading.value = false;
      console.groupEnd();
    }
  }

  async function updateDealStage(dealId: string, newStage: number) {
    // This function relies on finding the deal in store to know type.
    console.group('Store: updateDealStage');
    const deal = deals.value.find(d => d.id === dealId); 
    // WARN: If ID clash, this might pick wrong deal.
    // Ideally we pass type or unique ID.
    // Assume user is interacting with a specific card.
    
    if (deal) {
      const oldStage = deal.stage;
      deal.stage = newStage;
      
      try {
        const dealPayload = toRaw(deal);
        const updatedDeal = await api.updateActiveDeal(dealPayload);
        Object.assign(deal, updatedDeal);
      } catch (err) {
        deal.stage = oldStage;
        console.error('Failed to update stage, reverting. Error:', err);
      }
    } else {
        console.error('Deal not found in store:', dealId);
    }
    console.groupEnd();
  }

  async function deleteDeal(dealId: string, type: 'BRRRR' | 'FLIP' = 'BRRRR') {
    console.group('Store: deleteDeal');
    console.log('Deleting deal ID:', dealId, 'Type:', type);
    isLoading.value = true;
    try {
      await api.deleteActiveDeal(dealId, type);
      deals.value = deals.value.filter(d => !(d.id === dealId && (d.deal_type === type || (!d.deal_type && type === 'BRRRR'))));
      console.log('Deal removed from store');
    } catch (err) {
      error.value = 'Failed to delete deal';
      console.error('Store Error:', err);
      throw err;
    } finally {
      isLoading.value = false;
      console.groupEnd();
    }
  }

  async function duplicateDeal(dealId: string, type: 'BRRRR' | 'FLIP' = 'BRRRR') {
    console.group('Store: duplicateDeal');
    console.log('Duplicating deal ID:', dealId, 'Type:', type);
    isLoading.value = true;
    try {
      const newDeal = await api.duplicateActiveDeal(dealId, type);
      deals.value.push(newDeal); // Add to local state
      console.log('Duplicated deal added to store:', newDeal);
      return newDeal;
    } catch (err) {
      error.value = 'Failed to duplicate deal';
      console.error('Store Error:', err);
      throw err;
    } finally {
      isLoading.value = false;
      console.groupEnd();
    }
  }

  return {
    deals,
    currentAnalysisResult,
    isLoading,
    error,
    dealsBySection,
    activeDealsCount,
    fetchDeals,
    analyze,
    saveDeal,
    updateDeal,
    updateDealStage,
    deleteDeal,
    duplicateDeal,
  };
});
