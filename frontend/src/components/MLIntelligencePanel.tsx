import React, { useCallback, useEffect, useState } from 'react';
import {
  AlertCircle,
  BrainCircuit,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Loader2,
  Search,
  ShieldAlert,
} from 'lucide-react';
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { api } from '@/services/api';
import type {
  APIResponse,
  MLEvaluation,
  MLExplanation,
  MLReadiness,
  MLStatus,
  PaginatedPredictions,
} from '@/types';

const number = (value: number | undefined) => (value ?? 0).toLocaleString();
const percent = (value: number | undefined) => `${((value ?? 0) * 100).toFixed(1)}%`;

export const MLIntelligencePanel: React.FC = () => {
  const [readiness, setReadiness] = useState<MLReadiness | null>(null);
  const [status, setStatus] = useState<MLStatus | null>(null);
  const [evaluation, setEvaluation] = useState<MLEvaluation | null>(null);
  const [predictions, setPredictions] = useState<PaginatedPredictions | null>(null);
  const [explanation, setExplanation] = useState<MLExplanation | null>(null);
  const [threshold, setThreshold] = useState(0.5);
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);
  const [suspiciousOnly, setSuspiciousOnly] = useState(true);
  const [loading, setLoading] = useState(true);
  const [training, setTraining] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadEvaluation = useCallback(async () => {
    try {
      const response = await api.ml.evaluation();
      setEvaluation(response.data ?? null);
    } catch (err) {
      if (err instanceof Error && !err.message.includes('409')) setError(err.message);
    }
  }, []);

  const loadPredictions = useCallback(async () => {
    try {
      const response = await api.ml.predictions({
        page,
        pageSize: 10,
        threshold,
        search,
        suspiciousOnly,
      });
      setPredictions(response.data ?? null);
    } catch (err) {
      if (err instanceof Error && !err.message.includes('409')) setError(err.message);
    }
  }, [page, search, suspiciousOnly, threshold]);

  const loadState = useCallback(async () => {
    try {
      const [readyResponse, statusResponse] = await Promise.all([
        api.ml.readiness(),
        api.ml.status(),
      ]);
      setReadiness(readyResponse.data ?? null);
      setStatus(statusResponse.data ?? null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not load ML service status.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadState();
  }, [loadState]);

  useEffect(() => {
    if (status?.status !== 'running') return undefined;
    const timer = window.setInterval(() => {
      void loadState();
    }, 2000);
    return () => window.clearInterval(timer);
  }, [loadState, status?.status]);

  useEffect(() => {
    if (status?.status === 'completed') {
      void loadEvaluation();
      void loadPredictions();
    }
  }, [loadEvaluation, loadPredictions, status?.status]);

  useEffect(() => {
    setPage(1);
  }, [search, threshold, suspiciousOnly]);

  const startTraining = async () => {
    setError(null);
    setTraining(true);
    try {
      const response = await api.ml.train(threshold);
      if (response.data) setStatus(response.data);
      setEvaluation(null);
      setPredictions(null);
      setExplanation(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not start training.');
    } finally {
      setTraining(false);
    }
  };

  const inspectTransaction = async (transactionId: string) => {
    setError(null);
    try {
      const response = await api.ml.explain(transactionId);
      setExplanation(response.data ?? null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not load transaction explanation.');
    }
  };

  const chartData = evaluation
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

  return (
    <section className="space-y-5">
      <div className="card p-5 md:p-6">
        <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
          <div className="flex items-start gap-3">
            <div className="rounded-lg p-2 text-blue-300" style={{ backgroundColor: 'rgba(59,130,246,0.12)' }}>
              <BrainCircuit className="w-5 h-5" />
            </div>
            <div>
              <p className="section-label">Stage 3 · Machine Learning Intelligence</p>
              <p className="text-sm text-slate-400 mt-1">
                Compare supervised models on labeled records. Unknown ground-truth transactions remain excluded from training.
              </p>
            </div>
          </div>
          <button
            type="button"
            className="btn-primary whitespace-nowrap disabled:opacity-40"
            onClick={startTraining}
            disabled={!readiness?.ready || status?.status === 'running' || training || loading}
          >
            {training || status?.status === 'running'
              ? <><Loader2 className="w-4 h-4 animate-spin" /> Training models</>
              : <><BrainCircuit className="w-4 h-4" /> Train &amp; evaluate</>}
          </button>
        </div>

        <div className="mt-5 grid grid-cols-2 md:grid-cols-4 gap-3">
          <SummaryCell label="Dataset status" value={loading ? 'Checking…' : readiness?.ready ? 'Ready' : 'Not ready'} tone={readiness?.ready ? 'green' : 'muted'} />
          <SummaryCell label="Feature rows" value={number(readiness?.total_transactions)} />
          <SummaryCell label="Licit / illicit" value={`${number(readiness?.label_counts.licit)} / ${number(readiness?.label_counts.illicit)}`} />
          <SummaryCell label="Unknown excluded" value={number(readiness?.label_counts.unknown)} />
        </div>
        {readiness && !readiness.ready && <p className="text-xs text-amber-300 mt-3">{readiness.message}</p>}

        <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="min-w-0">
            <p className="text-xs text-slate-300">{status?.message ?? 'Ready to train Logistic Regression and Random Forest.'}</p>
            {status?.error && <p className="text-xs text-red-300 mt-1">{status.error}</p>}
            {status?.best_model && <p className="text-xs text-emerald-300 mt-1">Selected: {status.best_model}</p>}
          </div>
          <label className="flex items-center gap-2 text-xs text-slate-400 whitespace-nowrap">
            Illicit threshold
            <input
              type="number"
              min="0.05"
              max="0.95"
              step="0.05"
              value={threshold}
              onChange={event => setThreshold(Math.min(0.95, Math.max(0.05, Number(event.target.value))))}
              className="w-20 rounded-md px-2 py-1 text-slate-200"
              style={{ backgroundColor: '#0a0e1a', border: '1px solid #263354' }}
            />
          </label>
        </div>
        {status?.status === 'running' && (
          <div className="mt-3">
            <div className="h-1.5 rounded-full bg-slate-800 overflow-hidden">
              <div className="h-full bg-blue-500 transition-all" style={{ width: `${status.progress}%` }} />
            </div>
            <p className="text-[0.65rem] text-slate-500 mt-1">{status.progress}% · processing in the background</p>
          </div>
        )}
      </div>

      {error && (
        <div className="card p-3 flex items-start gap-2" style={{ borderLeft: '2px solid #ef4444' }}>
          <AlertCircle className="w-4 h-4 text-red-400 mt-0.5" />
          <p className="text-xs text-red-300">{error}</p>
        </div>
      )}

      {!evaluation ? (
        <div className="card p-8 text-center">
          {status?.status === 'running' ? <Loader2 className="w-6 h-6 animate-spin text-blue-400 mx-auto" /> : <BrainCircuit className="w-6 h-6 text-slate-600 mx-auto" />}
          <p className="text-sm text-slate-300 mt-3">{status?.status === 'running' ? 'Training and evaluating models…' : 'No completed model evaluation yet'}</p>
          <p className="text-xs text-slate-500 mt-1">Training outputs, metrics, and predictions will appear here.</p>
        </div>
      ) : (
        <>
          <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-3">
            <MetricCard label="Illicit precision" value={percent(evaluation.metrics.precision)} />
            <MetricCard label="Illicit recall" value={percent(evaluation.metrics.recall)} />
            <MetricCard label="Illicit F1" value={percent(evaluation.metrics.f1)} />
            <MetricCard label="ROC-AUC" value={percent(evaluation.metrics.roc_auc)} />
            <MetricCard label="PR-AUC" value={percent(evaluation.metrics.pr_auc)} />
            <MetricCard label="Accuracy" value={percent(evaluation.metrics.accuracy)} />
          </div>

          <div className="grid grid-cols-1 xl:grid-cols-2 gap-5">
            <div className="card p-5">
              <p className="section-label">Held-out model comparison</p>
              <p className="text-xs text-slate-500 mt-1">
                Best: {evaluation.best_model} · {evaluation.selection_criterion}
              </p>
              <div className="h-72 mt-4">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={chartData} margin={{ top: 8, right: 8, left: -18, bottom: 4 }}>
                    <CartesianGrid stroke="#1e2d4a" strokeDasharray="3 3" />
                    <XAxis dataKey="model" tick={{ fill: '#94a3b8', fontSize: 11 }} />
                    <YAxis domain={[0, 1]} tick={{ fill: '#64748b', fontSize: 10 }} />
                    <Tooltip contentStyle={{ background: '#0d1426', border: '1px solid #263354', borderRadius: 8, fontSize: 11 }} />
                    <Bar dataKey="Accuracy" fill="#64748b" />
                    <Bar dataKey="Precision" fill="#60a5fa" />
                    <Bar dataKey="Recall" fill="#34d399" />
                    <Bar dataKey="F1" fill="#fbbf24" />
                    <Bar dataKey="ROC-AUC" fill="#a78bfa" />
                    <Bar dataKey="PR-AUC" fill="#f472b6" />
                  </BarChart>
                </ResponsiveContainer>
              </div>
              <p className="text-xs text-slate-500 mt-1">
                Chronological split: {evaluation.dataset.split_strategy.replace(/_/g, ' ')}
                {evaluation.dataset.time_column && ` at ${evaluation.dataset.time_column} ${evaluation.dataset.time_cutoff}`}.
              </p>
            </div>

            <div className="card p-5 space-y-4">
              <p className="section-label">Selected model · {evaluation.best_model}</p>
              <div className="grid grid-cols-2 gap-3">
                <SummaryCell label="Available labeled records" value={number(evaluation.dataset.available_supervised_records)} />
                <SummaryCell label="Training records" value={number(evaluation.dataset.trained_records)} />
                <SummaryCell label="Evaluation records" value={number(evaluation.dataset.evaluated_records)} />
                <SummaryCell label="Sampling applied" value={evaluation.dataset.sampling_applied ? 'Yes' : 'No'} tone={evaluation.dataset.sampling_applied ? 'amber' : 'green'} />
                <SummaryCell label="Train licit / illicit" value={`${number(evaluation.dataset.trained_class_distribution.licit)} / ${number(evaluation.dataset.trained_class_distribution.illicit)}`} />
                <SummaryCell label="Test licit / illicit" value={`${number(evaluation.dataset.evaluated_class_distribution.licit)} / ${number(evaluation.dataset.evaluated_class_distribution.illicit)}`} />
              </div>
              {matrix && (
                <div>
                  <p className="text-xs font-medium text-slate-300 mb-2">Confusion matrix · positive class: illicit</p>
                  <div className="grid grid-cols-3 gap-px text-center text-xs overflow-hidden rounded-lg" style={{ backgroundColor: '#263354' }}>
                    {['Actual / Predicted', 'Licit', 'Illicit', 'Licit', number(matrix.true_negative), number(matrix.false_positive), 'Illicit', number(matrix.false_negative), number(matrix.true_positive)].map((value, index) => (
                      <div key={index} className={`p-2 ${index < 3 ? 'text-slate-400' : 'text-slate-200'}`} style={{ backgroundColor: '#111a2e' }}>{value}</div>
                    ))}
                  </div>
                  <p className="text-xs text-slate-500 mt-2">
                    False positive rate {percent(evaluation.metrics.false_positive_rate)} · false negative rate {percent(evaluation.metrics.false_negative_rate)}
                  </p>
                </div>
              )}
              <p className="text-xs text-slate-500">
                Class imbalance is handled with class weighting. Unknown ground truth ({number(evaluation.dataset.unknown_records_excluded_from_supervision)} records) is never used as licit training data.
              </p>
            </div>
          </div>

          <div className="grid grid-cols-1 xl:grid-cols-2 gap-5">
            <div className="card p-5">
              <p className="section-label">Global feature importance</p>
              <p className="text-xs text-slate-500 mt-1">{evaluation.global_feature_importance[0]?.method ?? 'Model-specific importance'}</p>
              <div className="h-80 mt-4">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={evaluation.global_feature_importance.slice(0, 12).reverse()} layout="vertical" margin={{ left: 18, right: 20 }}>
                    <CartesianGrid stroke="#1e2d4a" strokeDasharray="3 3" />
                    <XAxis type="number" tick={{ fill: '#64748b', fontSize: 10 }} />
                    <YAxis type="category" dataKey="feature" width={130} tick={{ fill: '#94a3b8', fontSize: 10 }} />
                    <Tooltip contentStyle={{ background: '#0d1426', border: '1px solid #263354', borderRadius: 8, fontSize: 11 }} />
                    <Bar dataKey="importance" fill="#60a5fa" />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>

            <div className="card p-5">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <p className="section-label">Transaction predictions</p>
                  <p className="text-xs text-slate-500 mt-1">Predictions are model estimates, not evidence of wrongdoing.</p>
                </div>
                <label className="flex items-center gap-2 text-xs text-slate-400">
                  <input type="checkbox" checked={suspiciousOnly} onChange={event => setSuspiciousOnly(event.target.checked)} />
                  Above threshold only
                </label>
              </div>
              <div className="relative mt-4">
                <Search className="w-3.5 h-3.5 text-slate-500 absolute left-3 top-2.5" />
                <input
                  type="search"
                  value={search}
                  onChange={event => setSearch(event.target.value)}
                  placeholder="Search transaction ID"
                  className="w-full rounded-lg pl-9 pr-3 py-2 text-xs text-slate-200"
                  style={{ backgroundColor: '#0a0e1a', border: '1px solid #263354' }}
                />
              </div>
              <div className="overflow-x-auto mt-3">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="text-slate-500" style={{ borderBottom: '1px solid #263354' }}>
                      <th className="text-left p-2">Transaction ID</th>
                      <th className="text-left p-2">Prediction</th>
                      <th className="text-right p-2">Illicit probability</th>
                      <th className="text-left p-2">Model</th>
                      <th className="text-left p-2">Ground truth</th>
                    </tr>
                  </thead>
                  <tbody>
                    {predictions?.items.map(item => (
                      <tr
                        key={item.transaction_id}
                        onClick={() => void inspectTransaction(item.transaction_id)}
                        className="cursor-pointer hover:bg-slate-800/40"
                        style={{ borderBottom: '1px solid #1e2d4a' }}
                      >
                        <td className="p-2 text-slate-300 font-mono">{item.transaction_id}</td>
                        <td className={`p-2 capitalize ${item.predicted_class === 'illicit' ? 'text-amber-300' : 'text-emerald-300'}`}>
                          {item.predicted_class === 'illicit' && <ShieldAlert className="w-3 h-3 inline mr-1" />}
                          {item.predicted_class}
                        </td>
                        <td className="p-2 text-right text-slate-300">{percent(item.illicit_probability)}</td>
                        <td className="p-2 text-slate-400">{item.selected_model}</td>
                        <td className="p-2 capitalize text-slate-500">{item.ground_truth_label}</td>
                      </tr>
                    ))}
                    {!predictions?.items.length && (
                      <tr><td colSpan={5} className="p-6 text-center text-slate-500">No predictions match these filters.</td></tr>
                    )}
                  </tbody>
                </table>
              </div>
              <div className="flex items-center justify-between mt-3">
                <p className="text-xs text-slate-500">{number(predictions?.total)} matching transactions</p>
                <div className="flex items-center gap-2">
                  <button className="rounded-md p-1 text-slate-400 hover:bg-slate-800 disabled:opacity-30" disabled={page <= 1} onClick={() => setPage(current => Math.max(1, current - 1))}><ChevronLeft className="w-4 h-4" /></button>
                  <span className="text-xs text-slate-500">{page} / {Math.max(1, predictions?.total_pages ?? 1)}</span>
                  <button className="rounded-md p-1 text-slate-400 hover:bg-slate-800 disabled:opacity-30" disabled={!predictions || page >= predictions.total_pages} onClick={() => setPage(current => current + 1)}><ChevronRight className="w-4 h-4" /></button>
                </div>
              </div>
            </div>
          </div>

          {explanation && (
            <div className="card p-5">
              <div className="flex items-start gap-3">
                <CheckCircle2 className="w-4 h-4 text-blue-400 mt-0.5" />
                <div className="min-w-0 flex-1">
                  <p className="section-label">Transaction explanation · {explanation.transaction_id}</p>
                  <p className="text-xs text-slate-400 mt-1">
                    {explanation.predicted_class} · illicit probability {percent(explanation.illicit_probability)} · original label {explanation.ground_truth_label}
                  </p>
                  <p className="text-xs text-slate-500 mt-1">{explanation.method}</p>
                  <div className="mt-3 space-y-2">
                    {explanation.features.slice(0, 10).map(feature => (
                      <div key={feature.feature} className="grid grid-cols-[minmax(0,1fr)_auto_auto] gap-3 text-xs">
                        <span className="truncate text-slate-300">{feature.feature}</span>
                        <span className="text-slate-500">value {feature.observed_value.toPrecision(4)}</span>
                        <span className={feature.probability_delta >= 0 ? 'text-amber-300' : 'text-emerald-300'}>
                          Δ {feature.probability_delta >= 0 ? '+' : ''}{percent(feature.probability_delta)}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          )}
        </>
      )}
    </section>
  );
};

const SummaryCell: React.FC<{ label: string; value: string; tone?: 'green' | 'amber' | 'muted' }> = ({ label, value, tone = 'muted' }) => (
  <div className="rounded-lg p-3 min-w-0" style={{ backgroundColor: '#141d35', border: '1px solid #1e2d4a' }}>
    <p className="text-[0.62rem] uppercase tracking-wider text-slate-500 truncate">{label}</p>
    <p className={`text-sm font-semibold mt-1 truncate ${tone === 'green' ? 'text-emerald-300' : tone === 'amber' ? 'text-amber-300' : 'text-slate-200'}`}>{value}</p>
  </div>
);

const MetricCard: React.FC<{ label: string; value: string }> = ({ label, value }) => (
  <div className="card p-4">
    <p className="text-[0.62rem] uppercase tracking-wider text-slate-500">{label}</p>
    <p className="text-xl font-semibold text-slate-100 mt-2">{value}</p>
  </div>
);
