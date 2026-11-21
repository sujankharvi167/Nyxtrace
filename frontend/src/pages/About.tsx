import React from 'react';
import { Activity, AlertTriangle } from 'lucide-react';
import { SectionHeader } from '@/components/ui';

const TECH_STACK = [
  {
    category: 'Frontend',
    color: '#60a5fa',
    items: ['React 18 + TypeScript', 'Vite 6', 'Tailwind CSS 3', 'React Router 6', 'React Flow (Stage 4)', 'Recharts (Stage 3+)'],
  },
  {
    category: 'Backend',
    color: '#34d399',
    items: ['Python 3.11+', 'FastAPI 0.115', 'Pydantic v2', 'Uvicorn', 'Pandas 2.2', 'NumPy 1.26'],
  },
  {
    category: 'Machine Learning',
    color: '#fbbf24',
    items: ['Scikit-learn 1.5 (Stage 3)', 'XGBoost (Stage 3)', 'SHAP Explainability (Stage 3)', 'NetworkX 3.4 (Stage 4)'],
  },
  {
    category: 'Deployment',
    color: '#a78bfa',
    items: ['Vercel — Frontend', 'Render — Backend', 'GitHub — Version Control'],
  },
];

const CAPABILITIES = [
  { label: 'ML-Based Detection',      desc: 'XGBoost transaction-level suspicious activity classification.',              stage: 3 },
  { label: 'Graph Analytics',         desc: 'NetworkX-powered transaction network construction and community detection.', stage: 4 },
  { label: 'Money-Flow Route Tracing',desc: 'Path identification across intermediary accounts.',                          stage: 4 },
  { label: 'AML Pattern Detection',   desc: 'Layering, fan-in/out, cyclic, and high-velocity pattern detection.',        stage: 4 },
  { label: 'Risk Scoring',            desc: 'Quantitative suspicion scoring with SHAP explainability.',                  stage: 3 },
  { label: 'Investigation Reports',   desc: 'Downloadable investigation summaries and compliance-ready exports.',         stage: 5 },
];

const ROADMAP = [
  { stage: 1, label: 'Project Foundation',         desc: 'Architecture, design system, navigation, frontend-backend connectivity.',               current: true  },
  { stage: 2, label: 'Dataset Processing',         desc: 'CSV upload, validation, cleaning, feature preprocessing, dataset statistics.',           current: false },
  { stage: 3, label: 'Machine Learning',           desc: 'Model training, suspicious classification, risk scoring, SHAP explainability.',          current: false },
  { stage: 4, label: 'Graph Intelligence',         desc: 'NetworkX graph, route tracing, pattern detection, React Flow visualisation.',            current: false },
  { stage: 5, label: 'Investigation Intelligence', desc: 'Investigation summaries, risk insights, downloadable reports, dashboard integration.',   current: false },
  { stage: 6, label: 'Finalisation',               desc: 'Testing, optimisation, security review, CI/CD, deployment preparation.',                 current: false },
];

