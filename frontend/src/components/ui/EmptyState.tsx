import React from 'react';
import { cn } from '@/utils';

interface EmptyStateProps {
  icon: React.ReactNode;
  title: string;
  description: string;
  action?: React.ReactNode;
  className?: string;
}

export const EmptyState: React.FC<EmptyStateProps> = ({
  icon,
  title,
  description,
  action,
  className,
}) => (
  <div className={cn('empty-state', className)}>
    <div
      className="w-16 h-16 rounded-2xl flex items-center justify-center mb-5 text-slate-500"
      style={{ backgroundColor: '#1a2440', border: '1px solid #263354' }}
    >
      {icon}
    </div>
    <h3 className="text-base font-semibold text-slate-200 mb-2">{title}</h3>
    <p className="text-sm text-slate-500 max-w-sm leading-relaxed">{description}</p>
    {action && <div className="mt-6">{action}</div>}
  </div>
);
