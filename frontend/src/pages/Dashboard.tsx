import React from 'react';
import {
  TrendingUp,
  AlertTriangle,
  Users,
  Activity,
  ArrowRight,
  Database,
  GitFork,
  ShieldAlert,
  Clock,
} from 'lucide-react';
import { Link } from 'react-router-dom';
import { StatCard, SectionHeader, StatusBadge, EmptyState } from '@/components/ui';
import { useApi } from '@/hooks/useApi';
import { api } from '@/services/api';
import { formatNumber } from '@/utils';
import type { PlatformStats } from '@/types';

/* ── Workflow step ─────────────────────────────────────────────── */
interface WorkflowStepProps {
  number: number;
  label: string;
  description: string;
  status: 'complete' | 'active' | 'pending';
}

const WorkflowStep: React.FC<WorkflowStepProps> = ({ number, label, description, status }) => {
  const styles = {
    complete: { bg: 'rgba(16,185,129,0.1)', border: 'rgba(16,185,129,0.3)', color: '#34d399' },
    active:   { bg: 'rgba(59,130,246,0.1)', border: 'rgba(59,130,246,0.3)', color: '#60a5fa' },
    pending:  { bg: '#1e2d4a',              border: '#263354',               color: '#475569' },
  };
  const s = styles[status];

  return (
    <div className={`flex gap-4 items-start ${status === 'pending' ? 'opacity-40' : ''}`}>
      <div
        className="flex-shrink-0 w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold"
        style={{ backgroundColor: s.bg, border: `1px solid ${s.border}`, color: s.color }}
      >
        {number}
      </div>
      <div>
        <p className="text-sm font-medium text-slate-200">{label}</p>
        <p className="text-xs text-slate-500 mt-0.5">{description}</p>
      </div>
    </div>
  );
};

/* ── Quick action card ──────────────────────────────────────────── */
interface QuickAction {
  label: string;
  description: string;
  icon: React.ElementType;
  path: string;
  iconColor: string;
  bg: string;
  border: string;
}

const QUICK_ACTIONS: QuickAction[] = [
  {
    label: 'Upload Dataset',
    description: 'Start transaction analysis',
    icon: Database,
    path: '/analysis',
    iconColor: '#60a5fa',
    bg: 'rgba(59,130,246,0.08)',
    border: 'rgba(59,130,246,0.2)',
  },
  {
    label: 'Money Flow',
    description: 'Trace transaction routes',
    icon: GitFork,
    path: '/money-flow',
    iconColor: '#22d3ee',
    bg: 'rgba(6,182,212,0.08)',
    border: 'rgba(6,182,212,0.2)',
  },
  {
    label: 'Risk Intelligence',
    description: 'Review suspicious activity',
    icon: ShieldAlert,
    path: '/risk',
    iconColor: '#fbbf24',
    bg: 'rgba(245,158,11,0.08)',
    border: 'rgba(245,158,11,0.2)',
  },
];

const STAGE_LABELS = ['1', '2', '3', '4', '5', '6'];

