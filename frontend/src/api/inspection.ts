import { apiClient } from "./index";
import type {
  InspectionCreateReq,
  InspectionDealLinkRes,
  InspectionItemRes,
  InspectionItemUpdateReq,
  InspectionListRowRes,
  InspectionPhotoRes,
  PublicInspectionRes,
} from "../types/inspection";

/**
 * Property inspections. `/public/inspections/...` needs no session (anyone
 * with the link); `/inspections/...` and `/bought-deals/.../inspections` are
 * behind the site's normal login.
 */
const publicInspectionPath = (inspectionId: string) => `/public/inspections/${encodeURIComponent(inspectionId)}`;

export const inspectionApi = {
  async createInspection(request: InspectionCreateReq): Promise<PublicInspectionRes> {
    return (await apiClient.post<PublicInspectionRes>("/public/inspections", request)).data;
  },

  async getInspection(inspectionId: string): Promise<PublicInspectionRes> {
    return (await apiClient.get<PublicInspectionRes>(publicInspectionPath(inspectionId))).data;
  },

  async updateInspectionStartInfo(inspectionId: string, request: Partial<InspectionCreateReq>): Promise<PublicInspectionRes> {
    return (await apiClient.patch<PublicInspectionRes>(publicInspectionPath(inspectionId), request)).data;
  },

  async updateInspectionItem(inspectionId: string, itemKey: string, request: InspectionItemUpdateReq): Promise<InspectionItemRes> {
    return (await apiClient.patch<InspectionItemRes>(`${publicInspectionPath(inspectionId)}/items/${encodeURIComponent(itemKey)}`, request)).data;
  },

  async completeInspection(inspectionId: string, completionOverrideReason: string | null): Promise<PublicInspectionRes> {
    const body = completionOverrideReason ? { completion_override_reason: completionOverrideReason } : {};
    return (await apiClient.post<PublicInspectionRes>(`${publicInspectionPath(inspectionId)}/complete`, body)).data;
  },

  async uploadInspectionPhoto(inspectionId: string, itemKey: string, fullImage: Blob, thumbnailImage: Blob): Promise<InspectionPhotoRes> {
    const formData = new FormData();
    formData.append("full_image", fullImage, "photo.jpg");
    formData.append("thumbnail_image", thumbnailImage, "thumbnail.jpg");
    const response = await apiClient.post<InspectionPhotoRes>(`${publicInspectionPath(inspectionId)}/items/${encodeURIComponent(itemKey)}/photos`, formData, {
      headers: { "Content-Type": "multipart/form-data" },
    });
    return response.data;
  },

  /** The photo as a Blob, shown through a `blob:` URL (the CSP's img-src does not name the API). */
  async getInspectionPhoto(inspectionId: string, photoId: string, size: "thumbnail" | "full"): Promise<Blob> {
    const response = await apiClient.get<Blob>(`${publicInspectionPath(inspectionId)}/photos/${encodeURIComponent(photoId)}/${size}`, { responseType: "blob" });
    return response.data;
  },

  async deleteInspectionPhoto(inspectionId: string, photoId: string): Promise<void> {
    await apiClient.delete(`${publicInspectionPath(inspectionId)}/photos/${encodeURIComponent(photoId)}`);
  },

  // --- logged in ---
  async listInspections(): Promise<InspectionListRowRes[]> {
    return (await apiClient.get<InspectionListRowRes[]>("/inspections")).data;
  },

  async deleteInspection(inspectionId: string): Promise<void> {
    await apiClient.delete(`/inspections/${encodeURIComponent(inspectionId)}`);
  },

  async getInspectionDealLink(inspectionId: string): Promise<InspectionDealLinkRes> {
    return (await apiClient.get<InspectionDealLinkRes>(`/inspections/${encodeURIComponent(inspectionId)}/deal-link`)).data;
  },

  async linkInspectionToDeal(inspectionId: string, boughtDealId: string, dealType: "BRRRR" | "FLIP"): Promise<InspectionDealLinkRes> {
    return (await apiClient.put<InspectionDealLinkRes>(`/inspections/${encodeURIComponent(inspectionId)}/deal-link`, { bought_deal_id: boughtDealId, deal_type: dealType })).data;
  },

  async unlinkInspectionFromDeal(inspectionId: string): Promise<InspectionDealLinkRes> {
    return (await apiClient.delete<InspectionDealLinkRes>(`/inspections/${encodeURIComponent(inspectionId)}/deal-link`)).data;
  },

  async listBoughtDealInspections(boughtDealId: string, dealType: "BRRRR" | "FLIP"): Promise<InspectionListRowRes[]> {
    return (await apiClient.get<InspectionListRowRes[]>(`/bought-deals/${encodeURIComponent(boughtDealId)}/inspections`, { params: { deal_type: dealType } })).data;
  },

  async createInspectionForBoughtDeal(boughtDealId: string, dealType: "BRRRR" | "FLIP"): Promise<PublicInspectionRes> {
    return (await apiClient.post<PublicInspectionRes>(`/bought-deals/${encodeURIComponent(boughtDealId)}/inspections`, {}, { params: { deal_type: dealType } })).data;
  },
};
