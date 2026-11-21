import React from 'react';
import { FileText, Download, Info, Search } from 'lucide-react';
import { SectionHeader, EmptyState } from '@/components/ui';

const REPORT_TYPES = [
  {
    title: 'Transaction Summary',
    desc:  'Full dataset statistics and preprocessing overview.',
    stage: 'Stage 2',
  },
  {
    title: 'ML Detection Report',
    desc:  'Suspicious transaction classifications with confidence scores and SHAP explanations.',
    stage: 'Stage 3',
  },
  {
    title: 'Network Analysis Report',
    desc:  'Graph topology, pattern findings, and high-risk cluster summaries.',
    stage: 'Stage 4',
  },
  {
    title: 'Investigation Brief',
    desc:  'Complete investigation summary combining all stages, ready for analyst review.',
    stage: 'Stage 5',
  },
  {
    title: 'Compliance Export',
    desc:  'Structured export formatted for Suspicious Activity Report (SAR) preparation.',
    stage: 'Stage 5',
  },
  {
    title: 'Risk Dashboard PDF',
    desc:  'Downloadable risk scorecard and visualisation snapshot.',
    stage: 'Stage 5',
  },
];

export const Reports: React.FC = () => (
  <div className="space-y-6">
    <SectionHeader
      title="Investigation Reports"
      subtitle="Analysis summaries and downloadable investigation documentation"
      actions={
        <button disabled className="btn-primary opacity-40 cursor-not-allowed">
          <Download className="w-4 h-4" />
          Export Report
        </button>
      }
    />

    {/* Stage notice */}
    <div className="card p-4" style={{ borderLeft: '2px solid #60a5fa' }}>
      <div className="flex items-start gap-3">
        <Info className="w-4 h-4 text-blue-400 mt-0.5 flex-shrink-0" />
        <div>
          <p className="text-sm font-medium text-blue-300">Stage 5 Feature</p>
          <p className="text-xs text-slate-400 mt-1">
            Automated investigation report generation, risk summaries, and downloadable documentation
            will be implemented in Stage 5 — Investigation Intelligence. Report formats and export
            capabilities are designed with AML analyst workflows in mind.
          </p>
        </div>
      </div>
    </div>

    {/* Search + filter bar */}
    <div className="card p-4">
      <div className="flex items-center gap-3">
        <div className="flex-1 relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-600" />
          <input
            type="text"
            placeholder="Search reports by name, date, or investigation ID…"
            disabled
            className="w-full rounded-lg py-2 pl-10 pr-4 text-sm text-slate-500 cursor-not-allowed"
            style={{ backgroundColor: '#141d35', border: '1px solid #1e2d4a' }}
          />
        </div>
        <button disabled className="btn-secondary opacity-40 cursor-not-allowed text-sm">
          Filter
        </button>
        <button disabled className="btn-secondary opacity-40 cursor-not-allowed text-sm">
          Sort
        </button>
      </div>
    </div>

    {/* Reports listing */}
    <div className="card p-5">
      <div
        className="flex items-center justify-between pb-4 mb-4"
        style={{ borderBottom: '1px solid #1e2d4a' }}
      >
        <p className="section-label">Investigation Reports</p>
        <span className="text-xs text-slate-600">0 reports</span>
      </div>
      <EmptyState
        icon={<FileText className="w-7 h-7" />}
        title="No Reports Generated"
        description="Investigation reports are produced after a complete pipeline run. Complete dataset upload (Stage 2), ML detection (Stage 3), and graph analysis (Stage 4) to generate your first report."
      />
    </div>

    {/* Report type catalogue */}
    <div>
      <p className="section-label mb-3 px-1">Available Report Types</p>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {REPORT_TYPES.map(({ title, desc, stage }) => (
          <div key={title} className="card p-5 opacity-50">
            <FileText className="w-5 h-5 text-blue-400 mb-3" />
            <p className="text-sm font-medium text-slate-200">{title}</p>
            <p className="text-xs text-slate-500 mt-1 leading-relaxed">{desc}</p>
            <p className="section-label mt-3">Available in {stage}</p>
          </div>
        ))}
      </div>
    </div>
  </div>
);
