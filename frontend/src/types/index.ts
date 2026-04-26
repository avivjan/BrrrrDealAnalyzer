export interface SoldComp {
  url?: string;
  arv?: number;
  how_long_ago?: string;
}

export interface RentComp {
  url?: string;
  rent?: number;
  time_on_market?: string;
}

// Base Interface for Shared Fields
export interface BaseDealReq {
  // Shared
  purchasePrice?: number;
  rehabCost?: number;
  rehabContingency?: number;
  down_payment?: number; 
  closingCostsBuy?: number;
  use_HM_for_rehab?: boolean;
  hmlPoints?: number; 
  HMLInterestRate?: number; 
  
  annual_property_taxes?: number;
  annual_insurance?: number;
  montly_hoa?: number;

  section: number; 
  stage: number; 
  address: string;
  sqft?: number;
  bedrooms?: number;
  bathrooms?: number;
  zillow_link?: string;
  overall_design?: string;
  crime_rate?: string;
  pics_link?: string;
  contact?: string;
  task?: string;
  niche?: string;
  sold_comps?: SoldComp[];
  rent_comps?: RentComp[];
  notes?: string;
}

// BRRRR Specific
export interface BrrrAnalyzeReq {
  arv_in_thousands: number;
  monthsUntilRefi: number;
  closingCostsRefi: number;
  /** % of refi loan amount; omit on request to use server default (1.5). */
  refiPoints?: number;
  loanTermYears: number; 
  ltv_as_precent: number; 
  interestRate: number; 
  rent: number;
  vacancyPercent: number; 
  property_managment_fee_precentages_from_rent: number;
  maintenancePercent: number; 
  capexPercent: number;
}

export interface BrrrAnalyzeRes {
  cash_flow: number;
  dscr?: number;
  cash_out?: number;
  cash_out_routi?: number;
  cash_on_cash?: number;
  roi?: number;
  equity?: number;
  net_profit?: number;
  total_cash_needed_for_deal?: number;
  total_cash_needed_for_deal_with_buffer?: number;
  messages?: string[];
}

export interface BrrrDealCreate extends BaseDealReq, Partial<BrrrAnalyzeReq> {
  deal_type: 'BRRRR';
}

export interface BrrrDealRes extends BrrrDealCreate, BrrrAnalyzeRes {
  id: string; // UUID
  created_at: string;
  updated_at: string;
}


// Flip Specific
export interface FlipAnalyzeReq {
  salePrice: number; // ARV
  holdingTime: number;
  buyerAgentSellingFee: number;
  sellerAgentSellingFee: number;
  sellingClosingCosts: number; // in thousands
  capitalGainsTax: number;
  monthly_utilities?: number;
}

export interface FlipAnalyzeRes {
  net_profit: number;
  roi: number;
  annualized_roi: number;
  total_cash_needed: number;
  total_cash_needed_with_buffer: number;
  total_holding_costs: number;
  total_hml_interest: number;
  messages?: string[];
}

export interface FlipDealCreate extends BaseDealReq, Partial<FlipAnalyzeReq> {
  deal_type: 'FLIP';
  sale_comps?: SoldComp[];
}

export interface FlipDealRes extends FlipDealCreate, FlipAnalyzeRes {
  id: string; // UUID
  created_at: string;
  updated_at: string;
}


// Unions
export type ActiveDealCreate = BrrrDealCreate | FlipDealCreate;
export type ActiveDealRes = BrrrDealRes | FlipDealRes;
export type AnalyzeDealReq = (BrrrAnalyzeReq & Partial<BaseDealReq>) | (FlipAnalyzeReq & Partial<BaseDealReq>); // Simplified for analyze API
export type AnalyzeDealRes = BrrrAnalyzeRes | FlipAnalyzeRes;

// Bought Deals
export interface BoughtBrrrDealRes extends BrrrDealRes {
  /** Stable pipeline stage id (slug or `stage_<uuid>`). */
  boughtStage: string;
  completedSubstages: Record<string, boolean>;
  sourceDealId?: string;
}

export interface BoughtFlipDealRes extends FlipDealRes {
  /** Stable pipeline stage id (slug or `stage_<uuid>`). */
  boughtStage: string;
  completedSubstages: Record<string, boolean>;
  sourceDealId?: string;
}

export type BoughtDealRes = BoughtBrrrDealRes | BoughtFlipDealRes;

// Pipeline templates (editable per deal type)
export interface PipelineSubStageDto {
  id: string;
  label: string;
}

export interface PipelineStageDto {
  id: string;
  name: string;
  subStages: PipelineSubStageDto[];
}

export interface PipelineTemplateDto {
  dealType: 'BRRRR' | 'FLIP';
  stages: PipelineStageDto[];
  updated_at?: string | null;
}

export interface PipelineSubstageStat {
  substageId: string;
  dealsWithCompletion: number;
}

export interface PipelineStageStat {
  stageId: string;
  dealCount: number;
  substages: PipelineSubstageStat[];
}

export interface PipelineTemplateStats {
  dealType: 'BRRRR' | 'FLIP';
  stages: PipelineStageStat[];
  orphanStageDealCount: number;
}

export interface SendOfferReq {
  agent_name: string;
  agent_email: string;
  property_address: string;
  purchase_price: number;
  inspection_period_days: number;
}

export interface SendOfferRes {
  message: string;
  success: boolean;
}
