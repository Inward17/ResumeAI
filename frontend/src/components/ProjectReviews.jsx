import React, { useCallback, useEffect, useState } from 'react';
import {
  AlertTriangle, CheckCircle2, CircleDashed, ExternalLink, Loader2, MessageSquareText, RefreshCw, Rocket, XCircle,
} from 'lucide-react';
import { cn } from '../lib/utils';
import { Button, Tag } from './common';
import { getProjectReviews, startProjectReviews } from '../services/jobService';

const STEP = { queued: 'Queued', visiting: 'Visiting the site…', reviewing: 'AI is reviewing…', done: 'Done', failed: 'Failed' };
const SITE = {
  live: { Icon: CheckCircle2, cls: 'text-success', text: 'Live' },
  down: { Icon: XCircle, cls: 'text-danger', text: 'Down' },
  blocked: { Icon: AlertTriangle, cls: 'text-warning', text: 'Blocked the visit' },
  empty: { Icon: AlertTriangle, cls: 'text-warning', text: 'Empty page' },
  placeholder: { Icon: AlertTriangle, cls: 'text-warning', text: 'Placeholder' },
};
const NOT_VISITED = { Icon: CircleDashed, cls: 'text-ink-3', text: 'Not visited' };
const VERDICT = { yes: 'text-success', partly: 'text-warning', no: 'text-danger', supports: 'text-success', conflicts: 'text-danger', unclear: 'text-ink-3' };
const VERDICT_TEXT = { yes: 'Yes', partly: 'Partly', no: 'No', supports: 'Supports', conflicts: 'Conflicts', unclear: 'Unclear' };
const RATING_LABEL = { working: 'Working', polish: 'Polish / UX', technical_depth: 'Technical depth', originality: 'Originality' };

const hostOf = (url) => { try { return new URL(url).hostname; } catch { return url || ''; } };
const pathOf = (url) => { try { return new URL(url).pathname; } catch { return url; } };
const when = (iso) => { const d = iso ? new Date(`${iso}`.endsWith('Z') ? iso : `${iso}Z`) : null; return d && !Number.isNaN(d) ? d.toLocaleString() : null; };

/** Discovered projects and the latest review for one candidate; polls while a review runs. */
export const useProjectReviews = (jobId, candidateId) => {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const load = useCallback(async () => {
    try {
      setData(await getProjectReviews(jobId, candidateId));
      setError(null);
    } catch (e) {
      setError(e.message);
    }
  }, [jobId, candidateId]);

  useEffect(() => { setData(null); if (jobId && candidateId) load(); }, [jobId, candidateId, load]);
  const running = data?.review?.status === 'running';
  useEffect(() => {
    if (!running) return undefined;
    const t = setInterval(load, 3000);
    return () => clearInterval(t);
  }, [running, load]);
  return { data, error, setError, load };
};

const ProjectLink = ({ p }) => (p.url ? (
  <a href={p.url} target="_blank" rel="noreferrer noopener" className="inline-flex min-w-0 items-center gap-1 font-medium text-primary-text hover:underline">
    <span className="truncate">{p.name || hostOf(p.url)}</span><ExternalLink className="h-3 w-3 shrink-0" aria-hidden="true" />
  </a>
) : <span className="truncate font-medium text-ink">{p.name}</span>);

const Source = ({ p }) => (
  <p className="text-xs leading-relaxed text-ink-3">
    <span className="font-medium text-ink-2">{p.sourceLabel}:</span> &lsquo;{p.mention}&rsquo;
  </p>
);

const Verdict = ({ label, v }) => (v ? (
  <p className="text-xs leading-relaxed text-ink-2">
    <span className="text-ink-3">{label}: </span>
    <span className={cn('font-medium', VERDICT[v.verdict])}>{VERDICT_TEXT[v.verdict] || v.verdict}</span>
    {v.text && <> · {v.text}</>}
  </p>
) : null);

