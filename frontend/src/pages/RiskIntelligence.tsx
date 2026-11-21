import React from 'react';
import { Info, AlertTriangle, TrendingUp, Eye } from 'lucide-react';
import { SectionHeader, EmptyState } from '@/components/ui';

const AML_PATTERNS = [
  { label: 'Structuring / Smurfing', severity: 'High',   desc: 'Breaking large amounts into smaller transactions to avoid reporting thresholds.' },
  { label: 'Layering',               severity: 'High',   desc: 'Moving funds through multiple accounts to obscure the audit trail.' },
  { label: 'Fan-out Pattern',        severity: 'Medium', desc: 'Single source distributing to many recipients simultaneously.' },
  { label: 'Fan-in Pattern',         severity: 'Medium', desc: 'Many sources converging funds into a single destination account.' },
  { label: 'Cyclic Transactions',    severity: 'High',   desc: 'Funds returning to their origin account via circular routes.' },
  { label: 'Rapid Movement',         severity: 'Medium', desc: 'Unusually high-velocity fund transfers across a short time window.' },
];

const RISK_TIERS = [
  { level: 'Critical', range: '0.90 – 1.00', color: '#f87171', width: '100%' },
  { level: 'High',     range: '0.70 – 0.89', color: '#fb923c', width: '80%'  },
  { level: 'Medium',   range: '0.40 – 0.69', color: '#fbbf24', width: '60%'  },
  { level: 'Low',      range: '0.00 – 0.39', color: '#34d399', width: '40%'  },
];

const severityStyle = (s: string): React.CSSProperties => ({
  color:           s === 'High' ? '#f87171' : '#fbbf24',
  backgroundColor: s === 'High' ? 'rgba(239,68,68,0.1)' : 'rgba(245,158,11,0.1)',
  border:          `1px solid ${s === 'High' ? 'rgba(239,68,68,0.2)' : 'rgba(245,158,11,0.2)'}`,
  fontSize: '0.6rem',
  padding: '1px 6px',
  borderRadius: '3px',
  fontWeight: 600,
});

export const RiskIntelligence: React.FC = () => (
  <div className="space-y-6">
    <SectionHeader
      title="Risk Intelligence"
      subtitle="Suspicious activity detection and financial risk insights"
    />

    {/* Stage notice */}
    <div className="card p-4" style={{ borderLeft: '2px solid #ef4444', backgroundColor: 'rgba(239,68,68,0.03)' }}>
      <div className="flex items-start gap-3">
        <Info className="w-4 h-4 text-red-400 mt-0.5 flex-shrink-0" />
        <div>
          <p className="text-sm font-medium text-red-300">Stage 3 &amp; 5 Feature</p>
          <div className="text-xs text-slate-400 mt-1 space-y-1">
            <p>Risk scoring and ML-based detection require a trained model (Stage 3).</p>
            <p className="italic text-slate-500">
              Important: ML model outputs indicate <strong className="text-slate-400">statistical suspicion
              only</strong>. All flagged transactions must be reviewed by a qualified analyst and do not
              constitute confirmed criminal activity.
            </p>
          </div>
        </div>
      </div>
    </div>

    {/* Distribution + legend */}
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
      <div className="card p-5 lg:col-span-2">
        <p className="section-label mb-4">Risk Distribution</p>
        <EmptyState
          icon={<TrendingUp className="w-6 h-6" />}
          title="No Risk Data Available"
          description="Risk distribution charts will display here after ML model training and prediction (Stage 3). Data reflects statistical suspicion, not confirmed findings."
        />
      </div>

      <div className="card p-5">
        <p className="section-label mb-4">Risk Score Legend</p>
        <div className="space-y-3">
          {RISK_TIERS.map(({ level, range, color, width }) => (
            <div key={level}>
              <div className="flex items-center justify-between text-xs mb-1.5">
                <span style={{ color }}>{level}</span>
                <span className="text-slate-500 font-mono">{range}</span>
              </div>
              <div className="h-1.5 rounded-full" style={{ backgroundColor: '#1e2d4a' }}>
                <div
                  className="h-full rounded-full"
                  style={{ width, backgroundColor: color, opacity: 0.5 }}
                />
              </div>
            </div>
          ))}
        </div>

        <div className="mt-5 pt-4" style={{ borderTop: '1px solid #1e2d4a' }}>
          <p className="text-xs text-slate-500 leading-relaxed">
            Scores are model-computed probabilities. They do not constitute legal findings and require
            expert review before any action is taken.
          </p>
        </div>
      </div>
    </div>

    {/* AML pattern library */}
    <div className="card p-5">
      <p className="section-label mb-4">AML Pattern Categories</p>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
        {AML_PATTERNS.map(({ label, severity, desc }) => (
          <div
            key={label}
            className="p-4 rounded-lg opacity-60"
            style={{ backgroundColor: '#141d35', border: '1px solid #1e2d4a' }}
          >
            <div className="flex items-start justify-between gap-2 mb-2">
              <AlertTriangle className="w-4 h-4 text-slate-500 mt-0.5 flex-shrink-0" />
              <span style={severityStyle(severity)}>{severity}</span>
            </div>
            <p className="text-sm font-medium text-slate-300">{label}</p>
            <p className="text-xs text-slate-500 mt-1 leading-relaxed">{desc}</p>
            <p className="section-label mt-3">Stage 3–4 Detection</p>
          </div>
        ))}
      </div>
    </div>

    {/* SHAP placeholder */}
    <div className="card p-5">
      <p className="section-label mb-4">Model Explainability — SHAP</p>
      <EmptyState
        icon={<Eye className="w-6 h-6" />}
        title="Explainability Not Yet Available"
        description="SHAP-based feature importance and per-prediction explanations will be available after ML model training in Stage 3."
      />
    </div>

    {/* Suspicious transactions table placeholder */}
    <div className="card p-5">
      <div
        className="flex items-center justify-between pb-4 mb-4"
        style={{ borderBottom: '1px solid #1e2d4a' }}
      >
        <p className="section-label">Flagged Transactions</p>
        <span className="text-xs text-slate-600">Requires Stage 3</span>
      </div>
      <EmptyState
        icon={<AlertTriangle className="w-6 h-6" />}
        title="No Flagged Transactions"
        description="Transactions flagged by the ML model will appear in a sortable, filterable table here after Stage 3 is complete."
      />
    </div>
  </div>
);
