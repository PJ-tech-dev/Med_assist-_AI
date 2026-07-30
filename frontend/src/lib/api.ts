/**
 * Central API Client for MedAssist AI Backend & Multi-Agent Orchestrator
 */

export const getApiBaseUrl = (): string => {
  if (typeof window !== 'undefined') {
    const defaultUrl = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
      ? 'http://127.0.0.1:8000/api/v1' 
      : `http://${window.location.hostname}:8000/api/v1`;
    return localStorage.getItem('medassist_api_url') || defaultUrl;
  }
  return 'http://127.0.0.1:8000/api/v1';
};

export const getAiApiKey = (): string => {
  if (typeof window !== 'undefined') {
    return localStorage.getItem('medassist_ai_key') || '';
  }
  return '';
};

export const setAiApiKey = (key: string): void => {
  if (typeof window !== 'undefined') {
    localStorage.setItem('medassist_ai_key', key);
  }
};

export const getAuthToken = (): string | null => {
  if (typeof window !== 'undefined') {
    return localStorage.getItem('medassist_token');
  }
  return null;
};

export const setAuthToken = (token: string): void => {
  if (typeof window !== 'undefined') {
    localStorage.setItem('medassist_token', token);
  }
};

export const logout = (): void => {
  if (typeof window !== 'undefined') {
    localStorage.removeItem('medassist_token');
    window.location.href = '/login';
  }
};

/**
 * Ensures a valid JWT auth token exists by logging in/registering a default demo user if needed.
 */
export async function ensureAuth(): Promise<string> {
  const existingToken = getAuthToken();
  if (existingToken) return existingToken;

  const baseUrl = getApiBaseUrl();
  const credentials = {
    email: 'patient@medassist.ai',
    password: 'Password123!',
    full_name: 'Johnathan Doe',
  };

  try {
    // Try logging in
    let res = await fetch(`${baseUrl}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: credentials.email, password: credentials.password }),
    }).catch(() => null);

    if (res && !res.ok) {
      // Register if user does not exist
      res = await fetch(`${baseUrl}/auth/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(credentials),
      }).catch(() => null);
    }

    if (res && res.ok) {
      const data = await res.json();
      const token = data.access_token;
      if (token) {
        setAuthToken(token);
        return token;
      }
    }
  } catch (err) {
    console.warn('Backend authentication attempt failed:', err);
  }

  return '';
}

async function request<T>(endpoint: string, options: RequestInit = {}, isRetry: boolean = false): Promise<T> {
  let token = getAuthToken();
  if (!token) {
    token = await ensureAuth();
  }

  const baseUrl = getApiBaseUrl();
  const aiApiKey = getAiApiKey();

  const headers: Record<string, string> = {
    ...(options.headers as Record<string, string>),
  };

  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  if (aiApiKey) {
    headers['X-AI-API-Key'] = aiApiKey;
  }

  if (!(options.body instanceof FormData) && !headers['Content-Type']) {
    headers['Content-Type'] = 'application/json';
  }

  try {
    const response = await fetch(`${baseUrl}${endpoint}`, {
      ...options,
      headers,
    });

    if (!response.ok) {
      if (response.status === 401 && !isRetry) {
        if (typeof window !== 'undefined') {
          localStorage.removeItem('medassist_token');
        }
        // Retry the request once after clearing the token
        return request<T>(endpoint, options, true);
      }
      const errorBody = await response.text().catch(() => '');
      throw new Error(`API Error ${response.status}: ${errorBody || response.statusText}`);
    }

    if (response.status === 204) {
      return {} as T;
    }

    return await response.json();
  } catch (error: any) {
    if (error.name === 'TypeError' || error.message?.includes('Failed to fetch')) {
      console.warn(`Backend network fetch failed for ${endpoint}. FastAPI server offline.`);
      throw new Error(`FastAPI backend server offline at ${baseUrl}. Please start python main.py.`);
    }
    throw error;
  }
}

