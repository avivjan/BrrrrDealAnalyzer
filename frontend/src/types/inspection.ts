import type { InspectionFieldValues, InspectionItemStatus } from "../inspection/inspectionChecklistLogic";

/** Mirrors `ReqRes/common/inspection_schemas.py`. Public shapes carry no deal data, only `linked`. */
export interface InspectionItemRes {
  item_key: string;
  item_status: InspectionItemStatus;
  item_notes: string | null;
  item_field_values: InspectionFieldValues;
  updated_at: string | null;
}

export interface InspectionPhotoRes {
  id: string;
  item_key: string;
  created_at: string | null;
}

export interface PublicInspectionRes {
  id: string;
  property_address: string;
  inspection_date: string;
  inspector_name: string | null;
  inspection_status: "draft" | "completed";
  completed_at: string | null;
  completion_override_reason: string | null;
  linked: boolean;
  created_at: string | null;
  updated_at: string | null;
  items: InspectionItemRes[];
  photos: InspectionPhotoRes[];
  /** The report of the last finish: e-mailed and saved to Drive, still sending, or retrying. Null before a finish. */
  report_delivery_status?: "sending" | "delivered" | "will_retry" | null;
}

export interface InspectionCreateReq {
  property_address: string;
  inspection_date?: string;
  inspector_name?: string | null;
}

export interface InspectionItemUpdateReq {
  item_status?: InspectionItemStatus;
  item_notes?: string;
  item_field_values?: Record<string, string | number | null>;
}

/** Which board a deal lives on: My Deals (the active pipeline) or Bought Deals. */
export type InspectionDealBoard = "my_deals" | "bought";

export interface LinkedDealRes {
  deal_id: string;
  deal_type: "BRRRR" | "FLIP";
  deal_board: InspectionDealBoard;
  property_address: string | null;
}

export interface InspectionDealLinkRes {
  linked_deal: LinkedDealRes | null;
}

export interface InspectionListRowRes {
  id: string;
  property_address: string;
  inspection_date: string;
  inspector_name: string | null;
  inspection_status: "draft" | "completed";
  completed_at: string | null;
  created_at: string | null;
  updated_at: string | null;
  checked_item_count: number;
  total_item_count: number;
  repair_or_replace_item_count: number;
  photo_count: number;
  linked_deal: LinkedDealRes | null;
}
