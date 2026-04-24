/**
 * Bought-deal pipeline helpers.
 *
 * The pipeline template is persisted on the server (see `pipeline_templates`
 * table). These defaults are kept in the frontend only as a fallback for
 * first-render before the API resolves, and to seed new installs. IDs are
 * stable string identifiers – renaming or reordering never changes an id.
 */

export interface SubStage {
  id: string;
  label: string;
}

export interface BoughtDealStage {
  /** Stable string ID (slug for defaults, `stage_<uuid>` for user-added). */
  id: string;
  name: string;
  subStages: SubStage[];
}

export interface BoughtDealPipeline {
  dealType: 'FLIP' | 'BRRRR';
  stages: BoughtDealStage[];
}

export const flipPipeline: BoughtDealPipeline = {
  dealType: 'FLIP',
  stages: [
    {
      id: 'purchase',
      name: 'Purchase',
      subStages: [
        { id: 'purchase_agreement', label: 'Purchase Agreement' },
        { id: 'emd', label: 'EMD' },
      ],
    },
    {
      id: 'prepare_for_closing',
      name: 'Prepare for Closing',
      subStages: [
        { id: 'lender_approval', label: 'Lender Approval' },
        { id: 'insurance', label: 'Insurance' },
        { id: 'title_insurance', label: 'Title Insurance' },
        { id: 'title_approval', label: 'Title Approval (Ready to Close)' },
      ],
    },
    { id: 'closed', name: 'Closed', subStages: [] },
    { id: 'rehab', name: 'Rehab', subStages: [] },
    {
      id: 'sell',
      name: 'Sell',
      subStages: [
        { id: 'decide_who_sells', label: 'Decide Who Sells It' },
        { id: 'pictures_ads', label: 'Pictures & Ads' },
      ],
    },
    { id: 'sold', name: 'Sold', subStages: [] },
  ],
};

export const brrrPipeline: BoughtDealPipeline = {
  dealType: 'BRRRR',
  stages: [
    {
      id: 'purchase',
      name: 'Purchase',
      subStages: [
        { id: 'purchase_agreement', label: 'Purchase Agreement' },
        { id: 'emd', label: 'EMD' },
      ],
    },
    {
      id: 'prepare_for_closing',
      name: 'Prepare for Closing',
      subStages: [
        { id: 'lender_approval', label: 'Lender Approval' },
        { id: 'insurance', label: 'Insurance' },
        { id: 'title_insurance', label: 'Title Insurance' },
        { id: 'title_approval', label: 'Title Approval (Ready to Close)' },
        { id: 'understand_breakdown', label: 'Understand Breakdown' },
      ],
    },
    {
      id: 'closed',
      name: 'Closed',
      subStages: [{ id: 'save_package', label: 'Save Package' }],
    },
    { id: 'rehab', name: 'Rehab', subStages: [] },
    {
      id: 'rent',
      name: 'Rent',
      subStages: [
        { id: 'decide_who_rents', label: 'Decide Who Rents It' },
        { id: 'pictures_ads', label: 'Pictures & Ads' },
      ],
    },
    {
      id: 'prepare_for_refi',
      name: 'Prepare for Refi',
      subStages: [
        { id: 'choose_best_lender', label: 'Choose Best Lender' },
        { id: 'lender_approval_refi', label: 'Lender Approval' },
        { id: 'appraisal', label: 'Appraisal' },
        { id: 'decide_reserve', label: 'Decide on Reserve (Down/% /Max)' },
      ],
    },
    {
      id: 'refinanced',
      name: 'Refinanced',
      subStages: [{ id: 'save_package_refi', label: 'Save Package' }],
    },
  ],
};

export function getDefaultPipelineForType(
  dealType: 'FLIP' | 'BRRRR',
): BoughtDealPipeline {
  return dealType === 'FLIP' ? flipPipeline : brrrPipeline;
}

/**
 * Find a stage by ID within a pipeline. When the referenced stage has been
 * deleted from the template, clamp to the nearest position (first or last)
 * so the board never breaks. Never throws, never mutates the pipeline.
 */
export function resolveStage(
  pipeline: BoughtDealPipeline,
  stageId: string,
): BoughtDealStage {
  const stages = pipeline.stages;
  const first = stages[0];
  const last = stages[stages.length - 1];
  if (!first || !last) {
    // A pipeline with zero stages is invalid; fall back to the shipped default
    // so the UI can still render instead of crashing.
    const fallback = getDefaultPipelineForType(pipeline.dealType);
    return fallback.stages[0]!;
  }
  const stage = stages.find((s) => s.id === stageId);
  if (stage) return stage;
  console.warn(
    `[PipelineTemplate] Stage "${stageId}" not found for ${pipeline.dealType}; clamping to first stage.`,
  );
  return first;
}

export function getSubStagesForStage(
  pipeline: BoughtDealPipeline,
  stageId: string,
): SubStage[] {
  return resolveStage(pipeline, stageId).subStages;
}

/**
 * Can this deal advance? Only substages that still exist in the current
 * template are considered – orphan entries in `completedSubstages` left over
 * from deleted substages are ignored (never block advance, never crash).
 */
export function canAdvance(
  pipeline: BoughtDealPipeline,
  stageId: string,
  completedSubstages: Record<string, boolean>,
): boolean {
  const subStages = getSubStagesForStage(pipeline, stageId);
  if (subStages.length === 0) return true;
  return subStages.every((sub) => completedSubstages[sub.id] === true);
}

export function isTerminalStage(
  pipeline: BoughtDealPipeline,
  stageId: string,
): boolean {
  const stages = pipeline.stages;
  const last = stages[stages.length - 1];
  return last !== undefined && stageId === last.id;
}

export function getMissingSubstages(
  pipeline: BoughtDealPipeline,
  stageId: string,
  completedSubstages: Record<string, boolean>,
): string[] {
  const subStages = getSubStagesForStage(pipeline, stageId);
  return subStages
    .filter((sub) => !completedSubstages[sub.id])
    .map((sub) => sub.label);
}

export function getStageIndex(pipeline: BoughtDealPipeline, stageId: string): number {
  return pipeline.stages.findIndex((s) => s.id === stageId);
}

/** Generate a collision-resistant id for a new stage or substage. */
export function newStageId(): string {
  return `stage_${cryptoRandomId()}`;
}

export function newSubStageId(): string {
  return `sub_${cryptoRandomId()}`;
}

function cryptoRandomId(): string {
  const g: any = globalThis as any;
  if (g.crypto && typeof g.crypto.randomUUID === 'function') {
    return g.crypto.randomUUID();
  }
  return Math.random().toString(36).slice(2) + Date.now().toString(36);
}
