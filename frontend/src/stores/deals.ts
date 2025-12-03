import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import type { AdditionalDetails, AnalyzeDealRequest, Deal, DealSection, DealStage } from '../types/deal';
import { analyzeDeal, createDeal, fetchDeals, updateDealStage } from '../services/api';

let dealId = 1;

export const useDealsStore = defineStore('deals', () => {
  const deals = ref<Deal[]>([]);
  const loading = ref(false);
  const error = ref<string | null>(null);

  const dealsBySection = computed(() => (section: DealSection) => deals.value.filter((deal) => deal.section === section));

  async function bootstrap() {
    loading.value = true;
    try {
      const remote = await fetchDeals();
      deals.value = remote.length ? remote : deals.value;
    } catch (err) {
      console.warn('Unable to fetch deals from API, falling back to local state.', err);
    } finally {
      loading.value = false;
    }
  }

  async function analyzeAndSave(base: AnalyzeDealRequest, extra: AdditionalDetails) {
    loading.value = true;
    error.value = null;
    try {
      const analysis = await analyzeDeal(base);
      const payload: Deal = {
        ...base,
        ...extra,
        id: dealId++,
        section: extra.section ?? 1,
        stage: extra.stage ?? 1,
        cash_flow: analysis.cash_flow,
        cash_out: analysis.cash_out ?? undefined,
        cash_on_cash: analysis.cash_on_cash ?? undefined,
        total_cash_needed_for_deal: analysis.total_cash_needed_for_deal ?? undefined,
        roi: analysis.roi ?? undefined
      };
      deals.value.push(payload);
      try {
        await createDeal({ ...base, ...extra });
      } catch (err) {
        console.warn('Local save succeeded, but remote save failed.', err);
      }
      return payload;
    } catch (err: any) {
      error.value = err?.response?.data?.detail ?? 'Unable to analyze the deal right now.';
      throw err;
    } finally {
      loading.value = false;
    }
  }

  async function updateStage(id: number, stage: DealStage) {
    const target = deals.value.find((deal) => deal.id === id);
    if (target) {
      target.stage = stage;
    }
    try {
      await updateDealStage(id, stage);
    } catch (err) {
      console.warn('Stage sync failed, keeping local change.', err);
    }
  }

  function updateDeal(id: number, patch: Partial<Deal>) {
    const idx = deals.value.findIndex((deal) => deal.id === id);
    if (idx !== -1) {
      deals.value[idx] = { ...deals.value[idx], ...patch };
    }
  }

  return { deals, loading, error, dealsBySection, bootstrap, analyzeAndSave, updateStage, updateDeal };
});
