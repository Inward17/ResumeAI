import React from 'react';
import { cn } from '../../lib/utils';

/** Grey placeholder block. Hidden from screen readers: wrap regions in SkeletonRegion. */
export const Skeleton = ({ className }) => (
  <span className={cn('block rounded-md bg-subtle motion-safe:animate-pulse', className)} aria-hidden="true" />
);

/** Announces "Loading …" once for a whole skeleton area */
export const SkeletonRegion = ({ label, className, children }) => (
  <div role="status" className={className}>
    <span className="sr-only">{label}</span>
    {children}
  </div>
);

const card = 'rounded-lg border border-line bg-surface';

/** Rows of avatar/title/meta, used for lists and tables */
export const RowsSkeleton = ({ rows = 4, avatar = false, className }) => (
  <ul className={cn('divide-y divide-line', className)} aria-hidden="true">
    {Array.from({ length: rows }, (_, i) => (
      <li key={i} className="flex items-center gap-3 px-5 py-3.5">
        {avatar && <Skeleton className="h-8 w-8 shrink-0 rounded-full" />}
        <div className="min-w-0 flex-1 space-y-1.5">
          <Skeleton className={cn('h-3.5', i % 2 ? 'w-2/5' : 'w-1/2')} />
          <Skeleton className="h-3 w-1/3" />
        </div>
        <Skeleton className="hidden h-2 w-24 sm:block" />
        <Skeleton className="h-6 w-20 shrink-0 rounded-full" />
      </li>
    ))}
  </ul>
);

/** Grid of cards shaped like job / interview cards */
export const CardGridSkeleton = ({ count = 3, avatar = false }) => (
  <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3" aria-hidden="true">
    {Array.from({ length: count }, (_, i) => (
      <div key={i} className={cn(card, 'flex flex-col p-5')}>
        <div className="flex items-start justify-between gap-3">
          <div className="flex min-w-0 flex-1 items-center gap-3">
            {avatar && <Skeleton className="h-10 w-10 shrink-0 rounded-full" />}
            <div className="min-w-0 flex-1 space-y-2">
              <Skeleton className="h-6 w-3/4" />
              <Skeleton className="h-3.5 w-1/3" />
            </div>
          </div>
          <Skeleton className="h-6 w-16 rounded-full" />
        </div>
        <div className="mt-4 space-y-2">
          <Skeleton className="h-3.5" />
          <Skeleton className="h-3.5 w-4/5" />
        </div>
        <div className="mt-4 flex gap-1.5">
          <Skeleton className="h-6 w-14 rounded-full" />
          <Skeleton className="h-6 w-20 rounded-full" />
          <Skeleton className="h-6 w-12 rounded-full" />
        </div>
        <div className="mt-5 flex gap-4 border-t border-line pt-3">
          <Skeleton className="h-3 w-24" />
          <Skeleton className="h-3 w-16" />
        </div>
      </div>
    ))}
  </div>
);

/** Card with a header bar and a body of rows */
export const PanelSkeleton = ({ rows = 3, avatar = false, className }) => (
  <div className={cn(card, 'overflow-hidden', className)} aria-hidden="true">
    <div className="border-b border-line px-5 py-4"><Skeleton className="h-4 w-32" /></div>
    <RowsSkeleton rows={rows} avatar={avatar} />
  </div>
);

/** Generic page: title, intro line, stat strip, two panels */
export const PageSkeleton = () => (
  <SkeletonRegion label="Loading page" className="mx-auto w-full max-w-7xl px-4 py-6 md:px-8 md:py-8">
    <div aria-hidden="true">
      <Skeleton className="h-9 w-56 md:h-11" />
      <Skeleton className="mt-3 h-4 w-full max-w-md" />
      <div className="mt-8 grid grid-cols-2 gap-px overflow-hidden rounded-lg border border-line bg-line lg:grid-cols-4">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="space-y-3 bg-surface px-5 py-5">
            <Skeleton className="h-3 w-20" />
            <Skeleton className="h-8 w-12" />
          </div>
        ))}
      </div>
      <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1fr)_320px]">
        <PanelSkeleton rows={4} />
        <PanelSkeleton rows={3} />
      </div>
    </div>
  </SkeletonRegion>
);
