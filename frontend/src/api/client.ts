import axios from 'axios'
import { clearAuth, getToken } from '../auth'

const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
})

api.interceptors.request.use((config) => {
  const token = getToken()
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

api.interceptors.response.use(
  (resp) => resp,
  (error) => {
    const msg = error.response?.data?.detail || error.message
    console.error('API Error:', msg)
    const url = String(error.config?.url || '')
    if (error.response?.status === 401 && !url.startsWith('/auth/')) {
      clearAuth()
      if (window.location.pathname !== '/login') {
        window.location.href = '/login'
      }
    }
    return Promise.reject(error)
  }
)

export default api

// Auth
export const authAPI = {
  login: (username: string, password: string) =>
    api.post('/auth/login', { username, password }),
  register: (username: string, password: string) =>
    api.post('/auth/register', { username, password }),
}

// Cookies
export const cookieAPI = {
  list: () => api.get('/cookies/'),
  create: (cookieJson: string, nickname?: string) =>
    api.post('/cookies/', { cookie_json: cookieJson, nickname }),
  delete: (id: number) => api.delete(`/cookies/${id}`),
}

// Tasks
export const taskAPI = {
  create: (profileUrl: string, cookieId: number, enableAi = false) =>
    api.post('/tasks/', { profile_url: profileUrl, cookie_id: cookieId, enable_ai_agent: enableAi }),
  list: () => api.get('/tasks/'),
  get: (id: number) => api.get(`/tasks/${id}`),
  cancel: (id: number) => api.post(`/tasks/${id}/cancel`),
  detailFetch: (id: number, maxCount = 25) =>
    api.post(`/tasks/${id}/detail-fetch`, { max_count: maxCount }),
  detailFetchStatus: (id: number) => api.get(`/tasks/${id}/detail-fetch`),
  competitorDiscover: (keyword: string, count: number, cookieId: number) =>
    api.post('/tasks/competitor-discover', { keyword, count, cookie_id: cookieId }),
}

// Reports
export const reportAPI = {
  list: (taskId: number) => api.get(`/reports/${taskId}`),
  get: (taskId: number, reportType: string) =>
    api.get(`/reports/${taskId}/${reportType}`),
  brief: (taskId: number) => api.get(`/reports/${taskId}/brief`),
  quality: (taskId: number) => api.get(`/reports/${taskId}/quality`),
  exportMarkdown: (taskId: number) =>
    api.get(`/reports/${taskId}/export`, { responseType: 'blob' }),
  exportShare: (taskId: number) =>
    api.get(`/reports/${taskId}/share`, { responseType: 'blob' }),
  compare: (taskIds: number[]) =>
    api.post('/reports/compare', { task_ids: taskIds }),
}

// Settings
export const settingsAPI = {
  getLlm: () => api.get('/settings/llm'),
  setLlm: (body: Record<string, string>) => api.post('/settings/llm', body),
}

// Anonymous product improvement
export const telemetryAPI = {
  preferences: () => api.get('/telemetry/preferences'),
  setConsent: (consent: 'granted' | 'denied') =>
    api.put('/telemetry/preferences', { consent }),
  event: (eventName: string, properties: Record<string, unknown> = {}) =>
    api.post('/telemetry/events', { event_name: eventName, properties }),
  diagnostic: (taskId: number) => api.get(`/telemetry/diagnostic/${taskId}`),
  diagnosticCopied: (taskId: number) => api.post(`/telemetry/diagnostic/${taskId}/copied`),
  feedback: (body: {
    task_id: number
    feedback_kind: 'report' | 'failure'
    rating: 'helpful' | 'not_helpful' | 'problem'
    reason?: string
    comment?: string
    reuse_intent?: string
  }) => api.post('/telemetry/feedback', body),
}

// AI
export const aiAPI = {
  deconstruct: (taskId: number) =>
    api.post('/ai/deconstruct', { task_id: taskId }),
  diagnose: (taskId: number, niche?: string) =>
    api.post('/ai/diagnose', { task_id: taskId, niche }),
  rewrite: (title: string, style: string) =>
    api.post('/ai/rewrite', { original_title: title, style }),
  compare: (taskIdA: number, taskIdB: number) =>
    api.post('/ai/compare', { task_id_a: taskIdA, task_id_b: taskIdB }),
}
