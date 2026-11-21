import React from 'react';
import { cn } from '@/utils';

interface StatusBadgeProps {
  status: 'operational' | 'warning' | 'error' | 'pending' | 'inactive';
  label?: string;
  className?: string;
}

const statusConfig = {
  operational: { dot: 'bg-emerald-400', text: 'text-emerald-400', label: 'Operational' },
  warning:     { dot: 'bg-amber-400',   text: 'text-amber-400',   label: 'Warning'     },
  error:       { dot: 'bg-red-400',     text: 'text-red-400',     label: 'Error'       },
  pending:     { dot: 'bg-blue-400 animate-pulse', text: 'text-blue-400', label: 'Pending' },
  inactive:    { dot: 'bg-slate-500',   text: 'text-slate-500',   label: 'Inactive'    },
};

export const StatusBadge: React.FC<StatusBadgeProps> = ({ status, label, className }) => {
  const config = statusConfig[status];
  return (
    <span className={cn('inline-flex items-center gap-1.5 text-xs font-medium', config.text, className)}>
      <span className={cn('w-1.5 h-1.5 rounded-full flex-shrink-0', config.dot)} />
      {label ?? config.label}
    </span>
  );
};
