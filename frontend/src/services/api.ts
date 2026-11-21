import type {
  APIResponse,
  MLEvaluation,
  MLExplanation,
  MLReadiness,
  MLStatus,
  PaginatedPredictions,
} from '@/types';

const API_BASE = '/api';

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const url = `${API_BASE}${path}`;
  const headers = new Headers(options?.headers);
  if (options?.body instanceof FormData) {
    headers.delete('Content-Type');
  } else if (!headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }
  const response = await fetch(url, {
    headers,
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
    getDataset: () => request<unknown>('/analysis/dataset'),
    uploadDataset: (files: File[], onProgress?: (percent: number) => void) =>
      new Promise<unknown>((resolve, reject) => {
        const formData = new FormData();
        files.forEach(file => formData.append('files', file));
        const xhr = new XMLHttpRequest();
        xhr.open('POST', `${API_BASE}/analysis/upload`);
        xhr.upload.onprogress = event => {
          if (event.lengthComputable && onProgress) {
            onProgress(Math.round((event.loaded / event.total) * 100));
          }
        };
        xhr.onload = () => {
          try {
            const body = JSON.parse(xhr.responseText);
            if (xhr.status >= 200 && xhr.status < 300) resolve(body);
            else reject(new Error(body.detail || body.message || `HTTP ${xhr.status}`));
          } catch {
            reject(new Error(`HTTP ${xhr.status}`));
          }
        };
        xhr.onerror = () => reject(new Error('Network error while uploading the dataset.'));
        xhr.ontimeout = () => reject(new Error('Upload timed out. Check the server and available disk space.'));
        xhr.onabort = () => reject(new Error('Dataset upload was cancelled.'));
        xhr.timeout = 2 * 60 * 60 * 1000;
        xhr.send(formData);
      }),
  },
  ml: {
    readiness: () => request<APIResponse<MLReadiness>>('/ml/readiness'),
    status: () => request<APIResponse<MLStatus>>('/ml/status'),
    progress: () => request<APIResponse<MLStatus>>('/ml/progress'),
    train: (classificationThreshold: number) =>
      request<APIResponse<MLStatus>>('/ml/train', {
        method: 'POST',
        body: JSON.stringify({ classification_threshold: classificationThreshold }),
      }),
    evaluation: () => request<APIResponse<MLEvaluation>>('/ml/evaluation'),
    predictions: (params: {
      page: number;
      pageSize: number;
      threshold: number;
      search: string;
      suspiciousOnly?: boolean;
    }) => {
      const query = new URLSearchParams({
        page: String(params.page),
        page_size: String(params.pageSize),
        threshold: String(params.threshold),
      });
      if (params.search) query.set('search', params.search);
      const endpoint = params.suspiciousOnly ? '/ml/suspicious' : '/ml/predictions';
      return request<APIResponse<PaginatedPredictions>>(`${endpoint}?${query}`);
    },
    explain: (transactionId: string) =>
      request<APIResponse<MLExplanation>>(
        `/ml/transactions/${encodeURIComponent(transactionId)}/explanation`,
      ),
  },
  reports: {
    list: () => request<unknown>('/reports'),
  },
};

export default api;
