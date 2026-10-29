/**
 * Shared building blocks so every page looks and behaves the same.
 * Colours come from the theme tokens in index.css (light + dark).
 */
import React, { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowLeft, ChevronDown, Search, X } from 'lucide-react';
import { cn } from '../lib/utils';
import { CANDIDATE_STATUSES, STATUS_STYLES, JOB_STATUS_STYLES } from '../lib/statuses';

/* ── Layout ─────────────────────────────────────────────────────────── */

export const Card = ({ className, children, ...props }) => (
  <div className={cn('rounded-lg border border-line bg-surface', className)} {...props}>
    {children}
  </div>
);

export const CardHeader = ({ title, subtitle, action, className }) => (
  <div className={cn('flex items-center justify-between gap-4 border-b border-line px-5 py-3.5', className)}>
    <div className="min-w-0">
      <h2 className="text-sm font-semibold text-ink">{title}</h2>
      {subtitle && <p className="mt-0.5 text-xs text-ink-3">{subtitle}</p>}
    </div>
    {action && <div className="shrink-0">{action}</div>}
  </div>
);

export const PageContainer = ({ className, children }) => (
  <div className={cn('mx-auto w-full max-w-7xl px-4 py-6 pb-24 md:px-8 md:py-8 md:pb-12', className)}>{children}</div>
);

export const BackLink = ({ to, children }) => (
  <Link to={to} className="mb-3 inline-flex items-center gap-1.5 rounded-md text-sm font-medium text-ink-3 transition-colors hover:text-ink">
    <ArrowLeft className="h-4 w-4" aria-hidden="true" /> {children}
  </Link>
);