export const api = {
  // ── Health Check ─────────────────────────────────────────────────────────────
  async checkHealth(): Promise<{ status: string; app: string }> {
    try {
      const rootUrl = getApiBaseUrl().replace(/\/api\/v1\/?$/, '');
      const res = await fetch(`${rootUrl}/health`).catch(() => null);
      if (!res || !res.ok) return { status: 'offline', app: 'MedAssist AI' };
      return res.json();
    } catch {
      return { status: 'offline', app: 'MedAssist AI' };
    }
  },

  // ── Multi-Agent AI Chat ──────────────────────────────────────────────────────
  chat: {
    async sendMessage(payload: {
      message: string;
      session_id?: string;
      patient_profile_id?: string;
    }) {
      const rawRes = await request<any>('/chat', {
        method: 'POST',
        body: JSON.stringify(payload),
      });
      
      return {
        session_id: rawRes.session_id,
        response: rawRes.final_response,
        agent_name: rawRes.selected_agents?.[0] || 'Orchestrator',
        intent: rawRes.detected_intents?.[0] || 'General',
        confidence: rawRes.agent_outputs?.[0]?.confidence || 0,
        execution_time_ms: Math.round(rawRes.total_execution_ms || 0),
        agent_outputs: rawRes.agent_outputs || [],
      };
    },
  },

  // ── Patients & Medical Profiles ─────────────────────────────────────────────
  patients: {
    async list(params?: { search?: string; page?: number; page_size?: number }) {
      const q = new URLSearchParams();
      if (params?.search) q.append('search', params.search);
      if (params?.page) q.append('page', params.page.toString());
      if (params?.page_size) q.append('page_size', params.page_size.toString());
      return request<any>(`/patients?${q.toString()}`);
    },

    async create(data: any) {
      return request<any>('/patients', {
        method: 'POST',
        body: JSON.stringify(data),
      });
    },

    async getMedications(patientId: string) {
      return request<any>(`/patients/${patientId}/medications`);
    },

    async addMedication(patientId: string, data: any) {
      return request<any>(`/patients/${patientId}/medications`, {
        method: 'POST',
        body: JSON.stringify(data),
      });
    },

    async getVitals(patientId: string, params?: { page?: number; page_size?: number }) {
      const q = new URLSearchParams();
      if (params?.page) q.append('page', params.page.toString());
      if (params?.page_size) q.append('page_size', params.page_size.toString());
      return request<any>(`/patients/${patientId}/vitals?${q.toString()}`);
    },

    async addVitals(patientId: string, data: any) {
      return request<any>(`/patients/${patientId}/vitals`, {
        method: 'POST',
        body: JSON.stringify(data),
      });
    },

    async getHistory(patientId: string) {
      return request<any>(`/patients/${patientId}/history`);
    },

    async addHistory(patientId: string, data: any) {
      return request<any>(`/patients/${patientId}/history`, {
        method: 'POST',
        body: JSON.stringify(data),
      });
    },
  },

  // ── Medical Reports ──────────────────────────────────────────────────────────
  reports: {
    async list() {
      return request<any[]>('/reports');
    },

    async upload(file: File, patientId: string) {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('patient_id', patientId);

      return request<any>('/reports/upload', {
        method: 'POST',
        body: formData,
      });
    },

    async createFromLLM(payload: {
      file: File;
      patient_id: string;
      raw_text: string;
      summary: string;
      report_type?: string;
      extracted_values?: { name: string; value: string; range: string; status: string }[];
    }) {
      const formData = new FormData();
      formData.append('file', payload.file);
      formData.append('patient_id', payload.patient_id);
      formData.append('filename', payload.file.name);
      formData.append('raw_text', payload.raw_text);
      formData.append('summary', payload.summary);
      if (payload.report_type) formData.append('report_type', payload.report_type);
      formData.append('extracted_values', JSON.stringify(payload.extracted_values || []));

      return request<any>('/reports/create_from_llm', {
        method: 'POST',
        body: formData,
      });
    },

    async analyze(reportId: string) {
      return request<any>(`/reports/${reportId}/analyze`, {
        method: 'POST',
      });
    },

    async analyzeAll(patientId?: string) {
      const q = patientId ? `?patient_id=${patientId}` : '';
      return request<any>(`/reports/analyze-all${q}`, {
        method: 'POST',
      });
    },
  },

  // ── Automated Emergency WhatsApp Alerts ──────────────────────────────────────
  emergency: {
    async sendWhatsappAlert(payload: {
      phone: string;
      contact_name?: string;
      emergency_type: string;
      details: string;
      location?: string;
    }) {
      return request<any>('/emergency/whatsapp-alert', {
        method: 'POST',
        body: JSON.stringify(payload),
      });
    },

    async dispatchAmbulance(payload: {
      location: string;
      patient_id?: string;
      reason: string;
    }) {
      return request<any>('/emergency/ambulance', {
        method: 'POST',
        body: JSON.stringify(payload),
      });
    },
  },

  // ── Medicine Orders API ──────────────────────────────────────────────────────
  orders: {
    async create(payload: {
      patient_id?: string;
      pharmacy_name: string;
      pharmacy_address: string;
      medicines: { name: string; quantity?: number; price?: number }[];
      delivery_address: string;
      total_amount?: number;
    }) {
      return request<any>('/orders', {
        method: 'POST',
        body: JSON.stringify(payload),
      });
    },

    async list(patientId?: string) {
      const q = patientId ? `?patient_id=${patientId}` : '';
      return request<any[]>(`/orders${q}`);
    },

    async get(orderId: string) {
      return request<any>(`/orders/${orderId}`);
    },

    async updateStatus(orderId: string, status: string) {
      return request<any>(`/orders/${orderId}/status`, {
        method: 'PATCH',
        body: JSON.stringify({ status }),
      });
    },
  },

  // ── Gemini AI Map Fetching API ──────────────────────────────────────────────
  maps: {
    async fetchLocationData(payload: { lat: number; lng: number; query?: string }) {
      return request<any>('/maps/fetch', {
        method: 'POST',
        body: JSON.stringify(payload),
      });
    },
  },
};
