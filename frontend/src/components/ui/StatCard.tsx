import React from 'react';
import { cn } from '@/utils';

interface StatCardProps {
  label: string;
  value: React.ReactNode;
  subtext?: string;
  icon?: React.ReactNode;
  className?: string;
  valueClassName?: string;
}

export const StatCard: React.FC<StatCardProps> = ({
  label,
  value,
  subtext,
  icon,
  className,
  valueClassName,
}) => (
  <div className={cn('stat-card', className)}>
    <div className="flex items-start justify-between">
      <span className="section-label">{label}</span>
      {icon && <span className="text-slate-500 mt-0.5">{icon}</span>}
    </div>
    <div className={cn('text-2xl font-semibold text-slate-100 mt-1', valueClassName)}>
      {value}
    </div>
    {subtext && <p className="text-xs text-slate-500 mt-1">{subtext}</p>}
  </div>
);
