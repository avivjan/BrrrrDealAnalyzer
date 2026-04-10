export interface SubStage {
  id: string;
  label: string;
}

export interface BoughtDealStage {
  id: number;
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
      id: 1,
      name: 'Purchase',
      subStages: [
        { id: 'purchase_agreement', label: 'Purchase Agreement' },
        { id: 'emd', label: 'EMD' },
      ],
    },
    {
      id: 2,
      name: 'Prepare for Closing',
      subStages: [
        { id: 'lender_approval', label: 'Lender Approval' },
        { id: 'insurance', label: 'Insurance' },
        { id: 'title_insurance', label: 'Title Insurance' },
        { id: 'title_approval', label: 'Title Approval (Ready to Close)' },
      ],
    },
    { id: 3, name: 'Closed', subStages: [] },
    { id: 4, name: 'Rehab', subStages: [] },
    {
      id: 5,
      name: 'Sell',
      subStages: [
        { id: 'decide_who_sells', label: 'Decide Who Sells It' },
        { id: 'pictures_ads', label: 'Pictures & Ads' },
      ],
    },
    { id: 6, name: 'Sold', subStages: [] },
  ],
};

export const brrrPipeline: BoughtDealPipeline = {
  dealType: 'BRRRR',
  stages: [
    {
      id: 1,
      name: 'Purchase',
      subStages: [
        { id: 'purchase_agreement', label: 'Purchase Agreement' },
        { id: 'emd', label: 'EMD' },
      ],
    },
    {
      id: 2,
      name: 'Prepare for Closing',
      subStages: [
        { id: 'lender_approval', label: 'Lender Approval' },
        { id: 'insurance', label: 'Insurance' },
        { id: 'title_insurance', label: 'Title Insurance' },
        { id: 'title_approval', label: 'Title Approval (Ready to Close)' },
      ],
    },
    { id: 3, name: 'Closed', subStages: [] },
    { id: 4, name: 'Rehab', subStages: [] },
    {
      id: 5,
      name: 'Rent',
      subStages: [
        { id: 'decide_who_rents', label: 'Decide Who Rents It' },
        { id: 'pictures_ads', label: 'Pictures & Ads' },
      ],
    },
    {
      id: 6,
      name: 'Prepare for Refi',
      subStages: [
        { id: 'choose_best_lender', label: 'Choose Best Lender' },
        { id: 'lender_approval_refi', label: 'Lender Approval' },
        { id: 'appraisal', label: 'Appraisal' },
        { id: 'decide_reserve', label: 'Decide on Reserve (Down/% /Max)' },
      ],
    },
    { id: 7, name: 'Refinanced', subStages: [] },
  ],
};

export function getPipelineForType(dealType: 'FLIP' | 'BRRRR'): BoughtDealPipeline {
  return dealType === 'FLIP' ? flipPipeline : brrrPipeline;
}

export function getStageConfig(dealType: 'FLIP' | 'BRRRR', stageId: number): BoughtDealStage {
  const pipeline = getPipelineForType(dealType);
  const stage = pipeline.stages.find(s => s.id === stageId);
  if (!stage) {
    console.warn(`[BoughtDealStages] Stage ${stageId} not found for ${dealType}, clamping to nearest valid stage`);
    // Clamp to last stage if beyond range, first if below
    if (stageId > pipeline.stages[pipeline.stages.length - 1].id) {
      return pipeline.stages[pipeline.stages.length - 1];
    }
    return pipeline.stages[0];
  }
  return stage;
}

export function getSubStagesForStage(dealType: 'FLIP' | 'BRRRR', stageId: number): SubStage[] {
  return getStageConfig(dealType, stageId).subStages;
}

export function canAdvance(dealType: 'FLIP' | 'BRRRR', stageId: number, completedSubstages: Record<string, boolean>): boolean {
  const subStages = getSubStagesForStage(dealType, stageId);
  if (subStages.length === 0) return true;
  return subStages.every(sub => completedSubstages[sub.id] === true);
}

export function isTerminalStage(dealType: 'FLIP' | 'BRRRR', stageId: number): boolean {
  const pipeline = getPipelineForType(dealType);
  return stageId === pipeline.stages[pipeline.stages.length - 1].id;
}

export function getMissingSubstages(dealType: 'FLIP' | 'BRRRR', stageId: number, completedSubstages: Record<string, boolean>): string[] {
  const subStages = getSubStagesForStage(dealType, stageId);
  return subStages.filter(sub => !completedSubstages[sub.id]).map(sub => sub.label);
}
