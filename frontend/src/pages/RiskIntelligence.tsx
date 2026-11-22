import React, { useEffect, useState } from 'react';
import { AlertTriangle, Info, Loader2, Search, TrendingUp } from 'lucide-react';
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { SectionHeader, EmptyState } from '@/components/ui';
import { api } from '@/services/api';
import type { RiskAssessment, RiskReadiness } from '@/types';

export const RiskIntelligence: React.FC = () => {
  const [readiness, setReadiness] = useState<RiskReadiness | null>(null);
  const [distribution, setDistribution] = useState<Record<string, number> | null>(null);
  const [assessments, setAssessments] = useState<RiskAssessment[]>([]);
  const [selected, setSelected] = useState<RiskAssessment | null>(null);
  const [search, setSearch] = useState('');
  const [category, setCategory] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = async () => {
    setLoading(true);
    setError(null);
    try {
      const [ready, dist, list] = await Promise.all([
        api.risk.readiness(),
        api.risk.distribution(),
        api.risk.assessments({
          page: 1,
          pageSize: 50,
          category: category || undefined,
          search: search || undefined,
          sortBy: 'risk_score',
          sortOrder: 'desc',
        }),
      ]);
      setReadiness(ready.data ?? null);
      setDistribution(dist.data?.distribution ?? null);
      setAssessments(list.data?.items ?? []);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not load risk intelligence.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void refresh();
  }, [category]);

  const assessTransaction = async (transactionId: string) => {
    setError(null);
    try {
      const response = await api.risk.assess(transactionId);
      setSelected(response.data ?? null);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not assess transaction.');
    }
  };

  const chartData = distribution
    ? ['critical', 'high', 'medium', 'low'].map(level => ({
        level: level[0].toUpperCase() + level.slice(1),
        count: distribution[level] ?? 0,
      }))
    : [];

  return (
    <div className="space-y-6">
      <SectionHeader
        title="Risk Intelligence"
        subtitle="Evidence-based investigation risk and persistent transaction assessments"
      />

      <div className="card p-4" style={{ borderLeft: '2px solid #ef4444' }}>
        <div className="flex items-start gap-3">
          <Info className="w-4 h-4 text-red-400 mt-0.5 flex-shrink-0" />
          <p className="text-xs text-slate-400">
            Investigation risk is a transparent combined score, not a calibrated probability of criminal activity.
            Graph depth and ML predictions require human review.
          </p>
        </div>
      </div>

      {error && <div className="card p-3 text-xs text-red-300" style={{ borderLeft: '2px solid #ef4444' }}>{error}</div>}

      {loading ? (
        <div className="card p-10 text-center"><Loader2 className="w-6 h-6 animate-spin mx-auto text-blue-400" /></div>
      ) : readiness?.compatible ? (
        <>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <RiskStat label="Dataset batch" value={readiness.dataset_batch ?? '—'} mono />
            <RiskStat label="Model batch" value={readiness.model_batch ?? '—'} mono />
            <RiskStat label="Graph batch" value={readiness.graph_batch ?? '—'} mono />
            <RiskStat label="Assessment version" value={readiness.scoring_version} />
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
            <div className="card p-5 lg:col-span-2">
              <p className="section-label mb-4">Risk category distribution</p>
              {chartData.some(item => item.count > 0) ? (
                <div className="h-72">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={chartData}>
                      <CartesianGrid stroke="#1e2d4a" strokeDasharray="3 3" />
                      <XAxis dataKey="level" tick={{ fill: '#94a3b8', fontSize: 11 }} />
                      <YAxis tick={{ fill: '#64748b', fontSize: 10 }} />
                      <Tooltip contentStyle={{ background: '#0d1426', border: '1px solid #263354', borderRadius: 8 }} />
                      <Bar dataKey="count" fill="#60a5fa" />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              ) : <EmptyState icon={<TrendingUp className="w-6 h-6" />} title="No assessments" description="Select or assess a transaction to populate this chart." />}
            </div>

            <div className="card p-5">
              <p className="section-label mb-4">Scoring method</p>
              <div className="space-y-2 text-xs text-slate-400">
                {Object.entries(readiness.weights).map(([factor, weight]) => (
                  <div key={factor} className="flex justify-between gap-3" style={{ borderBottom: '1px solid #1e2d4a' }}>
                    <span>{factor.replace(/_/g, ' ')}</span>
                    <span className="font-mono text-slate-200">{Math.round(weight * 100)}%</span>
                  </div>
                ))}
              </div>
              <p className="text-xs text-slate-500 mt-4">
                Thresholds: Low 0-0.39 · Medium 0.40-0.69 · High 0.70-0.89 · Critical 0.90-1.00
              </p>
            </div>
          </div>

          <div className="card p-5">
            <div className="grid grid-cols-1 md:grid-cols-[1fr_180px_auto] gap-3 mb-4">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
                <input
                  value={search}
                  onChange={event => setSearch(event.target.value)}
                  onKeyDown={event => { if (event.key === 'Enter') void refresh(); }}
                  placeholder="Search transaction ID"
                  className="w-full rounded-lg py-2 pl-10 pr-3 text-xs text-slate-200"
                  style={{ backgroundColor: '#141d35', border: '1px solid #1e2d4a' }}
                />
              </div>
              <select value={category} onChange={event => setCategory(event.target.value)} className="rounded-lg px-3 py-2 text-xs text-slate-300" style={{ backgroundColor: '#141d35', border: '1px solid #1e2d4a' }}>
                <option value="">All categories</option>
                <option value="critical">Critical</option>
                <option value="high">High</option>
                <option value="medium">Medium</option>
                <option value="low">Low</option>
              </select>
              <button type="button" className="btn-primary" onClick={() => void refresh()}><Search className="w-4 h-4" /> Apply</button>
            </div>

            {assessments.length ? (
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="text-slate-500 text-left">
                      <th className="py-2 pr-4">Transaction ID</th>
                      <th className="py-2 pr-4">ML prediction</th>
                      <th className="py-2 pr-4">ML probability</th>
                      <th className="py-2 pr-4">Combined score</th>
                      <th className="py-2 pr-4">Category</th>
                      <th className="py-2 pr-4">Graph evidence</th>
                      <th className="py-2 pr-4">Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {assessments.map(row => (
                      <tr key={row.transaction_id} style={{ borderTop: '1px solid #1e2d4a' }}>
                        <td className="py-3 pr-4 font-mono text-slate-200">{row.transaction_id}</td>
                        <td className="py-3 pr-4 text-slate-300">{row.ml_prediction}</td>
                        <td className="py-3 pr-4 text-slate-300">{(row.ml_probability * 100).toFixed(2)}%</td>
                        <td className="py-3 pr-4 text-slate-200">{row.combined_risk_score.toFixed(3)}</td>
                        <td className="py-3 pr-4"><RiskBadge category={row.risk_category} /></td>
                        <td className="py-3 pr-4 text-slate-400">
                          {row.graph_findings.incoming_count} in · {row.graph_findings.outgoing_count} out
                        </td>
                        <td className="py-3 pr-4">
                          <button type="button" onClick={() => setSelected(row)} className="text-blue-400 hover:text-blue-300">Details</button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <EmptyState icon={<AlertTriangle className="w-6 h-6" />} title="No risk assessments" description="Assess a transaction ID to create the first persisted result." />
            )}
          </div>

          <div className="card p-5">
            <p className="section-label mb-3">Individual transaction assessment</p>
            <TransactionAssessment onAssess={assessTransaction} />
            {selected && (
              <div className="mt-4 grid grid-cols-1 lg:grid-cols-2 gap-4">
                <div className="rounded-lg p-4" style={{ backgroundColor: '#141d35', border: '1px solid #1e2d4a' }}>
                  <p className="text-xs text-slate-500">Transaction</p>
                  <p className="font-mono text-sm text-slate-200 mt-1">{selected.transaction_id}</p>
                  <p className="text-xs mt-3">ML probability: <span className="text-slate-200">{(selected.ml_probability * 100).toFixed(2)}%</span></p>
                  <p className="text-xs mt-1">Combined risk: <span className="text-slate-200">{selected.combined_risk_score.toFixed(3)}</span></p>
                  <p className="text-xs mt-1">Category: <RiskBadge category={selected.risk_category} /></p>
                </div>
                <div className="rounded-lg p-4" style={{ backgroundColor: '#141d35', border: '1px solid #1e2d4a' }}>
                  <p className="text-xs text-slate-300">{selected.explanation.summary}</p>
                  {selected.contributing_factors.length > 0 && (
                    <ul className="mt-3 space-y-1 text-xs text-slate-400 list-disc pl-4">
                      {selected.contributing_factors.map(factor => <li key={factor}>{factor}</li>)}
                    </ul>
                  )}
                </div>
              </div>
            )}
          </div>
        </>
      ) : (
        <div className="card p-8">
          <EmptyState icon={<AlertTriangle className="w-7 h-7" />} title="Risk analysis unavailable" description={readiness?.message ?? 'Dataset, model, predictions, and graph are not compatible.'} />
        </div>
      )}
    </div>
  );
};

const RiskStat: React.FC<{ label: string; value: string; mono?: boolean }> = ({ label, value, mono }) => (
  <div className="card p-4">
    <p className="text-[0.62rem] uppercase tracking-wider text-slate-500">{label}</p>
    <p className={`text-sm font-semibold mt-1 text-slate-200 ${mono ? 'font-mono break-all' : ''}`}>{value}</p>
  </div>
);

const RiskBadge: React.FC<{ category: RiskAssessment['risk_category'] }> = ({ category }) => (
  <span className={`text-[0.65rem] px-2 py-1 rounded border ${
    category === 'critical' ? 'text-red-300 border-red-900' :
    category === 'high' ? 'text-orange-300 border-orange-900' :
    category === 'medium' ? 'text-amber-300 border-amber-900' : 'text-emerald-300 border-emerald-900'
  }`}>{category}</span>
);

const TransactionAssessment: React.FC<{ onAssess: (transactionId: string) => void }> = ({ onAssess }) => {
  const [transactionId, setTransactionId] = useState('');
  return (
    <div className="grid grid-cols-1 md:grid-cols-[1fr_auto] gap-3">
      <input value={transactionId} onChange={event => setTransactionId(event.target.value)} placeholder="Transaction ID" className="rounded-lg px-3 py-2 text-xs text-slate-200" style={{ backgroundColor: '#141d35', border: '1px solid #1e2d4a' }} />
      <button type="button" className="btn-primary" onClick={() => onAssess(transactionId.trim())}>Assess transaction</button>
    </div>
  );
};
