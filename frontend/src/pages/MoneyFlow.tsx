import React from 'react';
import { GitFork, Search, Info, Network, ArrowRightLeft, Layers } from 'lucide-react';
import { SectionHeader, EmptyState } from '@/components/ui';

const CAPABILITIES = [
  {
    icon: Network,
    label: 'Transaction Graph',
    desc: 'Interactive React Flow visualisation of fund movements between wallets and accounts.',
    color: '#22d3ee',
    stage: 'Stage 4',
  },
  {
    icon: ArrowRightLeft,
    label: 'Route Tracing',
    desc: 'Trace money-flow paths across any number of intermediary accounts using shortest-path algorithms.',
    color: '#22d3ee',
    stage: 'Stage 4',
  },
  {
    icon: Layers,
    label: 'Pattern Detection',
    desc: 'Identify layering, fan-in / fan-out, cyclic transactions, and high-velocity fund movement.',
    color: '#22d3ee',
    stage: 'Stage 4',
  },
];

export const MoneyFlow: React.FC = () => (
  <div className="space-y-6">
    <SectionHeader
      title="Money Flow Intelligence"
      subtitle="Transaction network analysis and fund route tracing"
    />

    {/* Stage notice */}
    <div className="card p-4" style={{ borderLeft: '2px solid #06b6d4' }}>
      <div className="flex items-start gap-3">
        <Info className="w-4 h-4 text-cyan-400 mt-0.5 flex-shrink-0" />
        <div>
          <p className="text-sm font-medium text-cyan-300">Stage 4 Feature</p>
          <p className="text-xs text-slate-400 mt-1">
            Graph construction, network analysis, and interactive visualisation require a processed dataset
            (Stage 2) and a trained ML model (Stage 3). The full graph engine will be implemented in Stage 4
            using NetworkX on the backend and React Flow on the frontend.
          </p>
        </div>
      </div>
    </div>

    {/* Search bar */}
    <div className="card p-5">
      <p className="section-label mb-3">Account &amp; Transaction Search</p>
      <div className="flex gap-3">
        <div className="flex-1 relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
          <input
            type="text"
            placeholder="Search by wallet address, transaction ID, or account…"
            disabled
            className="w-full rounded-lg py-2.5 pl-10 pr-4 text-sm text-slate-500 cursor-not-allowed"
            style={{ backgroundColor: '#141d35', border: '1px solid #1e2d4a' }}
          />
        </div>
        <button disabled className="btn-primary opacity-40 cursor-not-allowed">
          <GitFork className="w-4 h-4" />
          Trace Flow
        </button>
      </div>
    </div>

    {/* Graph canvas placeholder */}
    <div className="card" style={{ minHeight: 420 }}>
      <div
        className="p-5 flex items-center justify-between"
        style={{ borderBottom: '1px solid #1e2d4a' }}
      >
        <p className="section-label">Transaction Network Graph</p>
        <span className="text-xs text-slate-600">Requires Stage 2 (data) + Stage 4 (graph engine)</span>
      </div>
      <EmptyState
        icon={<Network className="w-8 h-8" />}
        title="Graph Visualization Not Yet Available"
        description="Process a dataset and train the ML model first. The interactive transaction network will render here in Stage 4 using React Flow."
        className="py-20"
      />
    </div>

    {/* Source / destination info panels */}
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      {['Source Account', 'Destination Account'].map(label => (
        <div key={label} className="card p-5 opacity-50">
          <p className="section-label mb-3">{label}</p>
          <div className="space-y-2">
            {['Address', 'Total Sent', 'Total Received', 'Risk Score', 'Label'].map(field => (
              <div
                key={field}
                className="flex items-center justify-between py-1.5"
                style={{ borderBottom: '1px solid #1e2d4a' }}
              >
                <span className="text-xs text-slate-500">{field}</span>
                <span className="text-xs text-slate-700 font-mono">—</span>
              </div>
            ))}
          </div>
          <p className="section-label mt-3">Stage 4</p>
        </div>
      ))}
    </div>

    {/* Capability cards */}
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
      {CAPABILITIES.map(({ icon: Icon, label, desc, color, stage }) => (
        <div key={label} className="card p-5 opacity-50">
          <Icon className="w-5 h-5 mb-3" style={{ color }} />
          <p className="text-sm font-medium text-slate-200">{label}</p>
          <p className="text-xs text-slate-500 mt-1 leading-relaxed">{desc}</p>
          <p className="section-label mt-3">{stage}</p>
        </div>
      ))}
    </div>
  </div>
);
