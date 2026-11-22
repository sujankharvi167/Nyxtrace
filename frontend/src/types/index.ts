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
  status: 'idle' | 'running' | 'completed' | 'stale' | 'error';
  progress: number;
  message: string;
  error?: string | null;
  dataset_stale?: boolean;
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
  recall: number | null;
  f1: number;
  roc_auc: number | null;
  pr_auc: number | null;
  confusion_matrix: MLConfusionMatrix;
  false_positive_rate: number | null;
  false_negative_rate: number | null;
  threshold: number;
  positive_class: string;
  unavailable_metric_reason?: string | null;
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

export interface MLSummary {
  batch_id: string;
  total_transactions: number;
  label_counts: Record<TransactionLabel, number>;
  ground_truth_distribution: Record<TransactionLabel | 'unlabeled', number>;
  total_predictions: number;
  prediction_distribution: Record<'licit' | 'illicit', number>;
  suspicious_count: number;
  suspicious_rate: number;
  threshold: number;
  best_model: string;
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

export interface GraphStatus {
  status: 'idle' | 'running' | 'ready' | 'stale' | 'error';
  progress: number;
  message: string;
  error?: string | null;
  graph_ready?: boolean;
  dataset_available: boolean;
  dataset_stale: boolean;
  ml_predictions_available?: boolean;
  dataset_batch?: string;
  ml_batch?: string;
  nodes?: number;
  edges?: number;
}

export interface GraphStatistics {
  nodes: number;
  edges: number;
  connected_components: number;
  average_degree: number;
  isolated_transactions: number;
  density: number | null;
  ml_flagged_transactions: number;
}

export interface GraphNode {
  transaction_id: string;
  predicted_class: 'licit' | 'illicit' | null;
  illicit_probability: number | null;
  confidence: number | null;
  ground_truth_label: TransactionLabel;
  selected_model?: string | null;
  incoming_count?: number;
  outgoing_count?: number;
  incoming_transaction_ids?: string[];
  outgoing_transaction_ids?: string[];
}

export interface GraphNeighborhood {
  transaction_id: string;
  direction: 'all' | 'upstream' | 'downstream';
  depth: number;
  nodes: GraphNode[];
  edges: Array<{ source: string; target: string }>;
}

export interface GraphPath {
  source: string;
  destination: string;
  path_found: boolean;
  transaction_ids: string[];
  hops: number | null;
  ml_flagged_transaction_ids: string[];
  nodes?: GraphNode[];
}

export interface GraphFanResult {
  items: Array<GraphNode & {
    incoming_count?: number;
    outgoing_count?: number;
    related_transaction_ids: string[];
  }>;
  total: number;
}

export interface GraphCycle {
  cycle: string[];
  cycle_length: number;
  related_transaction_ids: string[];
  ml_flagged: boolean;
  ml_flagged_transaction_ids: string[];
}

export interface GraphCycles {
  items: GraphCycle[];
  total: number;
  limited: boolean;
}

export interface GraphCluster {
  cluster_id: string;
  transaction_count: number;
  flagged_count: number;
  highest_illicit_probability: number | null;
  relevant_transaction_ids: string[];
  ml_flagged_transaction_ids: string[];
}

export interface GraphClusters {
  items: GraphCluster[];
  total: number;
}

export interface RiskReadiness {
  ready: boolean;
  compatible: boolean;
  dataset_batch: string | null;
  model_batch: string | null;
  prediction_batch: string | null;
  graph_batch: string | null;
  scoring_version: string;
  message: string;
  weights: Record<string, number>;
  thresholds: Record<string, number[]>;
}

export interface RiskAssessment {
  transaction_id: string;
  dataset_batch: string;
  model_batch: string;
  prediction_batch: string;
  graph_batch: string;
  ml_prediction: 'licit' | 'illicit';
  ml_probability: number;
  ml_confidence: number;
  combined_risk_score: number;
  risk_category: 'critical' | 'high' | 'medium' | 'low';
  evidence_availability: Record<string, boolean>;
  contributing_factors: string[];
  graph_findings: {
    incoming_count: number;
    outgoing_count: number;
    fan_in: boolean;
    fan_out: boolean;
    suspicious_neighbor_count: number;
    cluster_member: boolean;
  };
  explanation: {
    summary: string;
    method: string;
    ml_prediction: Record<string, unknown>;
    graph_findings: Record<string, unknown>;
    missing_evidence: string[];
  };
  assessment_timestamp: string;
  assessment_version: string;
  status: string;
}

export interface RiskAssessmentPage {
  items: RiskAssessment[];
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
}

export interface InvestigationCase {
  case_id: string;
  title: string;
  description: string;
  priority: 'critical' | 'high' | 'medium' | 'low';
  status: 'open' | 'under_review' | 'escalated' | 'resolved' | 'closed';
  primary_transaction_id: string | null;
  associated_transaction_ids: string[];
  dataset_batch: string;
  model_batch: string | null;
  risk_assessment_reference: string | null;
  created_at: string;
  updated_at: string;
  notes?: Array<{
    note_id: string;
    content: string;
    author: string | null;
    created_at: string;
    updated_at: string;
  }>;
  activity?: Array<{
    activity_id: string;
    action: string;
    details: string;
    created_at: string;
  }>;
  assessments?: RiskAssessment[];
}

export interface InvestigationCasePage {
  items: InvestigationCase[];
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
}

export interface ReportType {
  type: 'transaction_summary' | 'ml_detection' | 'network_analysis' | 'investigation_brief' | 'risk_dashboard' | 'compliance_export';
  title: string;
  description: string;
  format: 'pdf';
}

export interface GeneratedReport {
  report_id: string;
  report_name: string;
  report_type: ReportType['type'];
  report_title: string;
  created_at: string;
  dataset_batch: string | null;
  model_batch: string | null;
  graph_batch: string | null;
  risk_assessment_version: string | null;
  investigation_case_id: string | null;
  status: 'generating' | 'completed' | 'failed';
  file_format: 'pdf';
  metadata: Record<string, unknown>;
  error_message: string | null;
}

export interface GeneratedReportPage {
  items: GeneratedReport[];
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
}
