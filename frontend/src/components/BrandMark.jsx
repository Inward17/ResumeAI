import React from 'react';
import { cn } from '../lib/utils';

/** ResumeAI mark + serif wordmark, used in the sidebar, mobile header and auth pages */
const BrandMark = ({ compact = false, inverted = false, className }) => (
  <div className={cn('flex items-center gap-2', className)}>
    <div className={cn('flex h-6 w-6 shrink-0 items-center justify-center rounded-[5px]', inverted ? 'bg-white/90' : 'bg-btn')}>
      <svg viewBox="0 0 24 24" fill="none" className={cn('h-3.5 w-3.5', inverted ? 'stroke-[#1c1a17]' : 'stroke-btn-fg')} strokeWidth="2.4" strokeLinejoin="round" aria-hidden="true">
        <path d="M12 2L2 7l10 5 10-5-10-5z" />
        <path d="M2 17l10 5 10-5" />
        <path d="M2 12l10 5 10-5" />
      </svg>
    </div>
    {!compact && (
      <span className={cn('font-serif text-[1.35rem] leading-none tracking-[-0.01em]', inverted ? 'text-white' : 'text-ink')}>ResumeAI</span>
    )}
  </div>
);

export default BrandMark;
