export type TransactionLabel = 'licit' | 'illicit' | 'unknown';
export type RiskLevel = 'critical' | 'high' | 'medium' | 'low' | 'unknown';

export interface PlatformStats {
  total_transactions_analyzed: number | null;
  suspicious_transactions_detected: number | null;
  accounts_flagged: number | null;
  active_investigations: number;
  last_analysis_at: string | null;
  platform_status: 'ready' | 'processing' | 'error';
}

export interface DatasetInfo {
  filename: string;
  total_rows: number;
  total_columns: number;
  columns: string[];
  missing_values: Record<string, number>;
  dtypes: Record<string, string>;
  file_size_bytes: number;
  uploaded_at: string;
}

export interface APIResponse<T = unknown> {
  success: boolean;
  message: string;
  data?: T;
}
