import React, { useEffect, useRef, useState } from 'react';
import { AlertTriangle, FileText, Loader2, RefreshCw, Upload, ClipboardPaste, Trash2 } from 'lucide-react';
import { useToast } from '../hooks/use-toast';
import { attachCoverLetter, deleteCoverLetter, getCoverLetter, retryCoverLetterAnalysis } from '../services/jobService';
import { usePermissions } from '../lib/permissions';
import { cn } from '../lib/utils';
import { Button, Skeleton, Tag, Textarea } from './common';
import { SkeletonRegion } from './ui/skeleton';

const ACCEPTED_TYPES = '.pdf,.docx,.doc,.txt';
const SOURCE_LABEL = { uploaded: 'Uploaded', pasted: 'Pasted', auto_detected: 'Auto-detected in upload' };
const SPECIFICITY = { specific: 'Written for this job', generic: 'Generic letter', mixed: 'Partly tailored to this job' };

/** Pick a file or paste text; calls onSubmit(File | string) */
const AttachForm = ({ busy, onSubmit, onCancel }) => {
  const [pasting, setPasting] = useState(false);
  const [text, setText] = useState('');
  const fileRef = useRef(null);

  if (pasting) {
    return (
      <div className="space-y-2">
        <label htmlFor="cover-letter-text" className="sr-only">Cover letter text</label>
        <Textarea id="cover-letter-text" value={text} onChange={(e) => setText(e.target.value)} placeholder="Paste the cover letter here" />
        <div className="flex gap-2">
          <Button size="sm" disabled={busy || !text.trim()} onClick={() => onSubmit(text)}>Save</Button>
          <Button size="sm" variant="ghost" onClick={() => { setPasting(false); onCancel?.(); }}>Cancel</Button>
        </div>
      </div>
    );
  }
  return (
    <div className="flex flex-wrap gap-2">
      <input ref={fileRef} type="file" accept={ACCEPTED_TYPES} className="hidden" aria-hidden="true" tabIndex={-1}
        onChange={(e) => { const f = e.target.files?.[0]; e.target.value = ''; if (f) onSubmit(f); }} />
      <Button size="sm" variant="secondary" disabled={busy} onClick={() => fileRef.current?.click()}>
        <Upload aria-hidden="true" /> Upload file
      </Button>
      <Button size="sm" variant="secondary" disabled={busy} onClick={() => setPasting(true)}>
        <ClipboardPaste aria-hidden="true" /> Paste text
      </Button>
      {onCancel && <Button size="sm" variant="ghost" onClick={onCancel}>Cancel</Button>}
    </div>
  );
};

const Analysis = ({ analysis }) => {
  const { fit, contradictions, probePoints } = analysis;
  return (
    <div className="space-y-4 text-sm">
      <p className="leading-relaxed text-ink-2">{analysis.summary}</p>

      <div>
        <h4 className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-ink-3">Fit to this job</h4>
        <p className="text-ink-2">
          {[SPECIFICITY[fit.specificity], fit.addressesRole === true ? 'addresses the role' : fit.addressesRole === false ? "doesn't address the role" : null]
            .filter(Boolean).join(', ') || 'Not assessed'}
          {fit.notes && <span className="text-ink-3"> — {fit.notes}</span>}
        </p>
        {fit.requirementsAddressed.length > 0 && (
          <div className="mt-2 flex flex-wrap items-center gap-1.5">
            <span className="text-xs text-ink-3">Speaks to:</span>
            {fit.requirementsAddressed.map((r) => <Tag key={r} tone="primary">{r}</Tag>)}
          </div>
        )}
      </div>

      <div>
        <h4 className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-ink-3">Differences from the resume</h4>
        {contradictions.length === 0 ? (
          <p className="text-ink-3">None found.</p>
        ) : (
          <ul className="space-y-2">
            {contradictions.map((c, i) => (
              <li key={i} className={cn('rounded-lg px-3 py-2 ring-1 ring-inset',
                c.severity === 'major' ? 'bg-danger-soft ring-danger/25' : 'bg-warning-soft ring-warning/25')}>
                <p className={cn('text-xs font-semibold', c.severity === 'major' ? 'text-danger' : 'text-warning')}>
                  {c.severity === 'major' ? 'Major' : 'Minor'} · {c.topic}
                </p>
                <p className="mt-0.5 text-ink-2">Letter: {c.letterClaim}</p>
                {c.resumeSays && <p className="text-ink-2">Resume: {c.resumeSays}</p>}
              </li>
            ))}
          </ul>
        )}
      </div>

      {probePoints.length > 0 && (
        <div>
          <h4 className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-ink-3">Probe in the interview</h4>
          <ul className="list-disc space-y-1 pl-5 text-ink-2">
            {probePoints.map((p, i) => <li key={i}>{p}</li>)}
          </ul>
        </div>
      )}
    </div>
  );
};

