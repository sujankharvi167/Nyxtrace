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

export interface DatasetFileSummary {
  filename: string;
  role: 'features' | 'classes' | 'edgelist' | 'custom';
  original_rows: number;
  processed_rows: number;
  total_columns: number;
  duplicate_rows: number;
  missing_values: Record<string, number>;
  dtypes: Record<string, string>;
  columns: string[];
  column_info: Array<{
    name: string;
    dtype: string;
    missing: number;
    unique: number;
  }>;
  preview: Array<Record<string, unknown>>;
  detected_columns: Record<string, string>;
  validation_errors: string[];
}

export interface ProcessedDataset {
  batch_id: string;
  uploaded_at: string;
  status: string;
  message: string;
  total_transactions: number;
  total_edges: number;
  total_files: number;
  missing_values: number;
  duplicate_rows: number;
  label_counts: Record<TransactionLabel, number>;
  files: DatasetFileSummary[];
}

export interface MLReadiness {
  ready: boolean;
  message: string;
  batch_id?: string;
  total_transactions: number;
  label_counts: Record<TransactionLabel, number>;
  files?: {
    features: { name: string; size_bytes: number };
    classes: { name: string; size_bytes: number };
  };
}

export interface MLStatus {
  status: 'idle' | 'running' | 'completed' | 'error';
  progress: number;
  message: string;
  error?: string | null;
  best_model?: string;
  model_available?: boolean;
  predictions_available?: boolean;
  trained_records?: number;
  evaluated_records?: number;
  available_records?: number;
}

export interface MLConfusionMatrix {
  true_negative: number;
  false_positive: number;
  false_negative: number;
  true_positive: number;
}

export interface MLMetrics {
  accuracy: number;
  precision: number;
  recall: number;
  f1: number;
  roc_auc: number;
  pr_auc: number;
  confusion_matrix: MLConfusionMatrix;
  false_positive_rate: number;
  false_negative_rate: number;
  threshold: number;
  positive_class: string;
  train_records: number;
  test_records: number;
  test_class_distribution: Record<'licit' | 'illicit', number>;
}

export interface MLFeatureImportance {
  feature: string;
  importance: number;
  direction: number;
  method: string;
}

export interface MLEvaluation {
  best_model: string;
  selection_criterion: string;
  dataset: {
    batch_id: string;
    feature_rows: number;
    matched_feature_class_rows: number;
    available_supervised_records: number;
    available_class_distribution: Record<TransactionLabel, number>;
    sampling_applied: boolean;
    sampled_supervised_records: number;
    trained_records: number;
    evaluated_records: number;
    trained_class_distribution: Record<'licit' | 'illicit', number>;
    evaluated_class_distribution: Record<'licit' | 'illicit', number>;
    unknown_records_excluded_from_supervision: number;
    split_strategy: string;
    time_column: string | null;
    time_cutoff: number | null;
    random_seed: number;
    feature_count: number;
    feature_names: string[];
    dropped_features: Array<{ name: string; reason: string }>;
  };
  metrics: MLMetrics;
  models: Record<string, MLMetrics>;
  model_configuration: Record<string, Record<string, string | number>>;
  global_feature_importance: MLFeatureImportance[];
  explanation_method: string;
}

export interface MLPrediction {
  transaction_id: string;
  predicted_class: 'licit' | 'illicit';
  illicit_probability: number;
  confidence: number;
  selected_model: string;
  ground_truth_label: TransactionLabel | 'unlabeled';
}

export interface PaginatedPredictions {
  items: MLPrediction[];
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
  threshold: number;
  positive_class: string;
}

export interface MLExplanation {
  transaction_id: string;
  predicted_class: 'licit' | 'illicit';
  illicit_probability: number;
  confidence: number;
  ground_truth_label: TransactionLabel | 'unlabeled';
  model: string;
  method: string;
  features: Array<{
    feature: string;
    observed_value: number;
    training_median: number;
    probability_delta: number;
    global_importance: number;
  }>;
}