const Result = ({ p, onRetry, busy }) => {
  const site = SITE[p.siteStatus] || NOT_VISITED;
  const r = p.review;
  return (
    <li className="space-y-2.5 px-3 py-3 text-sm">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 space-y-0.5">
          <ProjectLink p={p} />
          <Source p={p} />
        </div>
        <div className="flex shrink-0 flex-col items-end gap-1">
          {r?.overall?.score != null && (
            <span className="text-sm font-semibold tabular-nums text-ink" aria-label={`Overall ${r.overall.score} out of 5`}>
              {r.overall.score}<span className="text-ink-3">/5</span>
            </span>
          )}
          <span className={cn('flex items-center gap-1 text-xs font-medium', site.cls)}>
            <site.Icon className="h-3.5 w-3.5" aria-hidden="true" />{p.state && p.state !== 'done' ? STEP[p.state] : site.text}
          </span>
        </div>
      </div>

      {r ? (
        <>
          <p className="text-sm leading-relaxed text-ink">{r.whatItDoes}</p>
          {r.overall?.justification && <p className="text-xs leading-relaxed text-ink-3">{r.overall.justification}</p>}
          <Verdict label="Live and working" v={r.live} />
          <Verdict label="Matches the claim" v={r.matchesClaim} />
          <Verdict label="Ownership" v={r.ownership} />
          <dl className="grid grid-cols-2 gap-x-3 gap-y-1.5 text-xs sm:grid-cols-4">
            {r.ratings.map((x) => (
              <div key={x.key} className="min-w-0" title={x.reason}>
                <dt className="text-ink-3">{RATING_LABEL[x.key]}</dt>
                <dd className="font-medium tabular-nums text-ink">{x.score ?? '—'}<span className="text-ink-3">/5</span></dd>
                <dd className="text-ink-3">{x.reason}</dd>
              </div>
            ))}
          </dl>
          {r.jobRelevance?.score != null && (
            <p className="text-xs leading-relaxed text-ink-2">
              <span className="text-ink-3">Relevance to this job: </span>
              <span className="font-medium tabular-nums text-ink">{r.jobRelevance.score}/5</span>
              {r.jobRelevance.reason && <> · {r.jobRelevance.reason}</>}
            </p>
          )}
          {r.redFlags.map((f) => (
            <p key={f} className="flex items-start gap-2 rounded-lg bg-warning-soft px-2.5 py-1.5 text-xs leading-relaxed text-warning ring-1 ring-inset ring-warning/25">
              <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden="true" />{f}
            </p>
          ))}
          {r.interviewQuestions.length > 0 && (
            <div>
              <h5 className="mb-1 text-xs font-semibold text-ink-2">Ask about this product</h5>
              <ul className="space-y-1">
                {r.interviewQuestions.map((q) => (
                  <li key={q} className="flex items-start gap-2 text-xs leading-relaxed text-ink-2">
                    <MessageSquareText className="mt-0.5 h-3.5 w-3.5 shrink-0 text-ink-3" aria-hidden="true" />{q}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </>
      ) : (p.siteNote || p.reviewNote) && (
        <p className="flex items-start gap-2 text-xs leading-relaxed text-ink-3">
          <CircleDashed className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden="true" />
          <span>{p.reviewStatus === 'ai_unavailable' ? p.reviewNote : (p.siteNote || p.reviewNote)}</span>
        </p>
      )}
      {p.reviewStatus === 'ai_unavailable' && (
        <Button size="sm" variant="secondary" onClick={onRetry} disabled={busy}><RefreshCw aria-hidden="true" />Retry AI review</Button>
      )}

      {(p.screenshot || p.pages.length > 0) && (
        <div className="flex items-start gap-3">
          {p.screenshot && (
            <a href={p.url || undefined} target="_blank" rel="noreferrer noopener" className="shrink-0">
              <img src={p.screenshot} alt={`Screenshot of ${p.name || hostOf(p.url)}`} loading="lazy"
                className="h-20 w-32 rounded-md border border-line object-cover object-top" />
            </a>
          )}
          {p.pages.length > 0 && (
            <div className="min-w-0 text-xs">
              <p className="text-ink-3">Pages visited</p>
              <ul className="space-y-0.5">
                {p.pages.map((pg) => (
                  <li key={pg.url || pg.title} className="truncate text-ink-2">
                    {pg.url ? <a href={pg.url} target="_blank" rel="noreferrer noopener" className="hover:underline">{pathOf(pg.url)}</a> : pg.title}
                    {pg.failed && <span className="text-ink-3"> (could not load)</span>}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </li>
  );
};

const ProjectReviews = ({ jobId, candidateId, state }) => {
  const { data, error, setError, load } = state;
  const [busy, setBusy] = useState(false);
  if (!data) {
    return (
      <section>
        <h3 className="mb-2.5 text-sm font-semibold text-ink">Projects</h3>
        <p className="text-sm text-ink-3">{error || 'Loading projects…'}</p>
      </section>
    );
  }
  const review = data.review;
  const running = review?.status === 'running';
  const reviewedIds = new Set((review?.projects || []).map((p) => p.id));
  const others = data.projects.filter((p) => !reviewedIds.has(p.id));
  const canRun = data.firecrawlConfigured && data.projects.some((p) => p.reviewable);

  const start = async (retry = false) => {
    setBusy(true);
    try {
      await startProjectReviews(jobId, candidateId, { retry });
      await load();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <section aria-labelledby="projects-heading">
      <div className="mb-2.5 flex items-center justify-between gap-3">
        <h3 id="projects-heading" className="text-sm font-semibold text-ink">Projects</h3>
        {data.projects.length > 0 && (
          <Button size="sm" variant="secondary" onClick={() => start(false)} disabled={!canRun || running || busy}>
            {running ? <Loader2 className="animate-spin" aria-hidden="true" /> : <Rocket aria-hidden="true" />}
            {running ? 'Reviewing…' : review ? 'Review again' : 'Review projects'}
          </Button>
        )}
      </div>

      {data.projects.length === 0 ? (
        <p className="text-sm text-ink-3">No deployed project links found on the resume, portfolio or GitHub.</p>
      ) : (
        <p className="mb-3 text-xs leading-relaxed text-ink-3">
          {data.firecrawlConfigured
            ? `The AI visits up to ${data.maxProjects} projects most relevant to this job (landing page, up to ${data.maxPages - 1} more pages and a screenshot each): about ${data.maxProjects * data.maxPages} Firecrawl credits and ${data.maxProjects} AI calls. Evidence only; not part of any score.`
            : 'Firecrawl not configured, so deployed projects can’t be visited.'}
        </p>
      )}

      {error && data && (
        <p role="alert" className="mb-3 flex items-start gap-2 rounded-lg bg-danger-soft px-3 py-2 text-xs text-danger ring-1 ring-inset ring-danger/25">
          <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden="true" />{error}
        </p>
      )}

      {review && (
        <div className="mb-3" aria-live="polite">
          <p className="mb-1.5 text-xs text-ink-3">
            {running ? 'Review in progress…' : review.status === 'failed' ? (review.error || 'The review failed.') : `Reviewed ${when(review.reviewedAt) || ''}`}
            {review.requestedBy && ` · requested by ${review.requestedBy}`}
          </p>
          <ul className="divide-y divide-line overflow-hidden rounded-lg border border-line bg-surface">
            {review.projects.map((p) => <Result key={p.id} p={p} busy={busy || running} onRetry={() => start(true)} />)}
          </ul>
        </div>
      )}

      {others.length > 0 && (
        <ul className="space-y-2">
          {others.map((p) => (
            <li key={p.id} className="space-y-0.5 text-sm">
              <div className="flex min-w-0 items-center gap-2">
                <ProjectLink p={p} />
                {!p.reviewable && <Tag>Not reviewable</Tag>}
                {p.reviewable && p.selected && !review && <Tag tone="primary">Will be reviewed</Tag>}
              </div>
              <Source p={p} />
              {p.note && <p className="text-xs text-ink-3">{p.note}</p>}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
};

export default ProjectReviews;
