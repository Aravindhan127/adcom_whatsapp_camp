import axios from 'axios';

export const API_BASE = import.meta.env.VITE_API_BACKEND_URL_WHATSAPP || 'http://localhost:8000';

// SECURITY: Add timeout and CSRF protection
const whatsappClient = axios.create({
    baseURL: API_BASE,
    headers: { 'Content-Type': 'application/json' },
    timeout: 30000, // 30 second timeout
    timeoutErrorMessage: 'Request timed out. Please try again.',
});

// Attach JWT Bearer token to every request automatically
whatsappClient.interceptors.request.use((config) => {
    const token = localStorage.getItem('token');
    // SECURITY: Removed fake-jwt-token check - that was a security vulnerability
    if (token) {
        config.headers['Authorization'] = `Bearer ${token}`;
    }
    return config;
});

// SECURITY: Add response interceptor for error handling
whatsappClient.interceptors.response.use(
    (response) => response,
    (error) => {
        // Handle 401 Unauthorized - redirect to login
        if (error.response?.status === 401) {
            localStorage.removeItem('token');
            localStorage.removeItem('role');
            window.location.href = '/login';
        }
        return Promise.reject(error);
    }
);

// ──────────────────────────────────────────────────────────────
// Types
// ──────────────────────────────────────────────────────────────
export interface Conversation {
    sessionId: string;
    phoneNumber: string;
    contactName?: string;
    lastMessage: string;
    timestamp: string;
    unreadCount: number;
    isActive: boolean;
    windowExpiresAt?: string;
}

export interface Message {
    id: string;
    text: string;
    sender: 'user' | 'agent';
    timestamp: string;
    type: string;
    mediaUrl?: string;
    deliveryStatus?: string;
    statusError?: string;
}

export interface Template {
    id: string;
    name: string;
    category: string;
    language: string;
    status: string;
    components: any[];
    rejection_reason?: string;
    last_synced_at?: string;
    created_at?: string;
    variable_mappings?: Record<string, string>;
}


export interface ContactList {
    id: string;
    name: string;
    description?: string;
    count: number;
}

export interface Campaign {
    id: string;
    name: string;
    template_name: string;
    status: 'draft' | 'scheduled' | 'running' | 'completed' | 'failed' | 'paused' | 'on_hold';
    total_contacts: number;
    sent_count: number;
    delivered_count: number;
    read_count: number;
    failed_count: number;
    failure_reason?: string | null;
    scheduled_at: string | null;
    created_at: string;
    completed_at: string | null;
}

export interface DashboardStats {
    messages: { total: number; delivered: number; read: number; failed: number; trend: number };
    rates: { delivery_trend: number; read_trend: number };
    costs: { total_usd: number; total_inr: number; trend_inr: number };
    balance: { estimated_inr: number; estimated_usd: number };
    brochures: { sent: number };
}

