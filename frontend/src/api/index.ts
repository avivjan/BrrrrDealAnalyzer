import axios from 'axios';
import type { AnalyzeDealReq, AnalyzeDealRes, ActiveDealCreate, ActiveDealRes } from '../types';

const apiClient = axios.create({
  baseURL: 'https://brrrrdealanalyzer.onrender.com', 
  headers: {
    'Content-Type': 'application/json',
  },
});

export default {
  // Analyze Deal Calculator
  async analyzeDeal(data: AnalyzeDealReq): Promise<AnalyzeDealRes> {
    // Data keys now match the backend expectations (aliases)
    const response = await apiClient.post<AnalyzeDealRes>('/analyzeDeal', data);
    return response.data;
  },

  // Active Deals (My Deals)
  async getActiveDeals(): Promise<ActiveDealRes[]> {
    const response = await apiClient.get<ActiveDealRes[]>('/active-deals');
    return response.data;
  },

  async saveActiveDeal(deal: ActiveDealCreate): Promise<ActiveDealRes> {
    const response = await apiClient.post<ActiveDealRes>('/active-deals', deal);
    return response.data;
  },

  async updateActiveDeal(deal: ActiveDealRes): Promise<ActiveDealRes> {
    const response = await apiClient.put<ActiveDealRes>(`/active-deals/${deal.id}`, deal);
    return response.data;
  },

  async deleteActiveDeal(dealId: number): Promise<void> {
    await apiClient.delete(`/active-deals/${dealId}`);
  },

  async updateDealStage(dealId: number, stage: number): Promise<void> {
    // Stub for update logic
    console.warn('Update endpoint not implemented in backend yet. Would send:', { dealId, stage });
    // return apiClient.put(`/active-deals/${dealId}`, { stage });
  }
};