/* ── Page ───────────────────────────────────────────────────────── */
export const Dashboard: React.FC = () => {
  const { data: stats, loading, error } = useApi<PlatformStats>(
    () => api.analysis.getStats() as Promise<PlatformStats>,
  );

  return (
    <div className="space-y-6">
      <SectionHeader
        title="Intelligence Dashboard"
        subtitle="Financial investigation platform overview"
        actions={<StatusBadge status="operational" label="System Ready" />}
      />

      {/* Platform notice */}
      <div className="card p-4" style={{ borderLeft: '2px solid #3b82f6' }}>
        <div className="flex items-start gap-3">
          <Activity className="w-4 h-4 text-blue-400 mt-0.5 flex-shrink-0" />
          <div>
            <p className="text-sm font-medium text-slate-200">Platform Initialised — Stage 1 Complete</p>
            <p className="text-xs text-slate-400 mt-1">
              NyxTrace foundation is operational. Upload a transaction dataset via the Analysis workspace to
              begin investigation. ML pipeline, graph analytics, and risk scoring will be available in
              subsequent development stages.
            </p>
          </div>
        </div>
      </div>

      {/* API error notice */}
      {error && (
        <div className="card p-4" style={{ borderLeft: '2px solid #ef4444' }}>
          <p className="text-xs text-red-400">
            Backend unreachable — ensure the FastAPI server is running on port 8000.
          </p>
        </div>
      )}

      {/* KPI row */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          label="Transactions Analyzed"
          value={loading ? '—' : formatNumber(stats?.total_transactions_analyzed)}
          subtext="Upload a dataset to begin"
          icon={<TrendingUp className="w-4 h-4" />}
        />
        <StatCard
          label="Suspicious Detected"
          value={loading ? '—' : formatNumber(stats?.suspicious_transactions_detected)}
          subtext="Requires ML pipeline (Stage 3)"
          icon={<AlertTriangle className="w-4 h-4" />}
          valueClassName="text-slate-400"
        />
        <StatCard
          label="Accounts Flagged"
          value={loading ? '—' : formatNumber(stats?.accounts_flagged)}
          subtext="Requires graph analysis (Stage 4)"
          icon={<Users className="w-4 h-4" />}
          valueClassName="text-slate-400"
        />
        <StatCard
          label="Active Investigations"
          value={loading ? '—' : (stats?.active_investigations ?? 0)}
          subtext="Investigation tracking"
          icon={<Activity className="w-4 h-4" />}
        />
      </div>

      {/* Main grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Investigation workflow */}
        <div className="card p-5 lg:col-span-2">
          <p className="section-label mb-5">Investigation Workflow</p>
          <div className="space-y-4">
            <WorkflowStep number={1} label="Dataset Upload"       description="Upload transaction CSV for processing"             status="active"  />
            <div className="ml-3.5 w-px h-3" style={{ backgroundColor: '#263354' }} />
            <WorkflowStep number={2} label="Data Preprocessing"  description="Validation, cleaning, and feature extraction"      status="pending" />
            <div className="ml-3.5 w-px h-3" style={{ backgroundColor: '#263354' }} />
            <WorkflowStep number={3} label="ML Detection"        description="Suspicious transaction classification"              status="pending" />
            <div className="ml-3.5 w-px h-3" style={{ backgroundColor: '#263354' }} />
            <WorkflowStep number={4} label="Graph Intelligence"  description="Transaction network construction and analysis"     status="pending" />
            <div className="ml-3.5 w-px h-3" style={{ backgroundColor: '#263354' }} />
            <WorkflowStep number={5} label="Risk Analysis"       description="Risk scoring and pattern identification"           status="pending" />
            <div className="ml-3.5 w-px h-3" style={{ backgroundColor: '#263354' }} />
            <WorkflowStep number={6} label="Investigation Report" description="Summary and downloadable report generation"       status="pending" />
          </div>
        </div>

        {/* Quick access */}
        <div className="card p-5">
          <p className="section-label mb-4">Quick Access</p>
          <div className="space-y-3">
            {QUICK_ACTIONS.map(({ label, description, icon: Icon, path, iconColor, bg, border }) => (
              <Link
                key={path}
                to={path}
                className="flex items-center gap-3 p-3 rounded-lg transition-opacity hover:opacity-80"
                style={{ backgroundColor: bg, border: `1px solid ${border}` }}
              >
                <div className="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0"
                  style={{ backgroundColor: bg }}>
                  <Icon className="w-4 h-4" style={{ color: iconColor }} />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-slate-200">{label}</p>
                  <p className="text-xs text-slate-500">{description}</p>
                </div>
                <ArrowRight className="w-3.5 h-3.5 text-slate-500 flex-shrink-0" />
              </Link>
            ))}
          </div>

          <div className="mt-5 pt-4" style={{ borderTop: '1px solid #1e2d4a' }}>
            <p className="section-label mb-3">Recent Activity</p>
            <EmptyState
              icon={<Clock className="w-6 h-6" />}
              title="No Activity Yet"
              description="Analysis history will appear here after your first dataset upload."
            />
          </div>
        </div>
      </div>

      {/* Stage progress */}
      <div className="card p-4">
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div className="flex items-center gap-3">
            <p className="section-label">Development Stage</p>
            <div className="flex items-center gap-1.5">
              {STAGE_LABELS.map(s => (
                <div
                  key={s}
                  className="w-6 h-1.5 rounded-full"
                  style={{ backgroundColor: s === '1' ? '#3b82f6' : '#1e2d4a' }}
                  title={`Stage ${s}`}
                />
              ))}
            </div>
          </div>
          <span className="text-xs text-blue-400 font-medium">Stage 1 of 6 — Foundation</span>
        </div>
      </div>
    </div>
  );
};
