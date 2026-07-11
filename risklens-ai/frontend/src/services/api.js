/**
 * RiskLens AI — API Service
 * Centralized Axios instance with interceptors.
 */

import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: `${API_BASE_URL}/api/v1`,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 30000,
});

// Request interceptor
api.interceptors.request.use(
  (config) => {
    // Add API key if configured
    const apiKey = import.meta.env.VITE_API_KEY;
    if (apiKey) {
      config.headers['X-API-Key'] = apiKey;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Response interceptor
api.interceptors.response.use(
  (response) => response.data,
  (error) => {
    const message = error.response?.data?.detail || error.message || 'An error occurred';
    console.error('API Error:', message);
    return Promise.reject(new Error(message));
  }
);

// --- Portfolio API ---
export const portfolioApi = {
  list: (params) => api.get('/portfolios', { params }),
  getById: (id) => api.get(`/portfolios/${id}`),
  upload: (formData) => api.post('/portfolios/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  }),
  delete: (id) => api.delete(`/portfolios/${id}`),
};

// --- Risk Analysis API ---
export const riskApi = {
  analyze: (portfolioId) => api.post(`/risk/analyze/${portfolioId}`),
  getAssessments: (portfolioId, params) => api.get(`/risk/assessments/${portfolioId}`, { params }),
  getLatest: (portfolioId) => api.get(`/risk/assessments/${portfolioId}/latest`),
};

// --- Alerts API ---
export const alertApi = {
  list: (params) => api.get('/alerts', { params }),
  getById: (id) => api.get(`/alerts/${id}`),
  acknowledge: (id, data) => api.patch(`/alerts/${id}/acknowledge`, data),
};

// --- Config API ---
export const configApi = {
  getLimits: (portfolioId) => api.get(`/config/risk-limits/${portfolioId}`),
  updateLimits: (portfolioId, data) => api.put(`/config/risk-limits/${portfolioId}`, data),
};

// --- Audit API ---
export const auditApi = {
  getLogs: (params) => api.get('/audit/logs', { params }),
};

// --- Health API ---
export const healthApi = {
  check: () => api.get('/health'),
};

export default api;
