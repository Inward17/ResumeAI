/**
 * Structured interview scorecards.
 * - ScorecardTemplateCard: the job's competencies (job page), edited in a modal, with an AI draft.
 * - ScorecardForm: one interviewer's ratings + evidence (interview page, dossier). Drafts autosave.
 * - InterviewScorecards: requests, the evidence summary and the AI brief (dossier).
 * Interviewer notes and AI text are plain text.
 */
import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  AlertTriangle, ClipboardCheck, Loader2, Lock, Plus, RefreshCw, Send, Sparkles, Trash2, UserPlus, X,
} from 'lucide-react';
import Modal from './Modal';
import { useToast } from '../hooks/use-toast';
import { cn } from '../lib/utils';
import { getEvaluation } from '../services/jobService';
import { getOrg } from '../services/orgService';
import {
  MIN_EVIDENCE, RECOMMENDATIONS, cancelScorecardRequest, getEvidenceBrief, getEvidenceSummary, getScorecardTemplate,
  getScorecards, requestScorecard, saveMyScorecard, saveScorecardTemplate, suggestScorecardTemplate,
} from '../services/scorecardService';
import {
  Button, Card, CardHeader, Field, IconButton, Input, ScoreRing, Select, Skeleton, Tag, Textarea, formatDate,
} from './common';

const RATING_LABEL = { 1: 'Clear gap', 2: 'Below the bar', 3: 'Meets the bar', 4: 'Strong' };
const REC_LABEL = Object.fromEntries(RECOMMENDATIONS.map((r) => [r.id, r.label]));
const STATUS_LABEL = { requested: 'Asked', draft: 'Draft', submitted: 'Submitted' };
const newId = () => Math.random().toString(36).slice(2, 10);
const blank = () => ({ id: newId(), name: '', description: '', anchors: ['', '', '', ''], weight: 1 });

/* ── Template (job page) ─────────────────────────────────────────────── */

