export type DealSection = 1 | 2 | 3;
export type DealStage = 1 | 2 | 3 | 4 | 5;

export interface AnalyzeDealRequest {
  arv_in_thousands: number;
  purchasePrice: number;
  rehabCost?: number;
  down_payment: number;
  closingCostsBuy?: number;
  use_HM_for_rehab?: boolean;
  hmlPoints?: number;
  monthsUntilRefi: number;
  HMLInterestRate: number;
  closingCostsRefi?: number;
  loanTermYears?: number;
  ltv_as_precent: number;
  interestRate: number;
  rent: number;
  vacancyPercent?: number;
  property_managment_fee_precentages_from_rent?: number;
  maintenancePercent?: number;
  capexPercent?: number;
  annual_property_taxes?: number;
  annual_insurance?: number;
  montly_hoa?: number;
}

export interface AnalyzeDealResponse {
  cash_flow: number;
  dscr?: number | null;
  cash_out?: number | null;
  cash_on_cash?: number | null;
  roi?: number | null;
  equity?: number | null;
  net_profit?: number | null;
  total_cash_needed_for_deal?: number | null;
  messages?: string[] | null;
}

export interface AdditionalDetails {
  section?: DealSection;
  stage?: DealStage;
  address?: string;
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

export interface Deal extends AnalyzeDealRequest, AdditionalDetails {
  id: number;
  arv_in_thousands: number;
  purchasePrice: number;
  rehabCost?: number;
  down_payment: number;
  closingCostsBuy?: number;
  use_HM_for_rehab?: boolean;
  hmlPoints?: number;
  monthsUntilRefi: number;
  HMLInterestRate: number;
  closingCostsRefi?: number;
  loanTermYears?: number;
  ltv_as_precent: number;
  interestRate: number;
  rent: number;
  vacancyPercent?: number;
  property_managment_fee_precentages_from_rent?: number;
  maintenancePercent?: number;
  capexPercent?: number;
  annual_property_taxes?: number;
  annual_insurance?: number;
  montly_hoa?: number;
  cash_flow?: number;
  cash_out?: number;
  cash_on_cash?: number;
  total_cash_needed_for_deal?: number;
  roi?: number;
}

export const sectionLabels: Record<DealSection, string> = {
  1: 'Wholesale',
  2: 'Market',
  3: 'Our Off Market'
};

export const stageLabels: Record<DealStage, string> = {
  1: 'New',
  2: 'Working',
  3: 'Brought',
  4: 'Keep in Mind',
  5: 'Dead'
};

export const stageColors: Record<DealStage, string> = {
  1: 'from-sky-500/30 via-sky-700/50 to-sky-900/60',
  2: 'from-amber-500/30 via-amber-600/40 to-amber-800/50',
  3: 'from-emerald-500/30 via-emerald-600/40 to-emerald-800/50',
  4: 'from-purple-500/30 via-purple-600/40 to-purple-800/50',
  5: 'from-slate-500/30 via-slate-600/40 to-slate-800/50'
};
