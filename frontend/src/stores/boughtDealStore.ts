import { defineStore } from 'pinia';
import { ref, computed, toRaw } from 'vue';
import api from '../api';
import type { BoughtDealRes, AnalyzeDealReq, AnalyzeDealRes } from '../types';
import { canAdvance } from '../config/boughtDealStages';
import { usePipelineTemplateStore } from './pipelineTemplateStore';

export const useBoughtDealStore = defineStore('boughtDeals', () => {
  const boughtDeals = ref<BoughtDealRes[]>([]);
  const isLoading = ref(false);
  const error = ref<string | null>(null);

  const dealsByType = computed(() => ({
    BRRRR: boughtDeals.value.filter(d => d.deal_type === 'BRRRR'),
    FLIP: boughtDeals.value.filter(d => d.deal_type === 'FLIP'),
  }));

  const countByType = computed(() => ({
    BRRRR: dealsByType.value.BRRRR.length,
    FLIP: dealsByType.value.FLIP.length,
  }));

  async function fetchBoughtDeals() {
    console.group('BoughtDealStore: fetchBoughtDeals');
    isLoading.value = true;
    try {
      boughtDeals.value = await api.getBoughtDeals();
      console.log('Bought deals loaded:', boughtDeals.value.length);
    } catch (err) {
      error.value = 'Failed to fetch bought deals';
      console.error('Store Error:', err);
    } finally {
      isLoading.value = false;
      console.groupEnd();
    }
  }

  async function analyze(data: AnalyzeDealReq, type: 'BRRRR' | 'FLIP'): Promise<AnalyzeDealRes | null> {
    try {
      return await api.analyzeDeal(data, type);
    } catch (err) {
      console.error('BoughtDealStore: analyze failed', err);
      return null;
    }
  }

  async function updateBoughtDeal(deal: BoughtDealRes) {
    console.group('BoughtDealStore: updateBoughtDeal');
    isLoading.value = true;
    try {
      const updatedDeal = await api.updateBoughtDeal(deal);
      const index = boughtDeals.value.findIndex(d => d.id === deal.id);
      if (index !== -1) {
        boughtDeals.value[index] = updatedDeal;
      }
      return updatedDeal;
    } catch (err) {
      error.value = 'Failed to update bought deal';
      console.error('Store Error:', err);
      throw err;
    } finally {
      isLoading.value = false;
      console.groupEnd();
    }
  }

  async function deleteBoughtDeal(dealId: string, type: 'BRRRR' | 'FLIP' = 'BRRRR') {
    console.group('BoughtDealStore: deleteBoughtDeal');
    isLoading.value = true;
    try {
      await api.deleteBoughtDeal(dealId, type);
      boughtDeals.value = boughtDeals.value.filter(d => d.id !== dealId);
      console.log('Bought deal removed from store');
    } catch (err) {
      error.value = 'Failed to delete bought deal';
      console.error('Store Error:', err);
      throw err;
    } finally {
      isLoading.value = false;
      console.groupEnd();
    }
  }

  async function moveToBought(dealId: string, dealType: 'BRRRR' | 'FLIP') {
    console.group('BoughtDealStore: moveToBought');
    isLoading.value = true;
    try {
      const newDeal = await api.moveToBought(dealId, dealType);
      boughtDeals.value.unshift(newDeal);
      console.log('Deal moved to bought:', newDeal);
      return newDeal;
    } catch (err) {
      error.value = 'Failed to move deal to bought';
      console.error('Store Error:', err);
      throw err;
    } finally {
      isLoading.value = false;
      console.groupEnd();
    }
  }

  async function toggleSubstage(dealId: string, substageId: string) {
    const deal = boughtDeals.value.find(d => d.id === dealId);
    if (!deal) return;

    const newCompleted = { ...deal.completedSubstages };
    if (newCompleted[substageId]) {
      delete newCompleted[substageId];
    } else {
      newCompleted[substageId] = true;
    }

    deal.completedSubstages = newCompleted;

    try {
      const payload = toRaw(deal);
      await api.updateBoughtDeal(payload);
    } catch (err) {
      // Revert on error
      if (newCompleted[substageId]) {
        delete newCompleted[substageId];
      } else {
        newCompleted[substageId] = true;
      }
      deal.completedSubstages = { ...newCompleted };
      console.error('Failed to toggle substage:', err);
    }
  }

  async function advanceStage(dealId: string) {
    const deal = boughtDeals.value.find(d => d.id === dealId);
    if (!deal) return;

    const dealType = deal.deal_type || 'BRRRR';
    const pipelineStore = usePipelineTemplateStore();
    const pipeline = pipelineStore.pipelineFor(dealType);

    if (!canAdvance(pipeline, deal.boughtStage, deal.completedSubstages)) {
      console.warn('Cannot advance: not all substages complete');
      return false;
    }

    const currentIdx = pipeline.stages.findIndex(s => s.id === deal.boughtStage);
    if (currentIdx === -1 || currentIdx >= pipeline.stages.length - 1) {
      console.warn('Already at terminal stage');
      return false;
    }

    const oldStage = deal.boughtStage;
    const oldSubstages = { ...deal.completedSubstages };
    const nextStage = pipeline.stages[currentIdx + 1];
    if (!nextStage) {
      console.warn('No next stage in pipeline');
      return false;
    }
    deal.boughtStage = nextStage.id;
    deal.completedSubstages = {};

    try {
      const payload = toRaw(deal);
      const updated = await api.updateBoughtDeal(payload);
      const index = boughtDeals.value.findIndex(d => d.id === dealId);
      if (index !== -1) boughtDeals.value[index] = updated;
      return true;
    } catch (err) {
      deal.boughtStage = oldStage;
      deal.completedSubstages = oldSubstages;
      console.error('Failed to advance stage:', err);
      return false;
    }
  }

  async function updateBoughtDealStage(dealId: string, newStageId: string) {
    const deal = boughtDeals.value.find(d => d.id === dealId);
    if (!deal) return;

    const oldStage = deal.boughtStage;
    const oldSubstages = { ...deal.completedSubstages };
    deal.boughtStage = newStageId;
    deal.completedSubstages = {};

    try {
      const payload = toRaw(deal);
      const updated = await api.updateBoughtDeal(payload);
      const index = boughtDeals.value.findIndex(d => d.id === dealId);
      if (index !== -1) boughtDeals.value[index] = updated;
    } catch (err) {
      deal.boughtStage = oldStage;
      deal.completedSubstages = oldSubstages;
      console.error('Failed to update bought deal stage:', err);
    }
  }

  return {
    boughtDeals,
    isLoading,
    error,
    dealsByType,
    countByType,
    fetchBoughtDeals,
    analyze,
    updateBoughtDeal,
    deleteBoughtDeal,
    moveToBought,
    toggleSubstage,
    advanceStage,
    updateBoughtDealStage,
  };
});