const TemplateEditor = ({ open, onOpenChange, jobId, initial, onSaved }) => {
  const { toast } = useToast();
  const [comps, setComps] = useState([]);
  const [busy, setBusy] = useState(null); // 'saving' | 'suggesting'
  const [error, setError] = useState(null);

  // Reset only when the editor opens, so a parent re-render doesn't wipe edits
  useEffect(() => {
    if (open) { setComps(initial?.length ? initial : [blank(), blank(), blank()]); setError(null); }
  }, [open]); // eslint-disable-line react-hooks/exhaustive-deps

  const edit = (i, patch) => setComps((cs) => cs.map((c, j) => (j === i ? { ...c, ...patch } : c)));
  const editAnchor = (i, k, v) => setComps((cs) => cs.map((c, j) => (j === i ? { ...c, anchors: c.anchors.map((a, n) => (n === k ? v : a)) } : c)));

  const suggest = async () => {
    setBusy('suggesting'); setError(null);
    try {
      setComps(await suggestScorecardTemplate(jobId));
    } catch (err) { setError(err.message); } finally { setBusy(null); }
  };
  const save = async () => {
    if (comps.length < 3 || comps.length > 8) { setError('A scorecard has 3 to 8 competencies.'); return; }
    if (comps.some((c) => !c.name.trim())) { setError('Every competency needs a name.'); return; }
    setBusy('saving'); setError(null);
    try {
      onSaved(await saveScorecardTemplate(jobId, comps.map((c) => ({ ...c, weight: Number(c.weight) || 1 }))));
      toast({ title: 'Scorecard saved' });
      onOpenChange(false);
    } catch (err) { setError(err.message); } finally { setBusy(null); }
  };

  return (
    <Modal open={open} onOpenChange={(o) => !busy && onOpenChange(o)} title="Interview scorecard" maxWidth="md:max-w-3xl"
      description="What every interviewer rates for this job, from 1 to 4, with evidence."
      footer={(
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <Button variant="secondary" onClick={suggest} disabled={!!busy}>
            {busy === 'suggesting' ? <Loader2 className="animate-spin" aria-hidden="true" /> : <Sparkles aria-hidden="true" />}
            {busy === 'suggesting' ? 'Drafting…' : 'Suggest from job description'}
          </Button>
          <div className="flex gap-2">
            <Button variant="ghost" onClick={() => onOpenChange(false)} disabled={!!busy}>Cancel</Button>
            <Button onClick={save} disabled={!!busy}>{busy === 'saving' ? 'Saving…' : 'Save scorecard'}</Button>
          </div>
        </div>
      )}>
      <div className="space-y-4 p-5" aria-busy={!!busy}>
        {error && <p className="rounded-lg bg-danger-soft px-3 py-2 text-sm text-danger" role="alert">{error}</p>}
        <p className="text-xs text-ink-3">An AI draft replaces what's below; nothing is saved until you press Save. Rate job-related skills and behaviours only.</p>
        {comps.map((c, i) => (
          <Card key={c.id} className="space-y-3 p-4">
            <div className="flex items-start gap-2">
              <Field label={`Competency ${i + 1}`} htmlFor={`comp-name-${c.id}`} className="flex-1">
                <Input id={`comp-name-${c.id}`} value={c.name} maxLength={80} onChange={(e) => edit(i, { name: e.target.value })} placeholder="e.g. System design" />
              </Field>
              <Field label="Weight" htmlFor={`comp-weight-${c.id}`} className="w-24">
                <Select id={`comp-weight-${c.id}`} value={c.weight} onChange={(e) => edit(i, { weight: Number(e.target.value) })}>
                  {[1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map((w) => <option key={w} value={w}>{w}</option>)}
                </Select>
              </Field>
              <IconButton label={`Remove ${c.name || `competency ${i + 1}`}`} className="mt-7" disabled={comps.length <= 3}
                onClick={() => setComps((cs) => cs.filter((_, j) => j !== i))}><Trash2 aria-hidden="true" /></IconButton>
            </div>
            <Field label="Description" htmlFor={`comp-desc-${c.id}`} optional>
              <Input id={`comp-desc-${c.id}`} value={c.description} maxLength={500} onChange={(e) => edit(i, { description: e.target.value })} />
            </Field>
            <fieldset>
              <legend className="mb-1.5 text-sm font-medium text-ink-2">What each rating looks like</legend>
              <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                {c.anchors.map((a, k) => (
                  <label key={k} className="block text-xs text-ink-3">
                    {k + 1} · {RATING_LABEL[k + 1]}
                    <Input value={a} maxLength={300} onChange={(e) => editAnchor(i, k, e.target.value)} className="mt-1" />
                  </label>
                ))}
              </div>
            </fieldset>
          </Card>
        ))}
        <Button variant="secondary" onClick={() => setComps((cs) => [...cs, blank()])} disabled={comps.length >= 8}>
          <Plus aria-hidden="true" /> Add competency
        </Button>
      </div>
    </Modal>
  );
};

export const ScorecardTemplateCard = ({ jobId }) => {
  const [template, setTemplate] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [editing, setEditing] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setLoading(true); setError(null);
    getScorecardTemplate(jobId)
      .then((t) => { if (!cancelled) setTemplate(t); })
      .catch((err) => { if (!cancelled) setError(err.message); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [jobId]);

  const comps = template?.competencies || [];
  return (
    <Card>
      <CardHeader title="Interview scorecard" subtitle={comps.length ? `${comps.length} competencies` : 'Not set up'}
        action={!loading && !error && (
          <Button size="sm" variant="secondary" onClick={() => setEditing(true)}>{comps.length ? 'Edit' : 'Set up'}</Button>
        )} />
      <div className="p-4 text-sm">
        {loading ? <Skeleton className="h-4" /> : error ? <p className="text-danger">{error}</p> : comps.length === 0 ? (
          <p className="text-ink-3">Set the competencies every interviewer rates, so candidates are compared on the same evidence.</p>
        ) : (
          <ul className="space-y-1.5">
            {comps.map((c) => (
              <li key={c.id} className="flex justify-between gap-3">
                <span className="truncate text-ink-2">{c.name}</span>
                <span className="shrink-0 text-xs tabular-nums text-ink-3">weight {c.weight}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
      <TemplateEditor open={editing} onOpenChange={setEditing} jobId={jobId} initial={comps} onSaved={setTemplate} />
    </Card>
  );
};

/* ── Interviewer form ────────────────────────────────────────────────── */

const fromCard = (template, mine) => {
  const byId = Object.fromEntries((mine?.ratings || []).map((r) => [r.competencyId, r]));
  return {
    ratings: template.map((c) => ({
      competencyId: c.id, rating: byId[c.id]?.rating ?? null, evidence: byId[c.id]?.evidence || '', questionIds: byId[c.id]?.questionIds || [],
    })),
    recommendation: mine?.recommendation || null,
    summary: mine?.summary || '',
  };
};

const problems = (template, form) => {
  const out = [];
  const rated = form.ratings.filter((r) => r.rating != null);
  if (!rated.length) out.push('Rate at least one competency.');
  rated.forEach((r) => {
    if (r.evidence.trim().length < MIN_EVIDENCE) out.push(`Add evidence for ${template.find((c) => c.id === r.competencyId)?.name}.`);
  });
  if (!form.recommendation) out.push('Choose a recommendation.');
  if (!form.summary.trim()) out.push('Write a short summary.');
  return out;
};

/** Ratings 1-4 (or not assessed) with required evidence, recommendation and summary. */
export const ScorecardForm = ({ jobId, candidateId, onSubmitted }) => {
  const { toast } = useToast();
  const [data, setData] = useState(null); // { template, mine }
  const [form, setForm] = useState(null);
  const [questions, setQuestions] = useState([]);
  const [loadError, setLoadError] = useState(null);
  const [saveState, setSaveState] = useState(null); // 'saving' | 'saved' | 'error'
  const [submitting, setSubmitting] = useState(false);
  const [showProblems, setShowProblems] = useState(false);
  const dirty = useRef(false);

  const load = useCallback(async () => {
    setLoadError(null);
    try {
      const [d, evaluation] = await Promise.all([getScorecards(jobId, candidateId), getEvaluation(jobId, candidateId).catch(() => null)]);
      setData(d);
      setForm(fromCard(d.template, d.mine));
      setQuestions(evaluation?.questions || []);
      dirty.current = false;
    } catch (err) { setLoadError(err.message); }
  }, [jobId, candidateId]);
  useEffect(() => { load(); }, [load]);

  const submitted = data?.mine?.status === 'submitted';

  // Drafts autosave a moment after the last change; a submitted card is only saved by submitting again
  useEffect(() => {
    if (!form || !dirty.current || submitted) return undefined;
    const timer = setTimeout(async () => {
      setSaveState('saving');
      try {
        const mine = await saveMyScorecard(jobId, candidateId, { ...form, submit: false });
        setData((d) => ({ ...d, mine }));
        dirty.current = false;
        setSaveState('saved');
      } catch { setSaveState('error'); }
    }, 1500);
    return () => clearTimeout(timer);
  }, [form, submitted, jobId, candidateId]);

  const change = (patch) => { dirty.current = true; setSaveState(null); setForm((f) => ({ ...f, ...patch })); };
  const changeRating = (i, patch) => change({ ratings: form.ratings.map((r, j) => (j === i ? { ...r, ...patch } : r)) });

  const submit = async () => {
    const issues = problems(data.template, form);
    if (issues.length) { setShowProblems(true); return; }
    setSubmitting(true);
    try {
      dirty.current = false;
      const mine = await saveMyScorecard(jobId, candidateId, { ...form, submit: true });
      setData((d) => ({ ...d, mine }));
      setShowProblems(false);
      toast({ title: submitted ? 'Scorecard updated' : 'Scorecard submitted' });
      onSubmitted?.();
    } catch (err) {
      toast({ title: 'Could not submit the scorecard', description: err.message, variant: 'destructive' });
    } finally { setSubmitting(false); }
  };

  if (loadError) {
    return (
      <div className="space-y-2 p-4 text-sm">
        <p className="text-danger">{loadError}</p>
        <Button size="sm" variant="secondary" onClick={load}><RefreshCw aria-hidden="true" /> Try again</Button>
      </div>
    );
  }
  if (!data || !form) return <div className="space-y-2 p-4"><Skeleton className="h-4" /><Skeleton className="h-24" /></div>;
  if (!data.template.length) {
    return <p className="p-4 text-sm text-ink-3">This job has no scorecard yet. Set one up from the job page under Interview scorecard.</p>;
  }
  const issues = showProblems ? problems(data.template, form) : [];

  return (
    <div className="space-y-5 p-4">
      <p className="text-xs text-ink-3" role="status">
        {submitted ? `Submitted ${formatDate(data.mine.submittedAt)}. Changes are saved only when you submit again.`
          : saveState === 'saving' ? 'Saving draft…' : saveState === 'saved' ? 'Draft saved. Only you can see it.'
            : saveState === 'error' ? 'Could not save the draft. Keep this page open and try again.'
              : 'Drafts save automatically and stay private. Other interviewers\' scorecards stay hidden until you submit yours.'}
      </p>

      {data.template.map((c, i) => {
        const r = form.ratings[i];
        const short = r.rating != null && r.evidence.trim().length < MIN_EVIDENCE;
        return (
          <fieldset key={c.id} className="space-y-2 border-t border-line pt-4 first-of-type:border-t-0 first-of-type:pt-0">
            <legend className="text-sm font-semibold text-ink">{c.name}<span className="ml-1.5 text-xs font-normal text-ink-3">weight {c.weight}</span></legend>
            {c.description && <p className="text-xs text-ink-3">{c.description}</p>}
            <div className="grid grid-cols-1 gap-1.5">
              {[1, 2, 3, 4, null].map((v) => (
                <label key={v ?? 'na'} className={cn('flex cursor-pointer items-start gap-2 rounded-md border px-2.5 py-1.5 text-sm',
                  r.rating === v ? 'border-primary bg-primary-soft text-ink' : 'border-line text-ink-2 hover:bg-subtle')}>
                  <input type="radio" name={`rating-${c.id}`} className="mt-1" checked={r.rating === v} onChange={() => changeRating(i, { rating: v })} />
                  <span>
                    <span className="font-medium">{v == null ? 'Not assessed' : `${v} · ${RATING_LABEL[v]}`}</span>
                    {v != null && c.anchors?.[v - 1] && <span className="block text-xs text-ink-3">{c.anchors[v - 1]}</span>}
                  </span>
                </label>
              ))}
            </div>
            <Field label="Evidence: what the candidate said or did" htmlFor={`evidence-${c.id}`} required={r.rating != null}
              error={showProblems && short ? `At least ${MIN_EVIDENCE} characters` : null}
              hint={r.rating != null ? `${r.evidence.trim().length}/${MIN_EVIDENCE} characters minimum` : 'Optional when not assessed'}>
              <Textarea id={`evidence-${c.id}`} value={r.evidence} maxLength={2000} className="min-h-[4.5rem]"
                onChange={(e) => changeRating(i, { evidence: e.target.value })} />
            </Field>
            {questions.length > 0 && (
              <details className="text-xs">
                <summary className="cursor-pointer text-ink-3 hover:text-ink">Link interview questions{r.questionIds.length ? ` (${r.questionIds.length})` : ''}</summary>
                <div className="mt-1.5 space-y-1">
                  {questions.map((q) => (
                    <label key={q.question_id} className="flex items-start gap-2 text-ink-2">
                      <input type="checkbox" className="mt-0.5" checked={r.questionIds.includes(q.question_id)}
                        onChange={(e) => changeRating(i, {
                          questionIds: e.target.checked ? [...r.questionIds, q.question_id] : r.questionIds.filter((x) => x !== q.question_id),
                        })} />
                      <span>{q.question} <span className="text-ink-3">({(q.selected_tags || []).length}/{q.total_tags} points covered)</span></span>
                    </label>
                  ))}
                </div>
              </details>
            )}
          </fieldset>
        );
      })}

      <fieldset className="space-y-2 border-t border-line pt-4">
        <legend className="text-sm font-semibold text-ink">Overall recommendation<span className="ml-0.5 text-danger" aria-hidden="true">*</span></legend>
        <div className="grid grid-cols-2 gap-1.5">
          {RECOMMENDATIONS.map((rec) => (
            <label key={rec.id} className={cn('flex cursor-pointer items-center gap-2 rounded-md border px-2.5 py-1.5 text-sm',
              form.recommendation === rec.id ? 'border-primary bg-primary-soft text-ink' : 'border-line text-ink-2 hover:bg-subtle')}>
              <input type="radio" name="recommendation" checked={form.recommendation === rec.id} onChange={() => change({ recommendation: rec.id })} />
              {rec.label}
            </label>
          ))}
        </div>
      </fieldset>
      <Field label="Summary" htmlFor="scorecard-summary" required>
        <Textarea id="scorecard-summary" value={form.summary} maxLength={4000} className="min-h-[4.5rem]" onChange={(e) => change({ summary: e.target.value })} />
      </Field>

      {issues.length > 0 && (
        <ul className="space-y-1 rounded-lg bg-warning-soft px-3 py-2 text-xs text-warning ring-1 ring-inset ring-warning/25" role="alert">
          {issues.map((p) => <li key={p}>{p}</li>)}
        </ul>
      )}
      <Button onClick={submit} disabled={submitting} className="w-full">
        {submitting ? <Loader2 className="animate-spin" aria-hidden="true" /> : <Send aria-hidden="true" />}
        {submitting ? 'Submitting…' : submitted ? 'Submit changes' : 'Submit scorecard'}
      </Button>
    </div>
  );
};

/* ── Dossier: requests, evidence summary, AI brief ───────────────────── */

const Brief = ({ jobId, candidateId }) => {
  const [brief, setBrief] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const run = async () => {
    setBusy(true); setError(null);
    try { setBrief(await getEvidenceBrief(jobId, candidateId)); } catch (err) { setError(err.message); } finally { setBusy(false); }
  };
  return (
    <div className="space-y-2">
      <Button size="sm" variant="secondary" onClick={run} disabled={busy}>
        {busy ? <Loader2 className="animate-spin" aria-hidden="true" /> : <Sparkles aria-hidden="true" />}
        {busy ? 'Summarising…' : brief ? 'Rewrite evidence brief' : 'AI evidence brief'}
      </Button>
      {error && <p className="flex items-start gap-2 text-xs text-warning"><AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden="true" />{error}</p>}
      {brief && (
        <div className="space-y-2 rounded-lg border border-line bg-surface p-3 text-sm">
          <p className="text-xs font-medium text-ink-3">AI summary of the submitted notes only. Check the notes below before relying on it.</p>
          <p className="leading-relaxed text-ink-2">{brief.summary}</p>
          {brief.points.length > 0 && (
            <ul className="list-disc space-y-1 pl-5 text-ink-2">
              {brief.points.map((p, i) => (
                <li key={i}>{p.competency && <span className="font-medium text-ink">{p.competency}: </span>}{p.text} <span className="text-xs text-ink-3">({p.cited.join(', ')})</span></li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
};

const Summary = ({ summary }) => (
  <div className="space-y-4">
    <div className="flex items-center gap-4">
      <ScoreRing value={summary.overallScore} label="Interview evidence" sublabel="Weighted scorecards" />
      <dl className="grid flex-1 grid-cols-2 gap-x-3 gap-y-1 text-xs">
        {RECOMMENDATIONS.map((r) => (
          <div key={r.id} className="flex justify-between gap-2"><dt className="text-ink-3">{r.label}</dt><dd className="font-medium tabular-nums text-ink">{summary.recommendations[r.id]}</dd></div>
        ))}
      </dl>
    </div>
    <ul className="space-y-3">
      {summary.competencies.map((c) => (
        <li key={c.id} className="rounded-lg border border-line bg-surface p-3">
          <div className="flex flex-wrap items-center justify-between gap-2 text-sm">
            <span className="font-medium text-ink">{c.name}</span>
            <span className="flex items-center gap-2 text-xs tabular-nums text-ink-3">
              {c.mean == null ? 'Not rated' : <>mean <span className="font-semibold text-ink">{c.mean}/4</span> · spread {c.spread} · {c.ratings} rating{c.ratings === 1 ? '' : 's'}</>}
              {c.disagreement && <Tag className="bg-warning-soft text-warning">Interviewers disagree</Tag>}
            </span>
          </div>
          {c.evidence.length > 0 && (
            <ul className="mt-2 space-y-2">
              {c.evidence.map((e, i) => (
                <li key={i} className="border-l-2 border-line pl-2.5 text-xs">
                  <p className="whitespace-pre-wrap leading-relaxed text-ink-2">{e.evidence || <span className="text-ink-3">No note</span>}</p>
                  <p className="mt-0.5 text-ink-3">{e.author} · {formatDate(e.date)} · {e.rating == null ? 'not assessed' : `rated ${e.rating}/4`}</p>
                  {e.questions.map((q) => (
                    <p key={q.id} className="mt-0.5 text-ink-3">Question: {q.question} ({q.covered.length}/{q.total} points covered)</p>
                  ))}
                </li>
              ))}
            </ul>
          )}
        </li>
      ))}
    </ul>
    {summary.summaries.length > 0 && (
      <div>
        <h4 className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-ink-3">Interviewer summaries</h4>
        <ul className="space-y-2 text-xs">
          {summary.summaries.map((s, i) => (
            <li key={i}><span className="font-medium text-ink">{s.author} · {REC_LABEL[s.recommendation] || '—'}:</span> <span className="whitespace-pre-wrap text-ink-2">{s.summary}</span></li>
          ))}
        </ul>
      </div>
    )}
  </div>
);

/** Resume and verification evidence, kept apart from the interview evidence */
const ResumeEvidence = ({ candidate }) => {
  const verified = (candidate.skillMatches || []).filter((m) => Number(m.score) >= 7).map((m) => m.skill);
  return (
    <div className="rounded-lg border border-dashed border-line p-3 text-xs">
      <p className="mb-1.5 font-semibold uppercase tracking-wide text-ink-3">Separate source: resume and verification</p>
      <p className="text-ink-2">Credibility <span className="font-medium tabular-nums text-ink">{candidate.verificationScore == null ? '—' : `${candidate.verificationScore}%`}</span></p>
      <p className="mt-1 text-ink-2">Job skills with strong resume evidence (7/10 or more): {verified.length ? verified.join(', ') : 'none'}</p>
    </div>
  );
};

export const InterviewScorecards = ({ jobId, candidate, compact = false }) => {
  const { toast } = useToast();
  const [data, setData] = useState(null);
  const [summary, setSummary] = useState(null);
  const [members, setMembers] = useState([]);
  const [pick, setPick] = useState('');
  const [error, setError] = useState(null);
  const [filling, setFilling] = useState(false);

  const load = useCallback(async () => {
    setError(null);
    try {
      const d = await getScorecards(jobId, candidate.id);
      setData(d);
      setSummary(d.locked || !d.template.length ? null : await getEvidenceSummary(jobId, candidate.id));
    } catch (err) { setError(err.message); }
  }, [jobId, candidate.id]);
  useEffect(() => { load(); }, [load]);
  useEffect(() => { getOrg().then((o) => setMembers(o.members || [])).catch(() => setMembers([])); }, []);

  const ask = async () => {
    try { await requestScorecard(jobId, candidate.id, pick); setPick(''); load(); } catch (err) {
      toast({ title: 'Could not request a scorecard', description: err.message, variant: 'destructive' });
    }
  };
  const withdraw = async (uid) => {
    try { await cancelScorecardRequest(jobId, candidate.id, uid); load(); } catch (err) {
      toast({ title: 'Could not withdraw the request', description: err.message, variant: 'destructive' });
    }
  };

  const asked = new Set((data?.interviewers || []).map((i) => i.uid));
  const submittedCount = (data?.interviewers || []).filter((i) => i.status === 'submitted').length;

  return (
    <section aria-labelledby="scorecards-heading" className="space-y-3">
      <div className="flex items-center justify-between gap-3">
        <h3 id="scorecards-heading" className="flex items-center gap-2 text-sm font-semibold text-ink">
          <ClipboardCheck className="h-4 w-4 text-ink-3" aria-hidden="true" /> Interview scorecards
          {data?.interviewers.length > 0 && <span className="font-normal tabular-nums text-ink-3">{submittedCount}/{data.interviewers.length} submitted</span>}
        </h3>
        {!compact && data?.template.length > 0 && (
          <Button size="sm" variant="ghost" onClick={() => setFilling((v) => !v)} aria-expanded={filling}>
            {filling ? <><X aria-hidden="true" /> Close form</> : data.mine?.status === 'submitted' ? 'Edit my scorecard' : 'Fill in my scorecard'}
          </Button>
        )}
      </div>

      {error ? <p className="text-sm text-danger">{error}</p> : !data ? <Skeleton className="h-16" /> : !data.template.length ? (
        <p className="text-sm text-ink-3">This job has no scorecard yet. Set one up on the job page under Interview scorecard.</p>
      ) : (
        <>
          {filling && <Card><ScorecardForm jobId={jobId} candidateId={candidate.id} onSubmitted={() => { setFilling(false); load(); }} /></Card>}

          {data.interviewers.length > 0 && (
            <ul className="flex flex-wrap gap-1.5">
              {data.interviewers.map((i) => (
                <li key={i.uid}>
                  <Tag tone={i.status === 'submitted' ? 'primary' : 'neutral'} className="gap-1">
                    {i.name} · {STATUS_LABEL[i.status]}
                    {i.status === 'requested' && (
                      <button type="button" onClick={() => withdraw(i.uid)} aria-label={`Withdraw request to ${i.name}`} className="rounded hover:text-danger">
                        <X className="h-3 w-3" aria-hidden="true" />
                      </button>
                    )}
                  </Tag>
                </li>
              ))}
            </ul>
          )}

          {members.length > 0 && (
            <div className="flex gap-2">
              <label htmlFor={`ask-${candidate.id}`} className="sr-only">Ask a teammate for a scorecard</label>
              <Select id={`ask-${candidate.id}`} value={pick} onChange={(e) => setPick(e.target.value)} className="h-8 flex-1 text-xs">
                <option value="">Ask a teammate to interview…</option>
                {members.filter((m) => !asked.has(m.uid)).map((m) => <option key={m.uid} value={m.uid}>{m.name || m.email}</option>)}
              </Select>
              <Button size="sm" variant="secondary" onClick={ask} disabled={!pick}><UserPlus aria-hidden="true" /> Ask</Button>
            </div>
          )}

          {data.locked ? (
            <p className="flex items-start gap-2 rounded-lg bg-subtle px-3 py-2 text-xs text-ink-2">
              <Lock className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden="true" />
              Submit your own scorecard to see the others. They stay hidden until then so they can't sway your ratings.
            </p>
          ) : summary && summary.submitted > 0 ? (
            <>
              <Summary summary={summary} />
              <Brief jobId={jobId} candidateId={candidate.id} />
            </>
          ) : (
            <p className="text-sm text-ink-3">No submitted scorecards yet.</p>
          )}
          <ResumeEvidence candidate={candidate} />
        </>
      )}
    </section>
  );
};
