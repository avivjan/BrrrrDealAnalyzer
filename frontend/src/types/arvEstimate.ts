/** `POST /arv-estimate` — mirrors `BackEnd/ReqRes/common/arv_estimate_schemas.py`. All money is in plain dollars. */

export type ArvEstimateDealType = 'BRRRR' | 'FLIP';

export interface ArvEstimateReq {
  deal_type: ArvEstimateDealType;
  property_address: string;
  investor_situation_note: string;
  subject_square_feet?: number | null;
  subject_bedrooms?: number | null;
  subject_bathrooms?: number | null;
  purchase_price?: number | null;
  rehab_budget?: number | null;
}

export interface ArvComparableProperty {
  address: string;
  distance_from_subject_in_miles: number | null;
  listing_status: 'SOLD' | 'ACTIVE' | 'PENDING';
  sale_or_list_date: string | null;
  sale_or_list_price: number | null;
  bedrooms: number | null;
  bathrooms: number | null;
  square_feet: number | null;
  year_built: number | null;
  lot_size_square_feet: number | null;
  price_per_square_foot: number | null;
  days_on_market: number | null;
  renovation_condition: string;
  adjusted_value_for_subject: number | null;
  adjustment_explanation: string;
  weight_in_valuation: 'PRIMARY' | 'SUPPORTING' | 'EXCLUDED';
  source_url: string | null;
}

export interface ArvDiscardedComparable {
  address: string;
  reason_for_discarding: string;
}

export interface ArvSubjectPropertyAsFound {
  bedrooms: number | null;
  bathrooms: number | null;
  square_feet: number | null;
  year_built: number | null;
  lot_size_square_feet: number | null;
  property_style: string | null;
}

export interface ArvEstimateRes {
  estimated_arv_range_low: number;
  estimated_arv_range_high: number;
  target_arv: number;
  conservative_lowest_arv: number;
  confidence_score_1_to_10: number;
  average_days_on_market_of_sold_comparables: number | null;
  median_days_on_market_of_sold_comparables: number | null;
  market_pace_verdict: 'FAST' | 'NORMAL' | 'SLOW' | 'UNKNOWN';
  market_logic: string;
  subject_property_as_found: ArvSubjectPropertyAsFound;
  sold_comparables: ArvComparableProperty[];
  active_or_pending_comparables: ArvComparableProperty[];
  discarded_comparables: ArvDiscardedComparable[];
  data_caveats: string[];
  source_urls: string[];
}
