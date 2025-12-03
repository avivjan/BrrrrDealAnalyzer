export interface SoldComp {
  url: string;
  arv: number;
  how_long_ago: string;
}

export interface RentComp {
  url: string;
  rent: number;
  time_on_market: string;
}

// Fields for calculation (Analyze Deal) & Active Deal
// Using JSON keys (aliases) where applicable to match backend response/request
export interface AnalyzeDealReq {
  arv_in_thousands: number;
  purchasePrice: number; // alias for purchase_price_in_thousands
  rehabCost: number; // alias for rehab_cost_in_thousands
  down_payment: number; 
  closingCostsBuy: number; // alias for closing_costs_buy_in_thousands
  use_HM_for_rehab: boolean;
  hmlPoints: number; 
  monthsUntilRefi: number;
  HMLInterestRate: number; 
  closingCostsRefi: number; 
  loanTermYears: number; 
  ltv_as_precent: number; 
  interestRate: number; 
  rent: number;
  vacancyPercent: number; 
  property_managment_fee_precentages_from_rent: number;
  maintenancePercent: number; 
  capexPercent: number; 
  annual_property_taxes: number;
  annual_insurance: number;
  montly_hoa: number;
}

export interface AnalyzeDealRes {
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

export interface DealDetails {
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

export interface ActiveDealCreate extends AnalyzeDealReq, DealDetails {}

export interface ActiveDealRes extends ActiveDealCreate, AnalyzeDealRes {
  id: number;
  created_at: string;
  updated_at: string;
}
