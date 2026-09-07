import axios from 'axios';
import { APP_KEY_DETAIL, APP_KEY_HEADER, appKeyRequired, readAppKey } from '../auth/appKey';
import type {
  AnalyzeDealReq,
  AnalyzeDealRes,
  ActiveDealCreate,
  ActiveDealRes,
  SendOfferReq,
  SendOfferRes,
  BoughtDealRes,
  PipelineTemplateDto,
  PipelineTemplateStats,
  PipelineStageDto,
} from '../types';
import type {
  RepsUser,
  RepsLogPayload,
  RepsLogRes,
  RepsEntriesEnvelope,
  RepsPropertyOption,
  RepsPerson,
  RepsConfigStatus,
  RepsActivityCategoryRes,
  RepsUploadBatchRes,
} from '../types/reps';

export const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000', 
  // Sessions are HttpOnly cookies (SECURITY_PLAN.md §3.2); the custom header
  // is one of the CSRF layers the API requires on unsafe methods.
  withCredentials: true,
  headers: {
    'Content-Type': 'application/json',
    'X-Requested-With': 'XMLHttpRequest',
  },
});

// A 401 from a data route means the access cookie expired: refresh once and
// retry; if the refresh fails too, the auth store sends the user to /login.
// The auth routes themselves are excluded so a failed login never loops.
let refreshing: Promise<boolean> | null = null;
apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const config = error?.config;
    const url: string = config?.url || '';
    if (error?.response?.status === 401 && config && !config.__retried && !url.startsWith('/auth/')) {
      const { useAuthStore } = await import('../stores/authStore');
      const auth = useAuthStore();
      if (auth.enforced) {
        refreshing = refreshing || auth.tryRefresh().finally(() => { refreshing = null; });
        const ok = await refreshing;
        if (ok) {
          config.__retried = true;
          return apiClient.request(config);
        }
        const { default: router } = await import('../router');
        if (router.currentRoute.value.name !== 'login') {
          router.push({ name: 'login', query: { next: router.currentRoute.value.fullPath } });
        }
      }
    }
    return Promise.reject(error);
  },
);