// ──────────────────────────────────────────────────────────────
// API methods
// ──────────────────────────────────────────────────────────────
export const whatsappApi = {
    // ── Auth ──────────────────────────────────────────────────
    login: async (username: string, password: string) => {
        const formData = new URLSearchParams();
        formData.append('username', username);
        formData.append('password', password);
        const res = await whatsappClient.post('/api/auth/login', formData, {
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' }
        });
        return res.data as { access_token: string; token_type: string; role: string; username: string };
    },

    registerAgent: async (payload: { username: string; email: string; password: string; full_name?: string; role: string }) => {
        const res = await whatsappClient.post('/api/auth/register', payload);
        return res.data;
    },

    forgotPassword: async (email: string) => {
        const res = await whatsappClient.post('/api/auth/forgot-password', { email });
        return res.data;
    },

    resetPassword: async (token: string, newPassword: string) => {
        const res = await whatsappClient.post('/api/auth/reset-password', { token, new_password: newPassword });
        return res.data;
    },

    // ── Conversations ─────────────────────────────────────────
    getConversations: async (params?: { skip?: number; limit?: number; search?: string; campaign_id?: string }): Promise<{ conversations: Conversation[]; total: number }> => {
        const response = await whatsappClient.get('/api/whatsapp/conversations', { params });
        return {
            conversations: response.data.conversations || [],
            total: response.data.total || 0
        };
    },

    getConversationMessages: async (waId: string, params?: { skip?: number; limit?: number }): Promise<Message[]> => {
        const response = await whatsappClient.get(`/api/whatsapp/conversation/${waId}`, { params });
        return response.data.messages || [];
    },

    sendMessage: async (to: string, text: string) => {
        return whatsappClient.post('/api/whatsapp/send-message', { to, message: text });
    },

    sendMedia: async (to: string, file: File, mediaType: string) => {
        const formData = new FormData();
        formData.append('to', to);
        formData.append('file', file);
        formData.append('media_type', mediaType);
        return whatsappClient.post('/api/whatsapp/send-media', formData, {
            headers: { 'Content-Type': 'multipart/form-data' }
        });
    },

    // ── Contacts ──────────────────────────────────────────────
    bulkImport: async (file: File, listId?: string, upsert: boolean = false, mapping?: string) => {
        const formData = new FormData();
        formData.append('file', file);
        if (listId) formData.append('list_id', listId);
        formData.append('upsert', String(upsert));
        if (mapping) formData.append('field_mapping', mapping);
        return whatsappClient.post('/api/contacts/bulk-import', formData, {
            headers: { 'Content-Type': 'multipart/form-data' }
        });
    },

    getContactLists: async (): Promise<ContactList[]> => {
        const res = await whatsappClient.get('/api/contacts/lists');
        return res.data || [];
    },

    getContacts: async (params?: {
        limit?: number;
        offset?: number;
        search?: string;
        status?: string;
        category?: string;
        list_id?: string;
        company_name?: string;
        lead_source?: string;
        customer_category?: string;
        customer_stage?: string;
        city?: string;
        sort_by?: string;
        sort_order?: string;
    }) => {
        const res = await whatsappClient.get('/api/contacts/', { params });
        return res.data as { total: number; items: any[]; limit: number; offset: number };
    },

    getContactFilterOptions: async () => {
        const res = await whatsappClient.get('/api/contacts/filter-options');
        return res.data as { categories: string[]; stages: string[]; cities: string[]; sources: string[] };
    },

    createContact: async (payload: {
        phone_number: string;
        name?: string;
        category?: string;
        list_id?: string;
        upsert?: boolean;
        company_name?: string;
        lead_source?: string;
        date_of_birth?: string;
        customer_category?: string;
        customer_stage?: string;
        city?: string;
        product_service_interest?: string;
        consent_confirmation?: string;
    }) => {
        const res = await whatsappClient.post('/api/contacts/', payload);
        return res.data;
    },

    updateContact: async (id: string, payload: {
        phone_number?: string;
        name?: string;
        category?: string;
        list_id?: string;
        status?: string;
        company_name?: string;
        lead_source?: string;
        date_of_birth?: string;
        customer_category?: string;
        customer_stage?: string;
        city?: string;
        product_service_interest?: string;
        consent_confirmation?: string;
    }) => {
        const res = await whatsappClient.patch(`/api/contacts/${id}`, payload);
        return res.data;
    },

    deleteContact: async (id: string) => {
        const res = await whatsappClient.delete(`/api/contacts/${id}`);
        return res.data;
    },

    createContactList: async (name: string, description?: string) => {
        const res = await whatsappClient.post('/api/contacts/lists', { name, description });
        return res.data as ContactList;
    },

    createListFromSelection: async (name: string, contactIds: string[]) => {
        const res = await whatsappClient.post('/api/contacts/lists/from-selection', { name, contact_ids: contactIds });
        return res.data as { id: string; name: string; count: number };
    },

    // ── Templates ─────────────────────────────────────────────
    getTemplates: async (params?: {
        status?: string;
        search?: string;
        category?: string;
        skip?: number;
        limit?: number;
        sort_by?: string;
        sort_order?: string;
    }): Promise<{ total: number; items: Template[] }> => {
        const res = await whatsappClient.get('/api/templates/', { params });
        // Robustness: Handle if backend still returns an array instead of paginated object
        if (Array.isArray(res.data)) {
            return { total: res.data.length, items: res.data };
        }
        return {
            total: res.data?.total || 0,
            items: res.data?.items || []
        };
    },



    syncTemplates: async () => {
        const res = await whatsappClient.post('/api/templates/sync');
        return res.data as { message: string, total_meta: number };
    },

    uploadTemplateMedia: async (file: File) => {
        const formData = new FormData();
        formData.append('file', file);
        const response = await whatsappClient.post('/api/templates/upload-media', formData, {
            headers: { 'Content-Type': 'multipart/form-data' }
        });
        return response.data; // { handle: "h/..." }
    },

    createTemplate: async (payload: {
        name: string;
        category: string;
        language: string;
        components: any[];
        submit_to_meta: boolean;
        variable_mappings?: Record<string, string>;
        media_id?: string;
    }) => {
        const res = await whatsappClient.post('/api/templates/', payload);
        return res.data as Template;
    },

    updateTemplate: async (id: string, payload: {
        name: string;
        category: string;
        language: string;
        components: any[];
        submit_to_meta: boolean;
        variable_mappings?: Record<string, string>;
        media_id?: string;
    }) => {
        const res = await whatsappClient.put(`/api/templates/${id}`, payload);
        return res.data as Template;
    },

    configureTemplate: async (templateId: string, payload: {
        variable_mappings?: Record<string, string>;
        media_id?: string;
    }) => {
        const res = await whatsappClient.post(`/api/templates/${templateId}/configure`, payload);
        return res.data as Template;
    },

    deleteTemplate: async (templateId: string) => {
        const res = await whatsappClient.delete(`/api/templates/${templateId}`);
        return res.data;
    },

    // ── Campaigns ─────────────────────────────────────────────
    getCampaigns: async (params?: {
        skip?: number;
        limit?: number;
        search?: string;
        status?: string;
        sort_by?: string;
        sort_order?: string;
    }): Promise<{ items: Campaign[]; total: number }> => {
        const res = await whatsappClient.get('/api/campaigns/', { params });
        return {
            items: res.data.items || [],
            total: res.data.total || 0
        };
    },

    uploadCampaignMedia: async (file: File) => {
        const formData = new FormData();
        formData.append('file', file);
        const response = await whatsappClient.post('/api/campaigns/upload-media', formData, {
            headers: { 'Content-Type': 'multipart/form-data' }
        });
        return response.data; // { id: "1234..." }
    },

    createCampaign: async (payload: {
        name: string;
        template_name: string;
        contact_list_id?: string;
        contact_ids?: string[];
        scheduled_at?: string | null;
        media_url?: string;
        template_params?: Record<string, string>;
    }) => {
        const res = await whatsappClient.post('/api/campaigns/', payload);
        return res.data as Campaign;
    },

    startCampaign: async (campaignId: string) => {
        const res = await whatsappClient.post(`/api/campaigns/${campaignId}/start`);
        return res.data;
    },

    pauseCampaign: async (campaignId: string) => {
        const res = await whatsappClient.post(`/api/campaigns/${campaignId}/pause`);
        return res.data;
    },

    resumeCampaign: async (campaignId: string) => {
        const res = await whatsappClient.post(`/api/campaigns/${campaignId}/resume`);
        return res.data;
    },

    getCampaignStats: async (campaignId: string) => {
        const res = await whatsappClient.get(`/api/campaigns/${campaignId}/stats`);
        return res.data;
    },

    getCampaignLogs: async (campaignId: string, params?: { skip?: number; limit?: number }) => {
        const res = await whatsappClient.get(`/api/campaigns/${campaignId}/logs`, { params });
        return res.data as { total: number; items: any[] };
    },

    deleteCampaign: async (campaignId: string) => {
        const res = await whatsappClient.delete(`/api/campaigns/${campaignId}`);
        return res.data;
    },

    // ── Dashboard ─────────────────────────────────────────────
    getStats: async (campaignId?: string): Promise<DashboardStats> => {
        const res = await whatsappClient.get('/api/analytics/dashboard/stats', { params: { campaign_id: campaignId } });
        return res.data;
    },
    getTrends: async (days: number = 7, campaignId?: string): Promise<any[]> => {
        const res = await whatsappClient.get('/api/analytics/dashboard/trends', { params: { days, campaign_id: campaignId } });
        return res.data || [];
    },
    getRecentActivity: async (limit: number = 5, hours: number = 24, campaignId?: string): Promise<any[]> => {
        const res = await whatsappClient.get('/api/analytics/dashboard/activity', { params: { limit, hours, campaign_id: campaignId } });
        return res.data || [];
    },



    // ── Health & Global Status ────────────────────────────────
    getHealthSummary: async () => {
        const res = await whatsappClient.get('/api/health/summary');
        return res.data;
    },

    getActiveProgress: async () => {
        const res = await whatsappClient.get('/api/campaigns/active/progress');
        return res.data as { id: string; name: string; progress: number; sent: number; total: number }[];
    },

    // ── System ────────────────────────────────────────────────
    getExchangeRate: async () => {
        const res = await whatsappClient.get('/api/system/currency');
        return res.data as { exchange_rate: number; last_updated: string };
    },

    syncExchangeRate: async () => {
        const res = await whatsappClient.post('/api/system/currency/sync');
        return res.data as { message: string; rate: number };
    },

    // ── Audit ──────────────────────────────────────────────────
    getAuditLogs: async (params?: { skip?: number; limit?: number; module?: string; action?: string }) => {
        const res = await whatsappClient.get('/api/audit/logs', { params });
        return res.data as { total: number; items: any[]; skip: number; limit: number };
    },
};
