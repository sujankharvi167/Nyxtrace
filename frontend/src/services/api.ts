import type {
  APIResponse,
  MLEvaluation,
  MLExplanation,
  MLReadiness,
  MLStatus,
  MLSummary,
  PaginatedPredictions,
  ProcessedDataset,
  GraphStatus,
  GraphStatistics,
  GraphNode,
  GraphNeighborhood,
  GraphPath,
  GraphFanResult,
  GraphCycles,
  GraphClusters,
  RiskReadiness,
  RiskAssessment,
  RiskAssessmentPage,
  InvestigationCase,
  InvestigationCasePage,
  ReportType,
  GeneratedReport,
  GeneratedReportPage,
} from '@/types';

const API_BASE = '/api';

export class APIError extends Error {
  constructor(message: string, public readonly status: number) {
    super(message);
    this.name = 'APIError';
  }
}

function errorMessage(body: unknown, fallback: string): string {
  if (!body || typeof body !== 'object') return fallback;
  const record = body as Record<string, unknown>;
  const detail = record.detail ?? record.message;
  if (typeof detail === 'string') return detail;
  if (detail !== undefined) return JSON.stringify(detail);
  return fallback;
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const url = `${API_BASE}${path}`;
  const headers = new Headers(options?.headers);
  if (options?.body instanceof FormData) {
    headers.delete('Content-Type');
  } else if (!headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }
  let response: Response;
  try {
    response = await fetch(url, {
      ...options,
      headers,
    });
  } catch (error) {
    throw new APIError(
      `Could not connect to the NyxTrace API. Confirm the backend is running on port 8001 and the Vite proxy is reachable. ${
        error instanceof Error ? error.message : ''
      }`.trim(),
      0,
    );
  }

  if (!response.ok) {
    let errorMsg = `HTTP ${response.status}${response.statusText ? ` ${response.statusText}` : ''}`;
    try {
      errorMsg = errorMessage(await response.json(), errorMsg);
    } catch {
      // The response body may not be JSON.
    }
    throw new APIError(errorMsg, response.status);
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
    getDataset: () => request<APIResponse<ProcessedDataset>>('/analysis/dataset'),
    uploadDataset: (
      files: File[],
      onProgress?: (percent: number) => void,
      onPhase?: (phase: 'uploading' | 'processing' | 'complete') => void,
      signal?: AbortSignal,
    ) =>
      new Promise<unknown>((resolve, reject) => {
        const formData = new FormData();
        files.forEach(file => formData.append('files', file));
        const xhr = new XMLHttpRequest();
        let settled = false;
        const cleanup = () => {
          signal?.removeEventListener('abort', abortUpload);
        };
        const finish = (callback: () => void) => {
          if (settled) return;
          settled = true;
          cleanup();
          callback();
        };
        const abortUpload = () => xhr.abort();

        if (signal?.aborted) {
          reject(new APIError('Upload cancelled before it started.', 0));
          return;
        }

        xhr.open('POST', `${API_BASE}/analysis/upload`);
        xhr.upload.onprogress = event => {
          if (event.lengthComputable && onProgress) {
            onProgress(Math.round((event.loaded / event.total) * 100));
          }
        };
        xhr.upload.onload = () => onPhase?.('processing');
        xhr.onload = () => {
          try {
            const body = JSON.parse(xhr.responseText);
            if (xhr.status >= 200 && xhr.status < 300) {
              onPhase?.('complete');
              finish(() => resolve(body));
            } else {
              const fallback = `HTTP ${xhr.status}${xhr.statusText ? ` ${xhr.statusText}` : ''}`;
              finish(() => reject(new APIError(errorMessage(body, fallback), xhr.status)));
            }
          } catch {
            finish(() => reject(new APIError(
              `The upload endpoint returned an unreadable response (HTTP ${xhr.status}).`,
              xhr.status,
            )));
          }
        };
        xhr.onerror = () => finish(() => reject(new APIError(
          'Could not reach the NyxTrace upload endpoint. Confirm the backend is running on port 8001 and the Vite proxy targets that port.',
          0,
        )));
        xhr.ontimeout = () => finish(() => reject(new APIError(
          'The upload timed out after two hours. Check backend logs and available disk space before retrying.',
          408,
        )));
        xhr.onabort = () => finish(() => reject(new APIError(
          'The upload was interrupted or cancelled. Check dataset status before retrying; incomplete uploads are not registered.',
          0,
        )));
        xhr.timeout = 2 * 60 * 60 * 1000;
        signal?.addEventListener('abort', abortUpload);
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
      sortBy?: string;
      sortOrder?: 'asc' | 'desc';
    }) => {
      const query = new URLSearchParams({
        page: String(params.page),
        page_size: String(params.pageSize),
        threshold: String(params.threshold),
      });
      if (params.search) query.set('search', params.search);
      if (params.sortBy) query.set('sort_by', params.sortBy);
      if (params.sortOrder) query.set('sort_order', params.sortOrder);
      const endpoint = params.suspiciousOnly ? '/ml/suspicious' : '/ml/predictions';
      return request<APIResponse<PaginatedPredictions>>(`${endpoint}?${query}`);
    },
    summary: (threshold: number) =>
      request<APIResponse<MLSummary>>(`/ml/summary?threshold=${threshold}`),
    explain: (transactionId: string) =>
      request<APIResponse<MLExplanation>>(
        `/ml/transactions/${encodeURIComponent(transactionId)}/explanation`,
      ),
  },
  graph: {
    status: () => request<APIResponse<GraphStatus>>('/graph/status'),
    build: () => request<APIResponse<unknown>>('/graph/build', { method: 'POST' }),
    statistics: () => request<APIResponse<GraphStatistics>>('/graph/statistics'),
    node: (transactionId: string) =>
      request<APIResponse<GraphNode>>(`/graph/transactions/${encodeURIComponent(transactionId)}`),
    neighborhood: (transactionId: string, depth = 2, limit = 100, direction: 'all' | 'upstream' | 'downstream' = 'all') =>
      request<APIResponse<GraphNeighborhood>>(
        `/graph/neighborhood/${encodeURIComponent(transactionId)}?depth=${depth}&limit=${limit}&direction=${direction}`,
      ),
    upstream: (transactionId: string, depth = 3, limit = 100) =>
      request<APIResponse<GraphNeighborhood>>(
        `/graph/traces/upstream/${encodeURIComponent(transactionId)}?depth=${depth}&limit=${limit}`,
      ),
    downstream: (transactionId: string, depth = 3, limit = 100) =>
      request<APIResponse<GraphNeighborhood>>(
        `/graph/traces/downstream/${encodeURIComponent(transactionId)}?depth=${depth}&limit=${limit}`,
      ),
    path: (source: string, destination: string, limit = 100) =>
      request<APIResponse<GraphPath>>(
        `/graph/path?source=${encodeURIComponent(source)}&destination=${encodeURIComponent(destination)}&limit=${limit}`,
      ),
    fanIn: (limit = 25) =>
      request<APIResponse<GraphFanResult>>(`/graph/patterns/fan-in?limit=${limit}`),
    fanOut: (limit = 25) =>
      request<APIResponse<GraphFanResult>>(`/graph/patterns/fan-out?limit=${limit}`),
    cycles: (limit = 25) =>
      request<APIResponse<GraphCycles>>(`/graph/patterns/cycles?limit=${limit}`),
    clusters: (limit = 25) =>
      request<APIResponse<GraphClusters>>(`/graph/patterns/clusters?limit=${limit}`),
  },
  risk: {
    readiness: () => request<APIResponse<RiskReadiness>>('/risk/readiness'),
    distribution: () => request<APIResponse<{ total_assessed: number; unassessed: number; distribution: Record<string, number> }>>('/risk/distribution'),
    assessments: (params: {
      page?: number;
      pageSize?: number;
      category?: string;
      search?: string;
      sortBy?: 'risk_score' | 'ml_probability' | 'transaction_id';
      sortOrder?: 'asc' | 'desc';
    } = {}) => {
      const query = new URLSearchParams({
        page: String(params.page ?? 1),
        page_size: String(params.pageSize ?? 25),
        sort_by: params.sortBy ?? 'risk_score',
        sort_order: params.sortOrder ?? 'desc',
      });
      if (params.category) query.set('category', params.category);
      if (params.search) query.set('search', params.search);
      return request<APIResponse<RiskAssessmentPage>>(`/risk/assessments?${query}`);
    },
    assess: (transactionId: string) =>
      request<APIResponse<RiskAssessment>>(`/risk/transactions/${encodeURIComponent(transactionId)}`),
    assessBulk: (transactionIds: string[]) =>
      request<APIResponse<{ assessed: RiskAssessment[]; errors: unknown[]; assessed_count: number }>>('/risk/assess/bulk', {
        method: 'POST',
        body: JSON.stringify({ transaction_ids: transactionIds }),
      }),
    cases: (params: { page?: number; pageSize?: number; status?: string; priority?: string } = {}) => {
      const query = new URLSearchParams({
        page: String(params.page ?? 1),
        page_size: String(params.pageSize ?? 25),
      });
      if (params.status) query.set('status', params.status);
      if (params.priority) query.set('priority', params.priority);
      return request<APIResponse<InvestigationCasePage>>(`/risk/cases?${query}`);
    },
    createCase: (body: {
      title: string;
      description?: string;
      priority: 'critical' | 'high' | 'medium' | 'low';
      status: 'open' | 'under_review' | 'escalated' | 'resolved' | 'closed';
      primary_transaction_id?: string;
      transaction_ids?: string[];
      risk_assessment_reference?: string;
    }) =>
      request<APIResponse<InvestigationCase>>('/risk/cases', {
        method: 'POST',
        body: JSON.stringify(body),
      }),
    case: (caseId: string) =>
      request<APIResponse<InvestigationCase>>(`/risk/cases/${encodeURIComponent(caseId)}`),
    updateCase: (caseId: string, body: {
      title?: string;
      description?: string;
      priority?: 'critical' | 'high' | 'medium' | 'low';
      status?: 'open' | 'under_review' | 'escalated' | 'resolved' | 'closed';
    }) =>
      request<APIResponse<InvestigationCase>>(`/risk/cases/${encodeURIComponent(caseId)}`, {
        method: 'PATCH',
        body: JSON.stringify(body),
      }),
    addCaseTransaction: (caseId: string, transactionId: string) =>
      request<APIResponse<InvestigationCase>>(`/risk/cases/${encodeURIComponent(caseId)}/transactions`, {
        method: 'POST',
        body: JSON.stringify({ transaction_id: transactionId }),
      }),
    removeCaseTransaction: (caseId: string, transactionId: string) =>
      request<APIResponse<InvestigationCase>>(`/risk/cases/${encodeURIComponent(caseId)}/transactions/${encodeURIComponent(transactionId)}`, {
        method: 'DELETE',
      }),
    addCaseNote: (caseId: string, content: string, author?: string) =>
      request<APIResponse<InvestigationCase>>(`/risk/cases/${encodeURIComponent(caseId)}/notes`, {
        method: 'POST',
        body: JSON.stringify({ content, author }),
      }),
  },
  reports: {
    types: () =>
      request<APIResponse<{ types: ReportType[] }>>('/reports/types'),
    list: (params: {
      page?: number;
      pageSize?: number;
      reportType?: string;
      investigationCaseId?: string;
    } = {}) => {
      const query = new URLSearchParams({
        page: String(params.page ?? 1),
        page_size: String(params.pageSize ?? 25),
      });
      if (params.reportType) query.set('report_type', params.reportType);
      if (params.investigationCaseId) query.set('investigation_case_id', params.investigationCaseId);
      return request<APIResponse<GeneratedReportPage>>(`/reports?${query}`);
    },
    generate: (body: {
      report_name: string;
      report_type: ReportType['type'];
      investigation_case_id?: string;
      transaction_ids?: string[];
    }) =>
      request<APIResponse<GeneratedReport>>('/reports/generate', {
        method: 'POST',
        body: JSON.stringify(body),
      }),
    metadata: (reportId: string) =>
      request<APIResponse<GeneratedReport>>(`/reports/${encodeURIComponent(reportId)}`),
    downloadUrl: (reportId: string) =>
      `${API_BASE}/reports/${encodeURIComponent(reportId)}/download`,
  },
};

export default api;
