import axios from 'axios';
import type { AnalyzeDealReq, AnalyzeDealRes, ActiveDealCreate, ActiveDealRes, LiquiditySettings } from '../types';

export const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000', 
  headers: {
    'Content-Type': 'application/json',
  },
});

export default {
  // Analyze Deal Calculator
  async analyzeDeal(data: AnalyzeDealReq, type: 'BRRRR' | 'FLIP'): Promise<AnalyzeDealRes> {
    const logPrefix = `[DealAnalyzer:${type}]`;
    console.group(`API: analyzeDeal (${type})`);
    console.log(`${logPrefix} Request Payload:`, data);
    try {
      const endpoint = type === 'BRRRR' ? '/analyze/brrr' : '/analyze/flip';
      const response = await apiClient.post<AnalyzeDealRes>(endpoint, data);
      console.log(`${logPrefix} Response Status:`, response.status);
      console.log(`${logPrefix} Response Data:`, response.data);
      console.groupEnd();
      return response.data;
    } catch (error) {
      console.error(`${logPrefix} API Error:`, error);
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
    const type = deal.deal_type || 'BRRRR';
    const logPrefix = `[DealAnalyzer:${type}]`;
    console.group(`API: saveActiveDeal (${type})`);
    console.log(`${logPrefix} Request Payload:`, deal);
    try {
      const response = await apiClient.post<ActiveDealRes>('/active-deals', deal);
      console.log(`${logPrefix} Response Status:`, response.status);
      console.log(`${logPrefix} Saved Deal:`, response.data);
      console.groupEnd();
      return response.data;
    } catch (error) {
      console.error(`${logPrefix} API Error:`, error);
      console.groupEnd();
      throw error;
    }
  },

  async updateActiveDeal(deal: ActiveDealRes): Promise<ActiveDealRes> {
    const type = deal.deal_type || 'BRRRR';
    const logPrefix = `[DealAnalyzer:${type}]`;
    console.group(`API: updateActiveDeal (${type})`);
    console.log(`${logPrefix} Request Payload:`, deal);
    try {
      const response = await apiClient.put<ActiveDealRes>(`/active-deals/${deal.id}`, deal);
      console.log(`${logPrefix} Response Status:`, response.status);
      console.log(`${logPrefix} Updated Deal:`, response.data);
      console.groupEnd();
      return response.data;
    } catch (error) {
      console.error(`${logPrefix} API Error:`, error);
      console.groupEnd();
      throw error;
    }
  },

  async deleteActiveDeal(dealId: string, type: 'BRRRR' | 'FLIP' = 'BRRRR'): Promise<void> {
    console.group('API: deleteActiveDeal');
    console.log('Deal ID:', dealId, 'Type:', type);
    try {
      await apiClient.delete(`/active-deals/${dealId}`, { params: { deal_type: type } });
      console.log('Delete Successful');
      console.groupEnd();
    } catch (error) {
      console.error('API Error:', error);
      console.groupEnd();
      throw error;
    }
  },

  async duplicateActiveDeal(dealId: string, type: 'BRRRR' | 'FLIP' = 'BRRRR'): Promise<ActiveDealRes> {
    console.group('API: duplicateActiveDeal');
    console.log('Deal ID:', dealId, 'Type:', type);
    try {
      const response = await apiClient.post<ActiveDealRes>(`/active-deals/${dealId}/duplicate`, null, { params: { deal_type: type } });
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

  async helloWorld(): Promise<{ message: string }> {
    try {
      const response = await apiClient.get<{ message: string }>('/helloworld');
      return response.data;
    } catch (error) {
      console.error('API Error:', error);
      throw error;
    }
  },

  async getLiquidity(): Promise<LiquiditySettings> {
    try {
      const response = await apiClient.get<LiquiditySettings>('/liquidity');
      return response.data;
    } catch (error) {
      console.error('API Error:', error);
      throw error;
    }
  },

  async updateLiquidity(settings: LiquiditySettings): Promise<LiquiditySettings> {
    try {
      const response = await apiClient.put<LiquiditySettings>('/liquidity', settings);
      return response.data;
    } catch (error) {
      console.error('API Error:', error);
      throw error;
    }
  }
};
