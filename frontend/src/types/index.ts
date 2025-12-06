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
  cash_on_cash?: number;
  roi?: number;
  equity?: number;
  net_profit?: number;
  total_cash_needed_for_deal?: number;
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