export const PageHeader = ({ title, description, action, back, meta }) => (
  <div className="mb-6 md:mb-8">
    {back && <BackLink to={back.to}>{back.label}</BackLink>}
    <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
      <div className="min-w-0">
        <h1 className="font-serif text-[2rem] leading-[1.1] tracking-[-0.01em] text-ink md:text-[2.6rem]">{title}</h1>
        {description && <p className="mt-1 max-w-2xl text-sm text-ink-3">{description}</p>}
        {meta && <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1.5 text-sm text-ink-3">{meta}</div>}
      </div>
      {action && <div className="flex shrink-0 flex-wrap gap-2">{action}</div>}
    </div>
  </div>
);

/* ── Buttons ────────────────────────────────────────────────────────── */

const BUTTON_VARIANTS = {
  primary: 'bg-btn text-btn-fg hover:bg-btn-hover',
  secondary: 'border border-line-strong bg-surface text-ink hover:bg-subtle',
  ghost: 'text-ink-2 hover:bg-subtle hover:text-ink',
  danger: 'bg-danger text-white hover:opacity-90 dark:text-canvas',
  'danger-outline': 'border border-line-strong bg-surface text-danger hover:border-danger/40 hover:bg-danger-soft',
};

const BUTTON_SIZES = {
  sm: 'h-8 gap-1.5 px-3 text-xs',
  md: 'h-9 gap-2 px-3.5 text-sm',
  lg: 'h-10 gap-2 px-4 text-sm',
};

export const buttonClass = (variant = 'primary', size = 'md') => cn(
  'inline-flex shrink-0 items-center justify-center whitespace-nowrap rounded-md font-medium transition-colors',
  'disabled:pointer-events-none disabled:opacity-50 [&_svg]:h-4 [&_svg]:w-4 [&_svg]:shrink-0',
  BUTTON_VARIANTS[variant], BUTTON_SIZES[size],
);

export const Button = React.forwardRef(({ variant, size, className, type = 'button', ...props }, ref) => (
  <button ref={ref} type={type} className={cn(buttonClass(variant, size), className)} {...props} />
));
Button.displayName = 'Button';

export const IconButton = React.forwardRef(({ label, className, children, ...props }, ref) => (
  <button
    ref={ref}
    type="button"
    aria-label={label}
    title={label}
    className={cn('inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-ink-3 transition-colors hover:bg-subtle hover:text-ink [&_svg]:h-4 [&_svg]:w-4', className)}
    {...props}
  >
    {children}
  </button>
));
IconButton.displayName = 'IconButton';

/* ── Form fields ────────────────────────────────────────────────────── */

export const inputClass = cn(
  'h-9 w-full rounded-md border border-line-strong bg-surface px-3 text-sm text-ink outline-none transition',
  'placeholder:text-ink-3 focus:border-primary focus:ring-[3px] focus:ring-primary/15',
  'disabled:cursor-not-allowed disabled:bg-subtle disabled:text-ink-3',
);

export const Field = ({ label, htmlFor, hint, error, required, optional, className, children }) => (
  <div className={className}>
    {label && (
      <label htmlFor={htmlFor} className="mb-1.5 block text-sm font-medium text-ink-2">
        {label}
        {required && <span className="ml-0.5 text-danger" aria-hidden="true">*</span>}
        {optional && <span className="ml-1.5 font-normal text-ink-3">Optional</span>}
      </label>
    )}
    {children}
    {error ? <p className="mt-1.5 text-xs text-danger">{error}</p> : hint && <p className="mt-1.5 text-xs text-ink-3">{hint}</p>}
  </div>
);

export const Input = React.forwardRef(({ className, ...props }, ref) => (
  <input ref={ref} className={cn(inputClass, className)} {...props} />
));
Input.displayName = 'Input';

export const Select = ({ className, children, ...props }) => (
  <select className={cn(inputClass, 'cursor-pointer pr-8', className)} {...props}>{children}</select>
);

export const Textarea = ({ className, ...props }) => (
  <textarea className={cn(inputClass, 'h-auto min-h-[7rem] resize-y py-2 leading-relaxed', className)} {...props} />
);

export const SearchInput = ({ value, onChange, placeholder, label, className }) => (
  <div className={cn('relative', className)}>
    <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-3" aria-hidden="true" />
    <input
      type="search"
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder={placeholder}
      aria-label={label || placeholder}
      className={cn(inputClass, 'pl-9 pr-8 [&::-webkit-search-cancel-button]:hidden')}
    />
    {value && (
      <button type="button" onClick={() => onChange('')} aria-label="Clear search"
        className="absolute right-2 top-1/2 -translate-y-1/2 rounded p-0.5 text-ink-3 hover:text-ink">
        <X className="h-3.5 w-3.5" aria-hidden="true" />
      </button>
    )}
  </div>
);

/** Segmented filter with optional counts (tabs that filter one list) */
export const Segmented = ({ items, value, onChange, label, className }) => (
  <div className={cn('no-scrollbar inline-flex max-w-full gap-0.5 overflow-x-auto rounded-md border border-line bg-subtle p-0.5', className)}
    role="tablist" aria-label={label}>
    {items.map(({ id, label: text, count }) => {
      const active = value === id;
      return (
        <button
          key={id}
          type="button"
          role="tab"
          aria-selected={active}
          onClick={() => onChange(id)}
          className={cn(
            'inline-flex items-center gap-1.5 whitespace-nowrap rounded px-3 py-1.5 text-sm font-medium transition-colors',
            active ? 'bg-surface text-ink shadow-sm' : 'text-ink-3 hover:text-ink',
          )}
        >
          {text}
          {count != null && (
            <span className={cn('rounded px-1.5 text-xs tabular-nums', active ? 'bg-subtle text-ink-2' : 'text-ink-3')}>{count}</span>
          )}
        </button>
      );
    })}
  </div>
);

/* ── Status & tags ──────────────────────────────────────────────────── */

const Dot = ({ className }) => <span className={cn('h-2 w-2 shrink-0 rounded-full', className)} aria-hidden="true" />;

export const StatusPill = ({ status, className }) => (
  <span className={cn('inline-flex items-center gap-2 whitespace-nowrap text-sm text-ink-2', className)}>
    <Dot className={STATUS_STYLES[status] || STATUS_STYLES['Under Review']} />{status}
  </span>
);

/** Status as a quiet select with a coloured dot — one click to move a candidate */
export const StatusSelect = ({ candidate, onChange }) => (
  <div className="relative inline-flex" onClick={(e) => e.stopPropagation()}>
    <Dot className={cn('pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2', STATUS_STYLES[candidate.status])} />
    <select
      value={candidate.status}
      onChange={(e) => onChange(candidate.id, e.target.value)}
      aria-label={`Status for ${candidate.name}`}
      className="h-8 cursor-pointer appearance-none rounded-md border border-transparent bg-transparent py-0 pl-7 pr-7 text-sm text-ink-2 outline-none transition hover:border-line-strong hover:bg-surface focus:border-primary focus:bg-surface focus:ring-[3px] focus:ring-primary/15"
    >
      {CANDIDATE_STATUSES.map((st) => <option key={st} value={st} className="bg-surface text-ink">{st}</option>)}
    </select>
    <ChevronDown className="pointer-events-none absolute right-2 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-ink-3" aria-hidden="true" />
  </div>
);

export const JobStatusPill = ({ status }) => (
  <span className="inline-flex items-center gap-1.5 whitespace-nowrap text-xs font-medium text-ink-3">
    <Dot className={cn('h-1.5 w-1.5', JOB_STATUS_STYLES[status] || JOB_STATUS_STYLES.Closed)} />{status}
  </span>
);

export const Tag = ({ children, tone = 'neutral', className }) => (
  <span className={cn(
    'inline-flex items-center whitespace-nowrap rounded-md px-1.5 py-0.5 text-xs font-medium',
    tone === 'primary' ? 'bg-primary-soft text-primary-soft-fg' : 'bg-subtle text-ink-2',
    className,
  )}>
    {children}
  </span>
);

export const ComingSoon = ({ className }) => (
  <span className={cn('inline-flex shrink-0 items-center whitespace-nowrap rounded-full bg-subtle px-2 py-0.5 text-[11px] font-medium text-ink-3', className)}>
    Coming soon
  </span>
);

/* ── Scores ─────────────────────────────────────────────────────────── */

/** 'good' at or above `strong`, 'fair' from 50, else 'low' */
export const scoreLevel = (value, strong = 75) => (value == null ? 'none' : value >= strong ? 'good' : value >= 50 ? 'fair' : 'low');

const LEVEL_TEXT = { good: 'text-success', fair: 'text-ink', low: 'text-warning', none: 'text-ink-3' };
const LEVEL_BAR = { good: 'bg-success', fair: 'bg-ink-2', low: 'bg-warning', none: 'bg-line-strong' };
const LEVEL_STROKE = { good: 'stroke-success', fair: 'stroke-ink-2', low: 'stroke-warning', none: 'stroke-line-strong' };

/** Number + thin bar; used in tables and cards */
export const ScoreBar = ({ value, strong, className, label }) => {
  const level = scoreLevel(value, strong);
  const shown = value == null ? 0 : Math.max(0, Math.min(100, value));
  return (
    <div className={cn('flex items-center gap-2.5', className)}>
      <span className={cn('w-9 shrink-0 text-right text-sm font-semibold tabular-nums', LEVEL_TEXT[level])}>
        {value == null ? '—' : `${shown}%`}
      </span>
      <div className="h-1 min-w-[3rem] flex-1 overflow-hidden rounded-full bg-line" role="img"
        aria-label={label ? `${label}: ${value == null ? 'not available' : `${shown}%`}` : undefined}>
        <div className={cn('h-full rounded-full transition-[width] duration-500', LEVEL_BAR[level])} style={{ width: `${shown}%` }} />
      </div>
    </div>
  );
};

export const ScoreRing = ({ value, label, sublabel, size = 64, stroke = 6, strong }) => {
  const r = (size - stroke) / 2;
  const circ = 2 * Math.PI * r;
  const shown = value == null ? 0 : Math.max(0, Math.min(100, value));
  const level = scoreLevel(value, strong);
  return (
    <div className="flex flex-col items-center gap-1.5 text-center">
      <div className="relative" style={{ width: size, height: size }}>
        <svg width={size} height={size} className="-rotate-90" aria-hidden="true">
          <circle cx={size / 2} cy={size / 2} r={r} fill="none" strokeWidth={stroke} className="stroke-line" />
          {shown > 0 && (
            <circle
              cx={size / 2} cy={size / 2} r={r} fill="none" strokeWidth={stroke} strokeLinecap="round"
              className={cn('transition-[stroke-dasharray] duration-500', LEVEL_STROKE[level])}
              strokeDasharray={`${(shown / 100) * circ} ${circ}`}
            />
          )}
        </svg>
        <span className={cn('absolute inset-0 flex items-center justify-center font-semibold tabular-nums', size >= 80 ? 'font-serif text-2xl font-normal' : 'text-sm', LEVEL_TEXT[level])}>
          {value == null ? '—' : `${shown}%`}
        </span>
      </div>
      {label && <span className="text-xs font-medium text-ink-2">{label}</span>}
      {sublabel && <span className="-mt-1 text-[11px] leading-tight text-ink-3">{sublabel}</span>}
    </div>
  );
};

/* ── Misc ───────────────────────────────────────────────────────────── */

const AVATAR_TONES = [
  'bg-primary-soft text-primary-soft-fg',
  'bg-warning-soft text-warning',
  'bg-info-soft text-info',
  'bg-danger-soft text-danger',
  'bg-subtle text-ink-2',
];

export const Initials = ({ name, className }) => {
  const parts = (name || '?').trim().split(/\s+/);
  const text = (parts[0][0] + (parts.length > 1 ? parts[parts.length - 1][0] : '')).toUpperCase();
  const hash = [...(name || '')].reduce((h, ch) => (h * 31 + ch.charCodeAt(0)) >>> 0, 7);
  return (
    <div
      className={cn('flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-xs font-semibold', AVATAR_TONES[hash % AVATAR_TONES.length], className)}
      aria-hidden="true"
    >
      {text}
    </div>
  );
};

/** Headline figures in one ruled strip. items: [{ label, value, sub }] */
export const StatStrip = ({ items, loading }) => (
  <Card className="grid grid-cols-2 gap-px overflow-hidden bg-line lg:grid-cols-4">
    {items.map(({ label, value, sub }) => (
      <div key={label} className="bg-surface px-5 py-4 md:py-5">
        <p className="text-xs font-medium uppercase tracking-[0.08em] text-ink-3">{label}</p>
        <p className="mt-2 font-serif text-4xl leading-none tabular-nums text-ink md:text-[2.75rem]">
          {loading ? <Skeleton className="h-9 w-14" /> : value}
        </p>
        {sub && !loading && <p className="mt-2 text-xs text-ink-3">{sub}</p>}
      </div>
    ))}
  </Card>
);

export const Skeleton = ({ className }) => (
  <span className={cn('block animate-pulse rounded-md bg-subtle', className)} aria-hidden="true" />
);

export const EmptyState = ({ icon: Icon, title, description, action, className }) => (
  <div className={cn('flex flex-col items-center px-6 py-12 text-center', className)}>
    {Icon && (
      <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-full border border-line bg-canvas">
        <Icon className="h-5 w-5 text-ink-3" aria-hidden="true" />
      </div>
    )}
    <p className="text-sm font-semibold text-ink">{title}</p>
    {description && <p className="mt-1 max-w-sm text-sm text-ink-3">{description}</p>}
    {action && <div className="mt-4">{action}</div>}
  </div>
);

/**
 * Small dropdown menu. Closes on outside click / Escape, arrow keys move
 * between items. `items`: [{ label, Icon, onSelect, danger, separator }]
 */
export const Menu = ({ trigger, items, align = 'right', label }) => {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  const btnRef = useRef(null);

  useEffect(() => {
    if (!open) return undefined;
    const close = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    document.addEventListener('mousedown', close);
    ref.current?.querySelector('[role="menuitem"]')?.focus();
    return () => document.removeEventListener('mousedown', close);
  }, [open]);

  const onKeyDown = (e) => {
    if (!open) return;
    const els = [...ref.current.querySelectorAll('[role="menuitem"]')];
    const i = els.indexOf(document.activeElement);
    if (e.key === 'Escape') { setOpen(false); btnRef.current?.focus(); }
    else if (e.key === 'ArrowDown') { e.preventDefault(); els[(i + 1) % els.length]?.focus(); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); els[(i - 1 + els.length) % els.length]?.focus(); }
    else if (e.key === 'Tab') setOpen(false);
  };

  return (
    <div className="relative" ref={ref} onKeyDown={onKeyDown}>
      {React.cloneElement(trigger, {
        ref: btnRef,
        onClick: (e) => { e.stopPropagation(); setOpen((o) => !o); },
        'aria-haspopup': 'menu',
        'aria-expanded': open,
      })}
      {open && (
        <div role="menu" aria-label={label}
          className={cn('absolute top-full z-40 mt-1 min-w-[11rem] rounded-md border border-line bg-surface p-1 shadow-pop animate-in fade-in-0 zoom-in-95',
            align === 'right' ? 'right-0' : 'left-0')}>
          {items.map((item, i) => (item.separator ? (
            <div key={`sep-${i}`} className="my-1 border-t border-line" />
          ) : (
            <button
              key={item.label}
              role="menuitem"
              type="button"
              onClick={(e) => { e.stopPropagation(); setOpen(false); item.onSelect(); }}
              className={cn(
                'flex w-full items-center gap-2.5 rounded px-2.5 py-1.5 text-left text-sm outline-none transition-colors',
                item.danger ? 'text-danger hover:bg-danger-soft focus:bg-danger-soft' : 'text-ink-2 hover:bg-subtle hover:text-ink focus:bg-subtle focus:text-ink',
              )}
            >
              {item.Icon && <item.Icon className="h-4 w-4 shrink-0 opacity-80" aria-hidden="true" />}
              {item.label}
            </button>
          )))}
        </div>
      )}
    </div>
  );
};

export const formatDate = (value) => {
  if (!value) return '—';
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? '—' : d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
};

/** "3 days ago" style date for lists; full date in the title attribute */
export const RelativeDate = ({ value }) => {
  const d = value ? new Date(value) : null;
  if (!d || Number.isNaN(d.getTime())) return <span>—</span>;
  const days = Math.floor((Date.now() - d.getTime()) / 86400000);
  const text = days <= 0 ? 'Today' : days === 1 ? 'Yesterday' : days < 30 ? `${days} days ago` : formatDate(value);
  return <time dateTime={d.toISOString()} title={formatDate(value)}>{text}</time>;
};