export const About: React.FC = () => (
  <div className="space-y-6 max-w-4xl">
    <SectionHeader
      title="About NyxTrace"
      subtitle="ML-Powered Money Laundering Detection & Intelligence Platform"
    />

    {/* Hero */}
    <div className="card p-8">
      <div className="flex items-start gap-5">
        <div
          className="w-14 h-14 rounded-2xl flex items-center justify-center flex-shrink-0"
          style={{ background: 'linear-gradient(135deg,#2563eb,#06b6d4)' }}
        >
          <Activity className="w-7 h-7 text-white" />
        </div>
        <div>
          <h2 className="text-xl font-semibold text-slate-100">NyxTrace</h2>
          <p className="text-slate-400 mt-2 leading-relaxed text-sm">
            NyxTrace is an intelligent financial investigation platform designed to identify potentially
            suspicious financial activities and map how funds move through interconnected transaction networks.
            Built as a professional portfolio project, it demonstrates applied Data Science, Machine Learning,
            Graph Analytics, and Full-Stack Engineering in a FinTech context, targeting Anti-Money Laundering
            (AML) analysts, financial crime investigators, and banking compliance teams.
          </p>
        </div>
      </div>
    </div>

    {/* Disclaimer */}
    <div
      className="card p-5"
      style={{ border: '1px solid rgba(245,158,11,0.2)', backgroundColor: 'rgba(245,158,11,0.03)' }}
    >
      <div className="flex items-start gap-3">
        <AlertTriangle className="w-4 h-4 text-amber-400 mt-0.5 flex-shrink-0" />
        <div>
          <p className="text-sm font-semibold text-amber-300 mb-2">Important Disclaimer</p>
          <div className="text-xs text-slate-400 leading-relaxed space-y-1.5">
            <p>NyxTrace is a research and portfolio project. It does not constitute licensed financial or legal advice.</p>
            <p>
              Machine learning model outputs indicate{' '}
              <strong className="text-slate-300">statistical suspicion only</strong> and must not be used as
              sole evidence of criminal activity.
            </p>
            <p>All flagged accounts and transactions require qualified human review and formal investigative procedures before any action is taken.</p>
            <p>Dataset labels (licit / illicit / unknown) reflect dataset annotations — not confirmed legal determinations.</p>
          </div>
        </div>
      </div>
    </div>

    {/* Core capabilities */}
    <div className="card p-5">
      <p className="section-label mb-4">Core Capabilities</p>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {CAPABILITIES.map(({ label, desc, stage }) => (
          <div
            key={label}
            className="p-4 rounded-lg"
            style={{ backgroundColor: '#141d35', border: '1px solid #1e2d4a' }}
          >
            <div className="flex items-start justify-between gap-2">
              <p className="text-sm font-medium text-slate-200">{label}</p>
              <span
                className="font-mono flex-shrink-0"
                style={{
                  fontSize: '0.6rem',
                  padding: '1px 5px',
                  borderRadius: '3px',
                  backgroundColor: '#1e2d4a',
                  color: '#64748b',
                }}
              >
                S{stage}
              </span>
            </div>
            <p className="text-xs text-slate-500 mt-1 leading-relaxed">{desc}</p>
          </div>
        ))}
      </div>
    </div>

    {/* Technology stack */}
    <div className="card p-5">
      <p className="section-label mb-4">Technology Stack</p>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {TECH_STACK.map(({ category, color, items }) => (
          <div key={category}>
            <p className="text-xs font-semibold mb-2" style={{ color }}>{category}</p>
            <ul className="space-y-1.5">
              {items.map(item => (
                <li key={item} className="flex items-center gap-2 text-xs text-slate-400">
                  <span className="w-1 h-1 rounded-full flex-shrink-0" style={{ backgroundColor: '#475569' }} />
                  {item}
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </div>

    {/* Primary dataset */}
    <div className="card p-5">
      <p className="section-label mb-3">Primary Dataset — Elliptic++</p>
      <div className="text-xs text-slate-400 leading-relaxed space-y-2">
        <p>
          The primary dataset is <strong className="text-slate-300">Elliptic++</strong>, a Bitcoin
          transaction graph dataset containing labeled transaction nodes with features, class labels, and an
          edgelist representing transaction relationships.
        </p>
        <p>
          Dataset files:{' '}
          {['txs_features.csv', 'txs_classes.csv', 'txs_edgelist.csv'].map(f => (
            <code
              key={f}
              className="text-blue-300 mx-0.5"
              style={{ backgroundColor: '#1a2440', padding: '1px 5px', borderRadius: '3px' }}
            >
              {f}
            </code>
          ))}
        </p>
        <p>
          Labels: <code style={{ backgroundColor: '#1a2440', padding: '1px 5px', borderRadius: '3px', color: '#f87171' }}>1</code> illicit ·{' '}
          <code style={{ backgroundColor: '#1a2440', padding: '1px 5px', borderRadius: '3px', color: '#34d399' }}>2</code> licit ·{' '}
          <code style={{ backgroundColor: '#1a2440', padding: '1px 5px', borderRadius: '3px', color: '#64748b' }}>unknown</code>
        </p>
        <p className="text-slate-500 italic">
          Note: Elliptic++ contains cryptocurrency data, not conventional bank records. Column schemas are
          inspected at preprocessing time — no hardcoded assumptions are made.
        </p>
      </div>
    </div>

    {/* Roadmap */}
    <div className="card p-5">
      <p className="section-label mb-4">Development Roadmap</p>
      <div className="space-y-2">
        {ROADMAP.map(({ stage, label, desc, current }) => (
          <div
            key={stage}
            className="flex items-start gap-4 p-3 rounded-lg"
            style={
              current
                ? { backgroundColor: 'rgba(59,130,246,0.08)', border: '1px solid rgba(59,130,246,0.2)' }
                : { backgroundColor: '#141d35' }
            }
          >
            <div
              className="w-6 h-6 rounded flex items-center justify-center text-xs font-bold flex-shrink-0"
              style={
                current
                  ? { backgroundColor: '#3b82f6', color: '#fff' }
                  : { backgroundColor: '#1e2d4a', color: '#64748b' }
              }
            >
              {stage}
            </div>
            <div>
              <p className={`text-sm font-medium ${current ? 'text-blue-300' : 'text-slate-300'}`}>
                {label}
                {current && (
                  <span
                    className="ml-2 font-mono"
                    style={{ fontSize: '0.6rem', color: '#60a5fa' }}
                  >
                    CURRENT
                  </span>
                )}
              </p>
              <p className="text-xs text-slate-500 mt-0.5">{desc}</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  </div>
);
