import axios from 'axios';
import type { AnalyzeDealReq, AnalyzeDealRes, ActiveDealCreate, ActiveDealRes } from '../types';

const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000', 
  headers: {
    'Content-Type': 'application/json',
  },
});

export default {
  // Analyze Deal Calculator
  async analyzeDeal(data: AnalyzeDealReq): Promise<AnalyzeDealRes> {
    console.group('API: analyzeDeal');
    console.log('Request Payload:', data);
    try {
      // Data keys now match the backend expectations (aliases)
      const response = await apiClient.post<AnalyzeDealRes>('/analyzeDeal', data);
      console.log('Response Status:', response.status);
      console.log('Response Data:', response.data);
      console.groupEnd();
      return response.data;
    } catch (error) {
      console.error('API Error:', error);
      console.groupEnd();
      throw error;
    }
  },

  // Active Deals (My Deals)
  async getActiveDeals(): Promise<ActiveDealRes[]> {
    console.group('API: getActiveDeals');
    console.log('Fetching active deals...');
    try {
      const response = await apiClient.get<ActiveDealRes[]>('/active-deals');
      console.log('Response Status:', response.status);
      console.log('Deals Fetched:', response.data.length);
      console.groupEnd();
      return response.data;
    } catch (error) {
      console.error('API Error:', error);
      console.groupEnd();
      throw error;
    }
  },

  async saveActiveDeal(deal: ActiveDealCreate): Promise<ActiveDealRes> {
    console.group('API: saveActiveDeal');
    console.log('Request Payload:', deal);
    try {
      const response = await apiClient.post<ActiveDealRes>('/active-deals', deal);
      console.log('Response Status:', response.status);
      console.log('Saved Deal:', response.data);
      console.groupEnd();
      return response.data;
    } catch (error) {
      console.error('API Error:', error);
      console.groupEnd();
      throw error;
    }
  },

  async updateActiveDeal(deal: ActiveDealRes): Promise<ActiveDealRes> {
    console.group('API: updateActiveDeal');
    console.log('Request Payload:', deal);
    try {
      const response = await apiClient.put<ActiveDealRes>(`/active-deals/${deal.id}`, deal);
      console.log('Response Status:', response.status);
      console.log('Updated Deal:', response.data);
      console.groupEnd();
      return response.data;
    } catch (error) {
      console.error('API Error:', error);
      console.groupEnd();
      throw error;
    }
  },

  async deleteActiveDeal(dealId: number): Promise<void> {
    console.group('API: deleteActiveDeal');
    console.log('Deal ID:', dealId);
    try {
      await apiClient.delete(`/active-deals/${dealId}`);
      console.log('Delete Successful');
      console.groupEnd();
    } catch (error) {
      console.error('API Error:', error);
      console.groupEnd();
      throw error;
    }
  },

  async duplicateActiveDeal(dealId: number): Promise<ActiveDealRes> {
    console.group('API: duplicateActiveDeal');
    console.log('Deal ID:', dealId);
    try {
      const response = await apiClient.post<ActiveDealRes>(`/active-deals/${dealId}/duplicate`);
      console.log('Response Status:', response.status);
      console.log('Duplicated Deal:', response.data);
      console.groupEnd();
      return response.data;
    } catch (error) {
      console.error('API Error:', error);
      console.groupEnd();
      throw error;
    }
  },

  async updateDealStage(dealId: number, stage: number): Promise<void> {
    console.group('API: updateDealStage');
    console.log('Deal ID:', dealId, 'New Stage:', stage);
    // Stub for update logic
    console.warn('Update endpoint not implemented in backend yet. Would send:', { dealId, stage });
    console.groupEnd();
    // return apiClient.put(`/active-deals/${dealId}`, { stage });
  }
};