/** Cover letter of one application: attach, read, AI analysis, remove. Evidence only, never a score. */
const CoverLetterSection = ({ jobId, candidateId }) => {
  const { toast } = useToast();
  const [letter, setLetter] = useState(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(null);
  const [busy, setBusy] = useState(null); // 'saving' | 'analysing' | 'removing'
  const [replacing, setReplacing] = useState(false);
  const { can } = usePermissions();
  const canAttach = can('candidate.verify');

  useEffect(() => {
    let cancelled = false;
    setLoading(true); setLoadError(null); setLetter(null); setReplacing(false);
    getCoverLetter(jobId, candidateId)
      .then((l) => { if (!cancelled) setLetter(l); })
      .catch((err) => { if (!cancelled) setLoadError(err.message); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [jobId, candidateId]);

  const run = async (kind, fn) => {
    setBusy(kind);
    try { await fn(); } catch (err) {
      toast({ title: 'Cover letter', description: err.message, variant: 'destructive' });
    } finally { setBusy(null); }
  };

  const attach = (fileOrText) => run('saving', async () => {
    setLetter(await attachCoverLetter(jobId, candidateId, fileOrText));
    setReplacing(false);
  });
  const retry = () => run('analysing', async () => setLetter(await retryCoverLetterAnalysis(jobId, candidateId)));
  const remove = () => run('removing', async () => { await deleteCoverLetter(jobId, candidateId); setLetter(null); });

  return (
    <section aria-labelledby="cover-letter-heading" aria-busy={!!busy}>
      <div className="mb-2.5 flex items-center justify-between gap-3">
        <h3 id="cover-letter-heading" className="text-sm font-semibold text-ink">Cover letter</h3>
        {letter && !replacing && canAttach && (
          <div className="flex gap-1">
            <Button size="sm" variant="ghost" disabled={!!busy} onClick={() => setReplacing(true)}>Replace</Button>
            <Button size="sm" variant="ghost" disabled={!!busy} onClick={remove}><Trash2 aria-hidden="true" /> Remove</Button>
          </div>
        )}
      </div>

      {loading ? (
        <SkeletonRegion label="Loading cover letter" className="space-y-2"><Skeleton className="h-4" /><Skeleton className="h-4 w-3/5" /></SkeletonRegion>
      ) : loadError ? (
        <p className="text-sm text-danger">{loadError}</p>
      ) : busy === 'saving' ? (
        <p className="flex items-center gap-2 text-sm text-ink-2" role="status">
          <Loader2 className="h-4 w-4 animate-spin text-primary-text" aria-hidden="true" /> Saving and analysing the letter…
        </p>
      ) : !letter || replacing ? (
        <div className="space-y-2">
          {!letter && <p className="text-sm text-ink-3">No cover letter for this job. It's shown as evidence and doesn't change any score.</p>}
          {canAttach && <AttachForm busy={!!busy} onSubmit={attach} onCancel={replacing ? () => setReplacing(false) : undefined} />}
        </div>
      ) : (
        <div className="space-y-4">
          <div className="flex flex-wrap items-center gap-2 text-xs text-ink-3">
            <Tag>{SOURCE_LABEL[letter.source] || letter.source}</Tag>
            {letter.filename && <span className="flex min-w-0 items-center gap-1"><FileText className="h-3.5 w-3.5 shrink-0" aria-hidden="true" /><span className="truncate">{letter.filename}</span></span>}
          </div>
          {letter.source === 'auto_detected' && (
            <p className="text-xs text-ink-3">Matched to this candidate by name or filename. Remove it if it belongs to someone else.</p>
          )}

          <details className="group rounded-lg border border-line bg-surface">
            <summary className="cursor-pointer px-3 py-2 text-sm font-medium text-ink-2 hover:text-ink">Show the letter</summary>
            <p className="max-h-80 overflow-y-auto whitespace-pre-wrap border-t border-line px-3 py-2 text-sm leading-relaxed text-ink-2">
              {letter.text}
            </p>
            {letter.truncated && <p className="px-3 pb-2 text-xs text-ink-3">Shortened: the letter was longer than the stored limit.</p>}
          </details>

          {letter.analysis ? (
            <Analysis analysis={letter.analysis} />
          ) : (
            <div className="flex items-start gap-2 rounded-lg bg-warning-soft px-3 py-2 text-sm text-warning ring-1 ring-inset ring-warning/25" role="status">
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
              <p className="flex-1">{busy === 'analysing' ? 'Analysing…' : (letter.analysisError || 'Analysis unavailable.')}</p>
              {can('ai.run') && (
                <Button size="sm" variant="secondary" disabled={!!busy} onClick={retry}>
                  {busy === 'analysing' ? <Loader2 className="animate-spin" aria-hidden="true" /> : <RefreshCw aria-hidden="true" />} Retry
                </Button>
              )}
            </div>
          )}
        </div>
      )}
    </section>
  );
};

export default CoverLetterSection;
