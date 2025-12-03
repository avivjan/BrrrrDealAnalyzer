import axios from 'axios';
import type { AnalyzeDealRequest, AnalyzeDealResponse, Deal, AdditionalDetails, DealStage } from '../types/deal';

const api = axios.create({
  baseURL: 'https://brrrrdealanalyzer.onrender.com',
  timeout: 12000
});

export async function analyzeDeal(payload: AnalyzeDealRequest) {
  const res = await api.post<AnalyzeDealResponse>('/analyzeDeal', payload);
  return res.data;
}

export async function fetchDeals() {
  const res = await api.get<Deal[]>('/active-deals');
  return res.data;
}

export async function createDeal(payload: AdditionalDetails & AnalyzeDealRequest) {
  const res = await api.post<Deal>('/active-deals', payload);
  return res.data;
}

export async function updateDealStage(id: number, stage: DealStage) {
  return api.patch(`/active-deals/${id}`, { stage });
}
