import React from 'react';
import { cn } from '../lib/utils';

/** ResumeAI logo + wordmark, used in the sidebar, top bar and auth pages */
const BrandMark = ({ compact = false, inverted = false, className }) => (
  <div className={cn('flex items-center gap-2.5', className)}>
    <div className={cn('flex h-8 w-8 shrink-0 items-center justify-center rounded-lg', inverted ? 'bg-white' : 'bg-brand')}>
      <svg viewBox="0 0 24 24" fill="none" className={cn('h-4 w-4', inverted ? 'stroke-brand' : 'stroke-white')} strokeWidth="2.5" aria-hidden="true">
        <path d="M12 2L2 7l10 5 10-5-10-5z" />
        <path d="M2 17l10 5 10-5" />
        <path d="M2 12l10 5 10-5" />
      </svg>
    </div>
    {!compact && (
      <div className="leading-tight">
        <p className={cn('font-display text-sm font-extrabold', inverted ? 'text-white' : 'text-brand')}>ResumeAI</p>
        <p className={cn('text-[10px] font-semibold uppercase tracking-widest', inverted ? 'text-indigo-200' : 'text-slate-500')}>
          AI resume screening
        </p>
      </div>
    )}
  </div>
);

export default BrandMark;
