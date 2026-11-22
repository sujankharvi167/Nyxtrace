import React, { useCallback, useEffect, useState } from 'react';
import { BarChart3 } from 'lucide-react';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { EmptyState } from '@/components/ui';
import { APIError, api } from '@/services/api';
import type { MLEvaluation, MLStatus, MLSummary, ProcessedDataset } from '@/types';

const COLORS = ['#60a5fa', '#f59e0b', '#94a3b8', '#34d399'];
const count = (value: number | null | undefined) =>
  value == null ? '—' : value.toLocaleString();
const percent = (value: number | null | undefined) =>
  typeof value === 'number' && Number.isFinite(value) ? `${(value * 100).toFixed(1)}%` : 'Unavailable';

export const MLDashboardOverview: React.FC = () => {
  const [dataset, setDataset] = useState<ProcessedDataset | null>(null);
  const [status, setStatus] = useState<MLStatus | null>(null);
  const [evaluation, setEvaluation] = useState<MLEvaluation | null>(null);
  const [summary, setSummary] = useState<MLSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    const [datasetResult, statusResult, evaluationResult, summaryResult] = await Promise.allSettled([
      api.analysis.getDataset(),
      api.ml.status(),
      api.ml.evaluation(),
      api.ml.summary(0.5),
    ]);
    const errors: string[] = [];

    if (datasetResult.status === 'fulfilled') setDataset(datasetResult.value.data ?? null);
    else errors.push(datasetResult.reason instanceof Error ? datasetResult.reason.message : 'Dataset status is unavailable.');

    if (statusResult.status === 'fulfilled') setStatus(statusResult.value.data ?? null);
    else errors.push(statusResult.reason instanceof Error ? statusResult.reason.message : 'Model training status is unavailable.');

    if (evaluationResult.status === 'fulfilled') setEvaluation(evaluationResult.value.data ?? null);
    else if (!(evaluationResult.reason instanceof APIError && evaluationResult.reason.status === 409)) {
      errors.push(evaluationResult.reason instanceof Error ? evaluationResult.reason.message : 'Model evaluation is unavailable.');
      setEvaluation(null);
    } else {
      setEvaluation(null);
    }

    if (summaryResult.status === 'fulfilled') setSummary(summaryResult.value.data ?? null);
    else if (!(summaryResult.reason instanceof APIError && summaryResult.reason.status === 409)) {
      errors.push(summaryResult.reason instanceof Error ? summaryResult.reason.message : 'Prediction summary is unavailable.');
      setSummary(null);
    } else {
      setSummary(null);
    }

    setError(errors.length ? [...new Set(errors)].join(' ') : null);
    setLoading(false);
  }, []);

  useEffect(() => {
    void refresh();
    const datasetUpdated = () => {
      setEvaluation(null);
      setSummary(null);
      void refresh();
    };
    window.addEventListener('nyxtrace:dataset-updated', datasetUpdated);
    return () => window.removeEventListener('nyxtrace:dataset-updated', datasetUpdated);
  }, [refresh]);

  useEffect(() => {
    if (status?.status !== 'running') return undefined;
    const interval = window.setInterval(() => void refresh(), 2000);
    return () => window.clearInterval(interval);
  }, [refresh, status?.status]);

  const classData = dataset
    ? [
        { label: 'Licit', value: dataset.label_counts.licit },
        { label: 'Illicit', value: dataset.label_counts.illicit },
        { label: 'Unknown', value: dataset.label_counts.unknown },
      ]
    : [];
  const predictionData = summary
    ? [
        { label: 'Predicted licit', value: summary.prediction_distribution.licit },
        { label: 'Predicted illicit', value: summary.prediction_distribution.illicit },
      ]
    : [];
  const modelData = evaluation
    ? Object.entries(evaluation.models).map(([model, metrics]) => ({
        model,
        Accuracy: metrics.accuracy,
        Precision: metrics.precision,
        Recall: metrics.recall,
        F1: metrics.f1,
        'ROC-AUC': metrics.roc_auc,
        'PR-AUC': metrics.pr_auc,
      }))
    : [];
  const matrix = evaluation?.metrics.confusion_matrix;
  const matrixData = matrix
    ? [
        { label: 'True negative', value: matrix.true_negative },
        { label: 'False positive', value: matrix.false_positive },
        { label: 'False negative', value: matrix.false_negative },
        { label: 'True positive', value: matrix.true_positive },
      ]
    : [];
  const featureData = evaluation?.global_feature_importance.slice(0, 10).slice().reverse() ?? [];

  return (
    <section className="space-y-4">
      <div>
        <p className="section-label">Stage 3 · Detection and Analysis</p>
        <p className="text-xs text-slate-500 mt-1">Current dataset, persisted model, and held-out results from the backend.</p>
      </div>

      {error && (
        <div className="rounded-lg p-3 text-xs text-red-300" style={{ backgroundColor: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.25)' }}>
          {error}
        </div>
      )}

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <OverviewStat label="Dataset rows" value={count(dataset?.total_transactions)} />
        <OverviewStat label="Model status" value={loading ? 'Checking…' : status?.status ?? 'Unavailable'} />
        <OverviewStat label="Predictions" value={count(summary?.total_predictions)} />
        <OverviewStat label="Flagged at 50%" value={count(summary?.suspicious_count)} tone="amber" />
      </div>

      {status?.status === 'running' && (
        <div className="card p-4">
          <div className="flex items-center justify-between text-xs text-slate-300">
            <span>{status.message}</span><span>{status.progress}%</span>
          </div>
          <div className="h-1.5 rounded-full bg-slate-800 overflow-hidden mt-2">
            <div className="h-full bg-blue-500 transition-all" style={{ width: `${status.progress}%` }} />
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        <ChartCard title="Ground-truth class distribution" subtitle="Labels from the current uploaded class CSV.">
          {loading && !dataset ? <ChartLoading /> : dataset && classData.some(item => item.value > 0) ? (
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={classData}>
                <CartesianGrid stroke="#1e2d4a" strokeDasharray="3 3" />
                <XAxis dataKey="label" tick={{ fill: '#94a3b8', fontSize: 11 }} />
                <YAxis tick={{ fill: '#64748b', fontSize: 10 }} />
                <Tooltip formatter={(value: number) => [count(value), 'Transactions']} contentStyle={tooltipStyle} />
                <Bar dataKey="value" name="Transactions">
                  {classData.map((item, index) => <Cell key={item.label} fill={COLORS[index]} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          ) : <ChartEmpty title={dataset ? 'No labeled transactions' : 'Dataset unavailable'} description={dataset ? 'The uploaded dataset has no recognized ground-truth class labels.' : 'Upload a dataset to view its labeled class distribution.'} />}
        </ChartCard>

        <ChartCard title="Prediction distribution" subtitle={`Threshold ${summary ? percent(summary.threshold) : '—'} · model ${summary?.best_model ?? 'not trained'}`}>
          {loading && !summary ? <ChartLoading /> : summary && summary.total_predictions > 0 ? (
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie data={predictionData} dataKey="value" nameKey="label" outerRadius={95} label={({ name, value }) => `${name}: ${count(Number(value))}`}>
                  {predictionData.map((item, index) => <Cell key={item.label} fill={COLORS[index]} />)}
                </Pie>
                <Tooltip formatter={(value: number) => [count(value), 'Transactions']} contentStyle={tooltipStyle} />
                <Legend />
              </PieChart>
            </ResponsiveContainer>
          ) : <ChartEmpty title="No current predictions" description="Train a model on the current dataset to populate this chart." />}
        </ChartCard>

        <ChartCard title="Held-out model comparison" subtitle={evaluation ? `Selected by ${evaluation.selection_criterion}` : 'Metrics are from the persisted test split.'}>
          {loading && !evaluation ? <ChartLoading /> : modelData.length ? (
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={modelData}>
                <CartesianGrid stroke="#1e2d4a" strokeDasharray="3 3" />
                <XAxis dataKey="model" tick={{ fill: '#94a3b8', fontSize: 10 }} />
                <YAxis domain={[0, 1]} tick={{ fill: '#64748b', fontSize: 10 }} />
                <Tooltip formatter={(value: unknown) => [percent(typeof value === 'number' ? value : null), 'Score']} contentStyle={tooltipStyle} />
                <Legend />
                <Bar dataKey="Accuracy" fill="#64748b" />
                <Bar dataKey="Precision" fill="#60a5fa" />
                <Bar dataKey="Recall" fill="#34d399" />
                <Bar dataKey="F1" fill="#fbbf24" />
                <Bar dataKey="ROC-AUC" fill="#a78bfa" />
                <Bar dataKey="PR-AUC" fill="#f472b6" />
              </BarChart>
            </ResponsiveContainer>
          ) : <ChartEmpty title="No completed evaluation" description="Held-out comparison metrics will appear after training completes." />}
        </ChartCard>

        <ChartCard title="Selected-model confusion matrix" subtitle="Positive class: illicit. Values are held-out transaction counts.">
          {loading && !evaluation ? <ChartLoading /> : matrixData.length ? (
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={matrixData}>
                <CartesianGrid stroke="#1e2d4a" strokeDasharray="3 3" />
                <XAxis dataKey="label" tick={{ fill: '#94a3b8', fontSize: 10 }} />
                <YAxis tick={{ fill: '#64748b', fontSize: 10 }} />
                <Tooltip formatter={(value: number) => [count(value), 'Transactions']} contentStyle={tooltipStyle} />
                <Bar dataKey="value" name="Transactions" fill="#60a5fa" />
              </BarChart>
            </ResponsiveContainer>
          ) : <ChartEmpty title="No confusion matrix" description="A matrix is available after a model has been evaluated." />}
        </ChartCard>

        <ChartCard title="Global feature importance" subtitle={evaluation?.global_feature_importance[0]?.method ?? 'Model-derived importance for the selected model.'}>
          {loading && !evaluation ? <ChartLoading /> : featureData.length ? (
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={featureData} layout="vertical" margin={{ left: 18, right: 12 }}>
                <CartesianGrid stroke="#1e2d4a" strokeDasharray="3 3" />
                <XAxis type="number" tick={{ fill: '#64748b', fontSize: 10 }} />
                <YAxis type="category" dataKey="feature" width={130} tick={{ fill: '#94a3b8', fontSize: 10 }} />
                <Tooltip formatter={(value: number) => [value.toPrecision(4), 'Importance']} contentStyle={tooltipStyle} />
                <Bar dataKey="importance" name="Importance" fill="#60a5fa" />
              </BarChart>
            </ResponsiveContainer>
          ) : <ChartEmpty title="No feature importance" description="Importance is shown after successful model training." />}
        </ChartCard>

        <div className="card p-5 space-y-4">
          <p className="section-label">Dataset and suspicious activity statistics</p>
          <OverviewStat label="Total feature transactions" value={count(dataset?.total_transactions)} />
          <OverviewStat label="Matched predictions" value={count(summary?.total_predictions)} />
          <OverviewStat label="Predicted illicit at threshold" value={count(summary?.suspicious_count)} tone="amber" />
          <OverviewStat label="Share above threshold" value={summary ? percent(summary.suspicious_rate) : '—'} tone="amber" />
          <p className="text-xs text-slate-500">
            Flags are statistical model estimates, not evidence of wrongdoing. Unknown labels remain separate from supervised licit/illicit training.
          </p>
        </div>
      </div>
    </section>
  );
};

const tooltipStyle = {
  background: '#0d1426',
  border: '1px solid #263354',
  borderRadius: 8,
  fontSize: 11,
};

const ChartCard: React.FC<{ title: string; subtitle: string; children: React.ReactNode }> = ({ title, subtitle, children }) => (
  <div className="card p-5">
    <p className="section-label">{title}</p>
    <p className="text-xs text-slate-500 mt-1">{subtitle}</p>
    <div className="h-64 mt-4">{children}</div>
  </div>
);

const ChartLoading: React.FC = () => <div className="h-full flex items-center justify-center text-xs text-slate-500">Loading live API data…</div>;

const ChartEmpty: React.FC<{ title: string; description: string }> = ({ title, description }) => (
  <EmptyState
    className="!py-2"
    icon={<BarChart3 className="w-5 h-5" />}
    title={title}
    description={description}
  />
);

const OverviewStat: React.FC<{ label: string; value: string; tone?: 'amber' }> = ({ label, value, tone }) => (
  <div className="rounded-lg p-3" style={{ backgroundColor: '#141d35', border: '1px solid #1e2d4a' }}>
    <p className="text-[0.62rem] uppercase tracking-wider text-slate-500">{label}</p>
    <p className={`text-sm font-semibold mt-1 ${tone === 'amber' ? 'text-amber-300' : 'text-slate-200'}`}>{value}</p>
  </div>
);
