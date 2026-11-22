import React, { useEffect, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import {
  LayoutDashboard,
  BarChart3,
  GitFork,
  ShieldAlert,
  FileText,
  Info,
  ChevronLeft,
  ChevronRight,
  Activity,
  Zap,
  BriefcaseBusiness,
} from 'lucide-react';
import { cn } from '@/utils';
import { StatusBadge } from '@/components/ui';
import { api } from '@/services/api';
import type { GraphStatus, MLStatus } from '@/types';

const NAV_ITEMS = [
  { label: 'Dashboard',            path: '/',           icon: LayoutDashboard },
  { label: 'Transaction Analysis', path: '/analysis',   icon: BarChart3       },
  { label: 'Money Flow',           path: '/money-flow', icon: GitFork         },
  { label: 'Risk Intelligence',    path: '/risk',       icon: ShieldAlert     },
  { label: 'Investigation Cases',  path: '/cases',      icon: BriefcaseBusiness },
  { label: 'Reports',              path: '/reports',    icon: FileText        },
  { label: 'About NyxTrace',       path: '/about',      icon: Info            },
];

interface AppLayoutProps {
  children: React.ReactNode;
}

export const AppLayout: React.FC<AppLayoutProps> = ({ children }) => {
  const location = useLocation();
  const [collapsed, setCollapsed] = useState(false);
  const [mlStatus, setMlStatus] = useState<MLStatus | null>(null);
  const [graphStatus, setGraphStatus] = useState<GraphStatus | null>(null);
  const [backendAvailable, setBackendAvailable] = useState(false);

  useEffect(() => {
    let active = true;
    const refresh = async () => {
      try {
        const [health, ml, graph] = await Promise.all([
          api.health.check(),
          api.ml.status(),
          api.graph.status(),
        ]);
        if (!active) return;
        setBackendAvailable(Boolean(health));
        setMlStatus(ml.data ?? null);
        setGraphStatus(graph.data ?? null);
      } catch {
        if (active) {
          setBackendAvailable(false);
          setMlStatus(null);
          setGraphStatus(null);
        }
      }
    };
    void refresh();
    const interval = window.setInterval(() => void refresh(), 5000);
    return () => {
      active = false;
      window.clearInterval(interval);
    };
  }, []);

  return (
    <div className="flex h-screen overflow-hidden" style={{ backgroundColor: '#0a0e1a' }}>
      {/* ── Sidebar ── */}
      <aside
        className={cn(
          'flex flex-col flex-shrink-0 transition-all duration-200',
          collapsed ? 'w-16' : 'w-64',
        )}
        style={{ backgroundColor: '#0f1629', borderRight: '1px solid #1e2d4a' }}
      >
        {/* Logo */}
        <div
          className={cn(
            'flex items-center h-16 px-4 flex-shrink-0',
            collapsed ? 'justify-center' : 'gap-3',
          )}
          style={{ borderBottom: '1px solid #1e2d4a' }}
        >
          <div
            className="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0"
            style={{ background: 'linear-gradient(135deg,#2563eb,#06b6d4)' }}
          >
            <Activity className="w-4 h-4 text-white" />
          </div>
          {!collapsed && (
            <div>
              <p className="text-sm font-bold text-slate-100 tracking-tight leading-none">
                NyxTrace
              </p>
              <p className="text-slate-500 mt-0.5" style={{ fontSize: '0.6rem', letterSpacing: '0.08em' }}>
                FINANCIAL INTELLIGENCE
              </p>
            </div>
          )}
        </div>

        {/* Nav */}
        <nav className="flex-1 overflow-y-auto py-3 px-2">
          {!collapsed && (
            <p className="px-2 mb-3 section-label">Navigation</p>
          )}
          <ul className="space-y-0.5">
            {NAV_ITEMS.map(({ label, path, icon: Icon }) => {
              const active = location.pathname === path;
              return (
                <li key={path}>
                  <Link
                    to={path}
                    title={collapsed ? label : undefined}
                    className={cn(
                      'flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors duration-150',
                      active
                        ? 'text-blue-400'
                        : 'text-slate-400 hover:text-slate-200 hover:bg-[#1a2440]',
                      collapsed && 'justify-center px-2',
                    )}
                    style={
                      active
                        ? { backgroundColor: 'rgba(59,130,246,0.1)', border: '1px solid rgba(59,130,246,0.2)' }
                        : undefined
                    }
                  >
                    <Icon
                      className={cn(
                        'flex-shrink-0',
                        collapsed ? 'w-5 h-5' : 'w-4 h-4',
                        active ? 'text-blue-400' : 'text-slate-500',
                      )}
                    />
                    {!collapsed && <span className="truncate">{label}</span>}
                    {!collapsed && active && (
                      <span className="ml-auto w-1.5 h-1.5 rounded-full bg-blue-400 flex-shrink-0" />
                    )}
                  </Link>
                </li>
              );
            })}
          </ul>
        </nav>

        {/* System Status */}
        {!collapsed && (
          <div className="px-4 py-3" style={{ borderTop: '1px solid #1e2d4a' }}>
            <p className="section-label mb-2">System Status</p>
            <div className="space-y-1.5">
              <div className="flex items-center justify-between">
                <span className="text-xs text-slate-500">Backend API</span>
                <StatusBadge status={backendAvailable ? 'operational' : 'inactive'} label={backendAvailable ? 'Operational' : 'Unavailable'} />
              </div>
              <div className="flex items-center justify-between">
                <span className="text-xs text-slate-500">ML Pipeline</span>
                <StatusBadge
                  status={mlStatus?.status === 'completed' ? 'operational' : 'inactive'}
                  label={mlStatus?.status === 'completed' ? 'Ready' : mlStatus?.status === 'stale' ? 'Stale' : mlStatus?.status === 'running' ? 'Training' : 'Not Trained'}
                />
              </div>
              <div className="flex items-center justify-between">
                <span className="text-xs text-slate-500">Graph Engine</span>
                <StatusBadge
                  status={graphStatus?.status === 'ready' ? 'operational' : 'inactive'}
                  label={graphStatus?.status === 'ready' ? 'Ready' : graphStatus?.status === 'stale' ? 'Stale' : graphStatus?.status === 'running' ? 'Building' : 'Not Built'}
                />
              </div>
            </div>
          </div>
        )}

        {/* Collapse toggle */}
        <button
          onClick={() => setCollapsed(c => !c)}
          className="flex items-center justify-center h-10 text-slate-500 hover:text-slate-300 hover:bg-[#1a2440] transition-colors"
          style={{ borderTop: '1px solid #1e2d4a' }}
          aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        >
          {collapsed ? <ChevronRight className="w-4 h-4" /> : <ChevronLeft className="w-4 h-4" />}
        </button>
      </aside>

      {/* ── Main area ── */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Top bar */}
        <header
          className="h-16 flex items-center px-6 gap-4 flex-shrink-0"
          style={{ backgroundColor: '#0f1629', borderBottom: '1px solid #1e2d4a' }}
        >
          <div className="flex-1" />
          <div className="flex items-center gap-2 text-xs text-slate-500">
            <Zap className="w-3 h-3 text-blue-500" />
            <span>Stage 1 — Foundation</span>
          </div>
          <div className="w-px h-5" style={{ backgroundColor: '#263354' }} />
          <div
            className="w-7 h-7 rounded-full flex items-center justify-center"
            style={{ background: 'linear-gradient(135deg,#2563eb,#06b6d4)' }}
          >
            <span className="text-white font-bold" style={{ fontSize: '0.6rem' }}>NT</span>
          </div>
        </header>

        {/* Page content */}
        <main
          className="flex-1 overflow-y-auto"
          style={{
            backgroundImage:
              'linear-gradient(rgba(59,130,246,0.03) 1px,transparent 1px),' +
              'linear-gradient(90deg,rgba(59,130,246,0.03) 1px,transparent 1px)',
            backgroundSize: '32px 32px',
          }}
        >
          <div className="max-w-7xl mx-auto p-6">{children}</div>
        </main>
      </div>
    </div>
  );
};