// Phase 0 stopgap (SECURITY_PLAN.md §4, step 0.2): the backend may require a
// shared key on every data route. The key is typed once by the user, kept in
// this browser only, and sent as `X-App-Key`. When the backend answers 401
// `app_key_required` the gate asks for it; nothing else about a request changes.
apiClient.interceptors.request.use((config) => {
  const key = readAppKey();
  if (key) config.headers.set(APP_KEY_HEADER, key);
  return config;
});
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error?.response?.status === 401 && error.response.data?.detail === APP_KEY_DETAIL) {
      appKeyRequired.value = true;
    }
    return Promise.reject(error);
  },
);

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

  async downloadDealPdf(
    data: AnalyzeDealReq,
    type: 'BRRRR' | 'FLIP',
    address: string,
  ): Promise<Blob> {
    const endpoint = type === 'FLIP' ? '/reports/flip-pdf' : '/reports/brrr-pdf';
    const logPrefix = `[DealReport:${type}]`;
    console.group(`API: downloadDealPdf (${type})`);
    try {
      const response = await apiClient.post(endpoint, data, {
        params: { address },
        responseType: 'blob',
      });
      console.log(`${logPrefix} Response Status:`, response.status);
      console.groupEnd();
      return response.data as Blob;
    } catch (error) {
      console.error(`${logPrefix} API Error:`, error);
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

  async sendOffer(data: SendOfferReq): Promise<SendOfferRes> {
    console.group('API: sendOffer');
    console.log('Request Payload:', data);
    try {
      const response = await apiClient.post<SendOfferRes>('/send-offer', data);
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

  // Bought Deals
  async getBoughtDeals(): Promise<BoughtDealRes[]> {
    console.group('API: getBoughtDeals');
    try {
      const response = await apiClient.get<BoughtDealRes[]>('/bought-deals');
      console.log('Response Status:', response.status);
      console.log('Bought Deals Fetched:', response.data.length);
      console.groupEnd();
      return response.data;
    } catch (error) {
      console.error('API Error:', error);
      console.groupEnd();
      throw error;
    }
  },

  async updateBoughtDeal(deal: BoughtDealRes): Promise<BoughtDealRes> {
    const type = deal.deal_type || 'BRRRR';
    const logPrefix = `[BoughtDeal:${type}]`;
    console.group(`API: updateBoughtDeal (${type})`);
    console.log(`${logPrefix} Request Payload:`, deal);
    try {
      const response = await apiClient.put<BoughtDealRes>(`/bought-deals/${deal.id}`, deal);
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

  async deleteBoughtDeal(dealId: string, type: 'BRRRR' | 'FLIP' = 'BRRRR'): Promise<void> {
    console.group('API: deleteBoughtDeal');
    console.log('Deal ID:', dealId, 'Type:', type);
    try {
      await apiClient.delete(`/bought-deals/${dealId}`, { params: { deal_type: type } });
      console.log('Delete Successful');
      console.groupEnd();
    } catch (error) {
      console.error('API Error:', error);
      console.groupEnd();
      throw error;
    }
  },

  async moveToBought(dealId: string, dealType: 'BRRRR' | 'FLIP'): Promise<BoughtDealRes> {
    console.group('API: moveToBought');
    console.log('Deal ID:', dealId, 'Type:', dealType);
    try {
      const response = await apiClient.post<BoughtDealRes>(`/bought-deals/from-active/${dealId}`, null, { params: { deal_type: dealType } });
      console.log('Response Status:', response.status);
      console.log('Created Bought Deal:', response.data);
      console.groupEnd();
      return response.data;
    } catch (error) {
      console.error('API Error:', error);
      console.groupEnd();
      throw error;
    }
  },

  // Pipeline Templates (bought-deal stages/substages per deal type)
  async getPipelineTemplates(): Promise<PipelineTemplateDto[]> {
    const response = await apiClient.get<PipelineTemplateDto[]>('/pipeline-templates');
    return response.data;
  },

  async updatePipelineTemplate(
    dealType: 'BRRRR' | 'FLIP',
    stages: PipelineStageDto[],
  ): Promise<PipelineTemplateDto> {
    const response = await apiClient.put<PipelineTemplateDto>(
      `/pipeline-templates/${dealType}`,
      { stages },
    );
    return response.data;
  },

  async getPipelineTemplateStats(
    dealType: 'BRRRR' | 'FLIP',
  ): Promise<PipelineTemplateStats> {
    const response = await apiClient.get<PipelineTemplateStats>(
      `/pipeline-templates/${dealType}/stats`,
    );
    return response.data;
  },

  // --- REPS Tracker --- //

  async getRepsConfigStatus(): Promise<RepsConfigStatus> {
    const response = await apiClient.get<RepsConfigStatus>('/reps/config-status');
    return response.data;
  },

  async logRepsEntry(payload: RepsLogPayload): Promise<RepsLogRes> {
    console.group('API: logRepsEntry');
    console.log('Payload:', payload);
    try {
      const response = await apiClient.post<RepsLogRes>('/reps/log', payload);
      console.log('Saved row range:', response.data.appended_range);
      console.groupEnd();
      return response.data;
    } catch (error) {
      console.error('API Error:', error);
      console.groupEnd();
      throw error;
    }
  },

  async getRepsEntries(user: RepsUser): Promise<RepsEntriesEnvelope> {
    const response = await apiClient.get<RepsEntriesEnvelope>('/reps/entries', {
      params: { user },
    });
    return response.data;
  },

  async uploadRepsEvidence(user: RepsUser, file: File): Promise<{ url: string; filename: string }> {
    const form = new FormData();
    form.append('user', user);
    form.append('file', file, file.name);
    const response = await apiClient.post<{ url: string; filename: string }>(
      '/reps/upload',
      form,
      { headers: { 'Content-Type': 'multipart/form-data' } },
    );
    return response.data;
  },

  async uploadRepsEvidenceBatch(args: {
    user: RepsUser;
    files: File[];
    propertyName?: string | null;
    activityCategory?: string | null;
    logTimestamp?: string | null;
  }): Promise<RepsUploadBatchRes> {
    const form = new FormData();
    form.append('user', args.user);
    if (args.propertyName) form.append('property_name', args.propertyName);
    if (args.activityCategory) form.append('activity_category', args.activityCategory);
    if (args.logTimestamp) form.append('log_timestamp', args.logTimestamp);
    for (const f of args.files) {
      form.append('files', f, f.name);
    }
    const response = await apiClient.post<RepsUploadBatchRes>(
      '/reps/upload-batch',
      form,
      { headers: { 'Content-Type': 'multipart/form-data' } },
    );
    return response.data;
  },

  async getRepsActivityCategories(): Promise<RepsActivityCategoryRes[]> {
    const response = await apiClient.get<RepsActivityCategoryRes[]>('/reps/activity-categories');
    return response.data;
  },

  async createRepsActivityCategory(name: string): Promise<RepsActivityCategoryRes> {
    const response = await apiClient.post<RepsActivityCategoryRes>(
      '/reps/activity-categories',
      { name },
    );
    return response.data;
  },

  async deleteRepsActivityCategory(id: string): Promise<void> {
    await apiClient.delete(`/reps/activity-categories/${id}`);
  },

  async getRepsProperties(): Promise<RepsPropertyOption[]> {
    const response = await apiClient.get<RepsPropertyOption[]>('/reps/properties');
    return response.data;
  },

  async createRepsProspect(name: string): Promise<RepsPropertyOption> {
    const response = await apiClient.post<RepsPropertyOption>('/reps/properties', { name });
    return response.data;
  },

  async getRepsPeople(): Promise<RepsPerson[]> {
    const response = await apiClient.get<RepsPerson[]>('/reps/people');
    return response.data;
  },

  async createRepsPerson(payload: { name: string; role?: string; notes?: string }): Promise<RepsPerson> {
    const response = await apiClient.post<RepsPerson>('/reps/people', payload);
    return response.data;
  },

  async updateRepsPerson(id: string, payload: { name?: string; role?: string; notes?: string }): Promise<RepsPerson> {
    const response = await apiClient.put<RepsPerson>(`/reps/people/${id}`, payload);
    return response.data;
  },

  async deleteRepsPerson(id: string): Promise<void> {
    await apiClient.delete(`/reps/people/${id}`);
  },
};
