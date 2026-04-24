import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import api from '../api';
import type { PipelineStageDto, PipelineTemplateDto, PipelineTemplateStats } from '../types';
import {
  brrrPipeline,
  flipPipeline,
  type BoughtDealPipeline,
} from '../config/boughtDealStages';

/**
 * Store for editable bought-deal pipeline templates (one per deal type).
 *
 * Renders from in-memory defaults until the server response lands so the board
 * never blocks on the network. Every save goes through the API and the local
 * pipeline is replaced with whatever the server returns (authoritative).
 */
export const usePipelineTemplateStore = defineStore('pipelineTemplate', () => {
  const brrrStages = ref<PipelineStageDto[]>(
    brrrPipeline.stages.map((s) => ({ ...s, subStages: [...s.subStages] })),
  );
  const flipStages = ref<PipelineStageDto[]>(
    flipPipeline.stages.map((s) => ({ ...s, subStages: [...s.subStages] })),
  );

  const isLoading = ref(false);
  const isSaving = ref(false);
  const isLoaded = ref(false);
  const error = ref<string | null>(null);

  const brrrPipelineView = computed<BoughtDealPipeline>(() => ({
    dealType: 'BRRRR',
    stages: brrrStages.value,
  }));

  const flipPipelineView = computed<BoughtDealPipeline>(() => ({
    dealType: 'FLIP',
    stages: flipStages.value,
  }));

  function pipelineFor(dealType: 'BRRRR' | 'FLIP'): BoughtDealPipeline {
    return dealType === 'BRRRR' ? brrrPipelineView.value : flipPipelineView.value;
  }

  function _applyTemplate(tpl: PipelineTemplateDto) {
    const next = tpl.stages.map((s) => ({
      ...s,
      subStages: s.subStages.map((sub) => ({ ...sub })),
    }));
    if (tpl.dealType === 'BRRRR') {
      brrrStages.value = next;
    } else {
      flipStages.value = next;
    }
  }

  async function fetchTemplates() {
    isLoading.value = true;
    error.value = null;
    try {
      const rows = await api.getPipelineTemplates();
      for (const row of rows) _applyTemplate(row);
      isLoaded.value = true;
    } catch (err) {
      console.error('PipelineTemplateStore: fetchTemplates failed', err);
      error.value = 'Failed to load pipeline templates';
    } finally {
      isLoading.value = false;
    }
  }

  async function saveTemplate(
    dealType: 'BRRRR' | 'FLIP',
    stages: PipelineStageDto[],
  ): Promise<PipelineTemplateDto | null> {
    isSaving.value = true;
    error.value = null;
    try {
      const updated = await api.updatePipelineTemplate(dealType, stages);
      _applyTemplate(updated);
      return updated;
    } catch (err) {
      console.error('PipelineTemplateStore: saveTemplate failed', err);
      error.value = 'Failed to save pipeline template';
      throw err;
    } finally {
      isSaving.value = false;
    }
  }

  async function fetchStats(
    dealType: 'BRRRR' | 'FLIP',
  ): Promise<PipelineTemplateStats | null> {
    try {
      return await api.getPipelineTemplateStats(dealType);
    } catch (err) {
      console.error('PipelineTemplateStore: fetchStats failed', err);
      return null;
    }
  }

  return {
    brrrStages,
    flipStages,
    isLoading,
    isSaving,
    isLoaded,
    error,
    brrrPipelineView,
    flipPipelineView,
    pipelineFor,
    fetchTemplates,
    saveTemplate,
    fetchStats,
  };
});
