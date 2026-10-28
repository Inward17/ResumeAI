/**
 * Small shared building blocks so every page looks the same.
 */
import React from 'react';
import { cn } from '../lib/utils';
import { STATUS_STYLES, JOB_STATUS_STYLES } from '../lib/statuses';

export const Card = ({ className, children, ...props }) => (
  <div className={cn('rounded-2xl border border-slate-200 bg-white shadow-sm', className)} {...props}>
    {children}
  </div>
);

export const CardHeader = ({ title, subtitle, action, className }) => (
  <div className={cn('flex items-start justify-between gap-4 border-b border-slate-100 px-5 py-4 md:px-6', className)}>
    <div className="min-w-0">
      <h2 className="text-base font-bold text-slate-900">{title}</h2>
      {subtitle && <p className="mt-0.5 text-sm text-slate-500">{subtitle}</p>}
    </div>
    {action && <div className="shrink-0">{action}</div>}
  </div>
);

export const PageHeader = ({ eyebrow, title, description, action }) => (
  <div className="mb-6 flex flex-col gap-4 md:mb-8 md:flex-row md:items-end md:justify-between">
    <div className="min-w-0">
      {eyebrow && <p className="mb-1 text-xs font-bold uppercase tracking-widest text-brand-accent">{eyebrow}</p>}
      <h1 className="text-2xl font-extrabold tracking-tight text-slate-900 md:text-[1.75rem]">{title}</h1>
      {description && <p className="mt-1 max-w-2xl text-sm text-slate-600">{description}</p>}
    </div>
    {action && <div className="shrink-0">{action}</div>}
  </div>
);

export const PageContainer = ({ className, children }) => (
  <div className={cn('mx-auto w-full max-w-7xl p-4 pb-24 md:p-8', className)}>{children}</div>
);

const pill = 'inline-flex items-center whitespace-nowrap rounded-full px-2.5 py-0.5 text-[11px] font-semibold ring-1 ring-inset';

export const StatusPill = ({ status, className }) => (
  <span className={cn(pill, STATUS_STYLES[status] || 'bg-slate-100 text-slate-700 ring-slate-200', className)}>
    {status}
  </span>
);

export const JobStatusPill = ({ status }) => (
  <span className={cn(pill, 'gap-1.5 uppercase tracking-wide', JOB_STATUS_STYLES[status] || JOB_STATUS_STYLES.Closed)}>
    {status === 'Active' && <span className="h-1.5 w-1.5 rounded-full bg-cyan-500" aria-hidden="true" />}
    {status}
  </span>
);

/** Colour band for a 0–100 score */
export const scoreTone = (value, strong = 75) =>
  value >= strong ? 'text-emerald-700 bg-emerald-50 ring-emerald-200'
    : value >= 50 ? 'text-indigo-700 bg-indigo-50 ring-indigo-200'
      : 'text-amber-800 bg-amber-50 ring-amber-200';

export const ScoreBadge = ({ value, label = 'match', strong }) => (
  <span className={cn(pill, scoreTone(value, strong))}>{value}% {label}</span>
);

export const ScoreRing = ({ value, label, sublabel, size = 56, stroke = 5 }) => {
  const r = (size - stroke) / 2;
  const circ = 2 * Math.PI * r;
  const shown = value == null ? 0 : Math.max(0, Math.min(100, value));
  return (
    <div className="flex flex-col items-center gap-1 text-center">
      <div className="relative" style={{ width: size, height: size }}>
        <svg width={size} height={size} className="-rotate-90" aria-hidden="true">
          <circle cx={size / 2} cy={size / 2} r={r} fill="none" strokeWidth={stroke} className="stroke-brand-soft" />
          <circle
            cx={size / 2} cy={size / 2} r={r} fill="none" strokeWidth={stroke} strokeLinecap="round"
            className="stroke-brand-accent transition-[stroke-dasharray] duration-500"
            strokeDasharray={`${(shown / 100) * circ} ${circ}`}
          />
        </svg>
        <span className="absolute inset-0 flex items-center justify-center text-xs font-extrabold text-brand">
          {value == null ? '—' : `${shown}%`}
        </span>
      </div>
      {label && <span className="text-xs font-semibold text-slate-700">{label}</span>}
      {sublabel && <span className="text-[11px] leading-tight text-slate-500">{sublabel}</span>}
    </div>
  );
};

export const Initials = ({ name, className }) => (
  <div
    className={cn('flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-brand text-xs font-bold text-white', className)}
    aria-hidden="true"
  >
    {(name || '?').trim().charAt(0).toUpperCase()}
  </div>
);

export const EmptyState = ({ icon: Icon, title, description, action, className }) => (
  <div className={cn('flex flex-col items-center px-6 py-14 text-center', className)}>
    {Icon && (
      <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-2xl bg-brand-light">
        <Icon className="h-6 w-6 text-brand-accent" aria-hidden="true" />
      </div>
    )}
    <p className="font-semibold text-slate-900">{title}</p>
    {description && <p className="mt-1 max-w-md text-sm text-slate-600">{description}</p>}
    {action && <div className="mt-5">{action}</div>}
  </div>
);

export const ComingSoon = ({ className }) => (
  <span className={cn('inline-flex shrink-0 items-center whitespace-nowrap rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-slate-600', className)}>
    Coming soon
  </span>
);

const buttonBase = 'inline-flex items-center justify-center gap-2 rounded-xl px-4 py-2.5 text-sm font-semibold transition-colors disabled:cursor-not-allowed disabled:opacity-50';

export const PrimaryButton = ({ className, ...props }) => (
  <button type="button" className={cn(buttonBase, 'bg-brand text-white shadow-sm hover:bg-brand-dark', className)} {...props} />
);

export const SecondaryButton = ({ className, ...props }) => (
  <button type="button" className={cn(buttonBase, 'border border-slate-200 bg-white text-slate-700 hover:bg-slate-50', className)} {...props} />
);

export const formatDate = (value) => {
  if (!value) return '—';
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? '—' : d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
};
