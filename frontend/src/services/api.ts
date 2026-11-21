const API_BASE = '/api';

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const url = `${API_BASE}${path}`;
  const response = await fetch(url, {
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
    ...options,
  });

  if (!response.ok) {
    let errorMsg = `HTTP ${response.status}`;
    try {
      const err = await response.json();
      errorMsg = err.detail || err.message || errorMsg;
    } catch {
      // ignore
    }
    throw new Error(errorMsg);
  }

  return response.json() as Promise<T>;
}

export const api = {
  health: {
    check: () => request<unknown>('/health'),
  },
  analysis: {
    getStats: () => request<unknown>('/analysis/stats'),
    getStatus: () => request<unknown>('/analysis/status'),
  },
  reports: {
    list: () => request<unknown>('/reports'),
  },
};

export default api;
