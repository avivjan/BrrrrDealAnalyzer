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

export interface LinkedBoughtDealRes {
  bought_deal_id: string;
  deal_type: "BRRRR" | "FLIP";
  property_address: string | null;
}

export interface InspectionDealLinkRes {
  linked_deal: LinkedBoughtDealRes | null;
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
  linked_deal: LinkedBoughtDealRes | null;
}
