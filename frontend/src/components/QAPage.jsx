import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useLocation, useNavigate, useParams } from 'react-router-dom';
import { Mail, Phone, Send, XCircle, Loader2, Bot, Briefcase, HelpCircle, Check, RefreshCw, AlertTriangle, UserRound, X, ClipboardCheck } from 'lucide-react';
import {
  getJob, getJobCandidate, getInterviewQuestions, getEvaluation, submitEvaluation, updateCandidateStatus,
} from '../services/jobService';
import { useToast } from '../hooks/use-toast';
import { cn } from '../lib/utils';
import FactCheckerBot from './FactCheckerBot';
import CandidateDossier from './CandidateDossier';
import { ScorecardForm } from './Scorecards';
import { loadPreferences } from '../lib/preferences';
import { ConfirmDialog } from './Modal';
import {
  Card, CardHeader, PageContainer, BackLink, ScoreRing, StatusPill, Initials, EmptyState, Button, IconButton, Skeleton, formatDate,
} from './common';
import { usePermissions } from '../lib/permissions';

const TopicTag = ({ label, selected, onClick }) => (
  <button
    type="button"
    onClick={onClick}
    aria-pressed={selected}
    className={cn(
      'inline-flex items-center gap-1.5 rounded-md border px-2.5 py-1.5 text-sm transition-colors',
      selected
        ? 'border-success/40 bg-success-soft font-medium text-success'
        : 'border-line-strong bg-surface text-ink-2 hover:border-primary/50 hover:bg-subtle',
    )}
  >
    <span className={cn('flex h-4 w-4 items-center justify-center rounded border',
      selected ? 'border-success bg-success text-surface' : 'border-line-strong')} aria-hidden="true">
      {selected && <Check className="h-3 w-3" strokeWidth={3} />}
    </span>
    {label}
  </button>
);

const QuestionCard = ({ index, question, tags, selectedTags, onToggleTag }) => {
  const selected = selectedTags.length;
  const total = tags.length;
  const done = selected === total && total > 0;
  return (
    <Card className="p-5">
      <div className="mb-2 flex items-center justify-between gap-3">
        <p className="text-xs font-medium text-ink-3">Question {index}</p>
        <span className={cn('rounded-md px-2 py-0.5 text-xs font-medium tabular-nums',
          done ? 'bg-success-soft text-success' : selected > 0 ? 'bg-primary-soft text-primary-soft-fg' : 'bg-subtle text-ink-3')}>
          {selected}/{total} covered
        </span>
      </div>
      <p className="mb-4 font-serif text-[1.45rem] leading-snug text-ink">{question}</p>
      <p className="mb-2 text-xs text-ink-3">Tick each point the candidate covered</p>
      <div className="flex flex-wrap gap-2">
        {tags.map((tag, i) => (
          <TopicTag key={i} label={tag} selected={selectedTags.includes(tag)} onClick={() => onToggleTag(tag)} />
        ))}
      </div>
    </Card>
  );
};

const PANEL_TABS = [{ id: 'candidate', label: 'Candidate' }, { id: 'scorecard', label: 'Scorecard' }, { id: 'factChecker', label: 'Fact checker' }];
const PANEL_KEY = 'resumeai.interviewPanel';
// The open tab (or closed) is remembered for this browser session only
const readPanel = () => {
  try { const v = sessionStorage.getItem(PANEL_KEY); return PANEL_TABS.some((t) => t.id === v) ? v : null; } catch { return null; }
};
const writePanel = (v) => {
  try { if (v) sessionStorage.setItem(PANEL_KEY, v); else sessionStorage.removeItem(PANEL_KEY); } catch { /* storage blocked */ }
};

const QAPage = () => {
  const { jobId, candidateId } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const { toast } = useToast();
  // Go back to wherever the interview was started from (pipeline or Interviews page)
  const returnTo = location.state?.from || `/jobs/${jobId}?candidate=${candidateId}`;
  const returnLabel = location.state?.fromLabel || 'Back to pipeline';
  const leave = () => navigate(returnTo, { replace: true });

  const [job, setJob] = useState(null);
  const [candidate, setCandidate] = useState(null);
  const [loadError, setLoadError] = useState(null);
  const [questions, setQuestions] = useState([]);
  const [loadingQuestions, setLoadingQuestions] = useState(true);
  const [questionError, setQuestionError] = useState(null);
  // The cover letter changed after these questions were generated
  const [questionsStale, setQuestionsStale] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [panel, setPanel] = useState(readPanel); // null (closed) | 'candidate' | 'scorecard' | 'factChecker'
  // Visited tabs stay mounted while the panel is open, so the chat survives a tab switch
  const [mounted, setMounted] = useState({});
  const [prefs] = useState(loadPreferences);
  const tabRefs = useRef({});
  const openerRefs = useRef({});
  const isPanelOpen = panel != null;
  const [selectedKeywords, setSelectedKeywords] = useState({}); // { [questionId]: ["tag", ...] }
  const [lastSubmitted, setLastSubmitted] = useState(null);
  const [confirmReject, setConfirmReject] = useState(false);
  const { can } = usePermissions();

  useEffect(() => {
    Promise.all([getJob(jobId), getJobCandidate(jobId, candidateId)])
      .then(([j, c]) => { setJob(j); setCandidate(c); })
      .catch((err) => setLoadError(err.message));
  }, [jobId, candidateId]);

  const loadQuestions = useCallback(async (regenerate) => {
    setLoadingQuestions(true);
    setQuestionError(null);
    try {
      const [data, previous] = await Promise.all([
        // Called from click handlers too, so only an explicit true regenerates
        getInterviewQuestions(jobId, candidateId, regenerate === true),
        getEvaluation(jobId, candidateId).catch(() => null),
      ]);
      const qs = data.questions || [];
      setQuestions(qs);
      setQuestionsStale(!!data.stale);
      // New questions: ticks for the old ones no longer apply
      if (regenerate === true) setSelectedKeywords({});
      // Re-opening an interview restores the ticks from the last submission
      if (previous) {
        const restored = {};
        (previous.questions || []).forEach((pq) => {
          const q = qs.find((x) => x.id === pq.question_id && x.question === pq.question);
          if (q) restored[q.id] = (pq.selected_tags || []).filter((t) => q.tags?.includes(t));
        });
        setSelectedKeywords(restored);
        setLastSubmitted(previous.submitted_at);
      }
    } catch (err) {
      setQuestionError(err.message || 'Could not generate interview questions.');
    } finally {
      setLoadingQuestions(false);
    }
  }, [jobId, candidateId]);

  useEffect(() => { loadQuestions(); }, [loadQuestions]);

  useEffect(() => {
    writePanel(panel);
    if (panel) setMounted((m) => (m[panel] ? m : { ...m, [panel]: true }));
  }, [panel]);

  const openPanel = (tab) => {
    const wasOpen = isPanelOpen;
    setPanel(tab);
    // A newly opened fact checker focuses its own input; otherwise focus the tab
    if (wasOpen || tab !== 'factChecker') requestAnimationFrame(() => tabRefs.current[tab]?.focus());
  };
  const closePanel = () => {
    const opener = openerRefs.current[panel];
    setPanel(null);
    setMounted({});
    requestAnimationFrame(() => opener?.focus());
  };
  const onTabKeyDown = (e) => {
    const n = PANEL_TABS.length;
    const i = PANEL_TABS.findIndex((t) => t.id === panel);
    const next = { ArrowRight: (i + 1) % n, ArrowLeft: (i - 1 + n) % n, Home: 0, End: n - 1 }[e.key];
    if (next == null) return;
    e.preventDefault();
    setPanel(PANEL_TABS[next].id);
    tabRefs.current[PANEL_TABS[next].id]?.focus();
  };

  const handleToggleTag = (questionId, tag) => {
    setSelectedKeywords((prev) => {
      const current = prev[questionId] || [];
      return { ...prev, [questionId]: current.includes(tag) ? current.filter((t) => t !== tag) : [...current, tag] };
    });
  };

  const totalPossible = questions.reduce((sum, q) => sum + (q.tags?.length || 0), 0);
  const totalSelected = Object.values(selectedKeywords).reduce((sum, tags) => sum + tags.length, 0);
  const aggregatePercent = totalPossible > 0 ? Math.round((totalSelected / totalPossible) * 100) : 0;
  // No questions (still loading or AI down) means there's no score to show yet
  const hasScore = !loadingQuestions && !questionError && totalPossible > 0;

  const handleSubmit = async () => {
    setSubmitting(true);
    try {
      await submitEvaluation(jobId, candidateId, {
        candidate_name: candidate?.name || '',
        job_title: job?.title || '',
        questions: questions.map((q) => ({
          question_id: q.id,
          question: q.question,
          total_tags: q.tags?.length || 0,
          selected_tags: selectedKeywords[q.id] || [],
          score: q.tags?.length > 0 ? (selectedKeywords[q.id]?.length || 0) / q.tags.length : 0,
        })),
        total_score: aggregatePercent,
        total_selected: totalSelected,
        total_possible: totalPossible,
      });
      toast({ title: 'Evaluation submitted', description: `${candidate?.name}: ${aggregatePercent}% of key points covered.` });
      leave();
    } catch (err) {
      toast({ title: 'Could not submit evaluation', description: err.message, variant: 'destructive' });
    } finally {
      setSubmitting(false);
    }
  };

  const handleReject = async () => {
    try {
      await updateCandidateStatus(jobId, candidateId, 'Rejected');
      toast({ title: 'Candidate rejected', description: candidate?.name });
      leave();
    } catch (err) {
      toast({ title: 'Could not reject candidate', description: err.message, variant: 'destructive' });
    }
  };

  if (loadError) {
    return (
      <PageContainer>
        <Card>
          <EmptyState icon={HelpCircle} title="Candidate not found" description={loadError}
            action={<Button onClick={leave}>{returnLabel}</Button>} />
        </Card>
      </PageContainer>
    );
  }

  const canSubmit = !submitting && !loadingQuestions && !questionError && !!candidate;

  return (
    <div className={cn('flex min-h-full flex-col', isPanelOpen && candidate && 'md:pr-[380px]')}>
      <PageContainer className="flex-1 pb-8 md:pb-8">
        <BackLink to={returnTo}>{returnLabel}</BackLink>

        {/* Candidate header */}
        <div className="mb-6 flex flex-col gap-4 md:mb-8 md:flex-row md:items-center md:justify-between">
          {candidate ? (
            <div className="flex min-w-0 items-center gap-4">
              <Initials name={candidate.name} className="h-12 w-12 text-base" />
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                  <h1 className="font-serif text-[2rem] leading-tight text-ink md:text-[2.5rem]">{candidate.name}</h1>
                  <StatusPill status={candidate.status} />
                </div>
                <div className="mt-1 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-ink-3">
                  {job && <span className="flex items-center gap-1.5"><Briefcase className="h-3.5 w-3.5" aria-hidden="true" />{job.title}</span>}
                  {candidate.email && <a href={`mailto:${candidate.email}`} className="flex items-center gap-1.5 hover:text-primary-text"><Mail className="h-3.5 w-3.5" aria-hidden="true" />{candidate.email}</a>}
                  {candidate.phone && <a href={`tel:${candidate.phone}`} className="flex items-center gap-1.5 hover:text-primary-text"><Phone className="h-3.5 w-3.5" aria-hidden="true" />{candidate.phone}</a>}
                </div>
              </div>
            </div>
          ) : (
            <div className="flex items-center gap-4"><Skeleton className="h-12 w-12 rounded-full" /><Skeleton className="h-7 w-56" /></div>
          )}
          <div className="flex flex-wrap gap-2">
            <Button variant="secondary" ref={(el) => { openerRefs.current.candidate = el; }} onClick={() => openPanel('candidate')}
              disabled={!candidate} aria-expanded={panel === 'candidate'} aria-controls="interview-panel">
              <UserRound className="text-primary-text" aria-hidden="true" /> View candidate
            </Button>
            <Button variant="secondary" ref={(el) => { openerRefs.current.scorecard = el; }} onClick={() => openPanel('scorecard')}
              disabled={!candidate} aria-expanded={panel === 'scorecard'} aria-controls="interview-panel">
              <ClipboardCheck className="text-primary-text" aria-hidden="true" /> Fill scorecard
            </Button>
            <Button variant="secondary" ref={(el) => { openerRefs.current.factChecker = el; }} onClick={() => openPanel('factChecker')}
              disabled={!candidate} aria-expanded={panel === 'factChecker'} aria-controls="interview-panel">
              <Bot className="text-primary-text" aria-hidden="true" /> Ask the fact checker
            </Button>
          </div>
        </div>

        {/* With the fact checker open the page loses 380px, so only go two-column on very wide screens */}
        <div className={cn('grid grid-cols-1 items-start gap-6',
          isPanelOpen ? '2xl:grid-cols-[300px_minmax(0,1fr)]' : 'lg:grid-cols-[300px_minmax(0,1fr)]')}>
          {/* Scores — stays in view while scrolling the questions */}
          <div className={cn('grid grid-cols-1 gap-4 sm:grid-cols-2',
            isPanelOpen ? '2xl:sticky 2xl:top-6 2xl:grid-cols-1' : 'lg:sticky lg:top-6 lg:grid-cols-1')}>
            <Card>
              <CardHeader title="Interview score" />
              <div className="p-4">
                <div className="flex justify-center"><ScoreRing value={hasScore ? aggregatePercent : null} size={96} stroke={8} /></div>
                <p className="mt-3 text-center text-sm text-ink-3">
                  {hasScore ? (
                    <><span className="font-medium tabular-nums text-ink">{totalSelected}</span> of <span className="font-medium tabular-nums text-ink">{totalPossible}</span> key points covered</>
                  ) : questionError ? 'No score without interview questions' : 'Waiting for questions'}
                </p>
                {questions.length > 0 && (
                  <ul className="mt-4 space-y-2 border-t border-line pt-4">
                    {questions.map((q, i) => {
                      const sel = (selectedKeywords[q.id] || []).length;
                      const tot = q.tags?.length || 0;
                      return (
                        <li key={q.id} className="flex items-center gap-3 text-xs">
                          <span className="w-6 text-ink-3">Q{i + 1}</span>
                          <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-subtle">
                            <div className={cn('h-full rounded-full transition-all', sel === tot && tot > 0 ? 'bg-success' : 'bg-primary')}
                              style={{ width: tot ? `${(sel / tot) * 100}%` : '0%' }} />
                          </div>
                          <span className="w-8 text-right font-medium tabular-nums text-ink-2">{sel}/{tot}</span>
                        </li>
                      );
                    })}
                  </ul>
                )}
              </div>
            </Card>

            <Card>
              <CardHeader title="Screening scores" />
              <div className="grid grid-cols-2 gap-3 p-4">
                <ScoreRing value={candidate?.jdMatchScore ?? null} label="Role match" />
                <ScoreRing value={candidate?.verificationScore ?? null} label="Credibility" />
              </div>
            </Card>
          </div>

          {/* Questions */}
          <div>
            <h2 className="mb-4 text-base font-semibold text-ink">Questions for this candidate</h2>
            {!loadingQuestions && lastSubmitted && (
              <p className="mb-4 rounded-md border border-line bg-subtle px-3 py-2 text-sm text-ink-2">
                Evaluation submitted on {formatDate(lastSubmitted)}. Your ticks are restored; submitting again replaces it.
              </p>
            )}

            {loadingQuestions && (
              <div className="space-y-4" role="status">
                <div className="flex items-center gap-3 rounded-lg border border-primary/20 bg-primary-soft p-4">
                  <Loader2 className="h-5 w-5 animate-spin text-primary-text" aria-hidden="true" />
                  <div>
                    <p className="text-sm font-medium text-ink">Generating questions…</p>
                    <p className="text-xs text-ink-3">Tailored to the job description and this resume. Usually takes a few seconds.</p>
                  </div>
                </div>
                {[1, 2, 3].map((i) => <Skeleton key={i} className="h-36 rounded-lg" />)}
              </div>
            )}

            {!loadingQuestions && questionError && (
              <Card>
                <EmptyState icon={XCircle} title="Interview questions unavailable"
                  description={`${questionError} Scoring and submitting the evaluation need the questions, so they're disabled too.`}
                  action={<Button variant="secondary" onClick={loadQuestions}><RefreshCw aria-hidden="true" /> Try again</Button>} />
              </Card>
            )}

            {!loadingQuestions && !questionError && questionsStale && (
              <div className="mb-4 flex flex-col gap-3 rounded-lg bg-warning-soft px-4 py-3 text-sm text-warning ring-1 ring-inset ring-warning/25 sm:flex-row sm:items-center" role="status">
                <AlertTriangle className="h-4 w-4 shrink-0" aria-hidden="true" />
                <p className="flex-1">
                  The cover letter changed after these questions were generated, so they don't use it.
                  Regenerating replaces them{lastSubmitted ? ' and clears the ticks restored from the last evaluation' : ''}.
                </p>
                <Button size="sm" variant="secondary" onClick={() => loadQuestions(true)}>
                  <RefreshCw aria-hidden="true" /> Regenerate questions
                </Button>
              </div>
            )}

            {!loadingQuestions && !questionError && (
              <div className="space-y-4">
                {questions.map((q, i) => (
                  <QuestionCard key={q.id} index={i + 1} question={q.question} tags={q.tags || []}
                    selectedTags={selectedKeywords[q.id] || []} onToggleTag={(tag) => handleToggleTag(q.id, tag)} />
                ))}
              </div>
            )}
          </div>
        </div>
      </PageContainer>

      {/* Action bar — sticks to the bottom of the scrolling page */}
      <div className="sticky bottom-0 z-20 border-t border-line bg-surface/95 backdrop-blur">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-3 px-4 py-3 md:px-8">
          <p className="hidden text-sm text-ink-3 sm:block">
            {hasScore ? (
              <>
                Score <span className="font-semibold tabular-nums text-ink">{aggregatePercent}%</span>
                <span className="mx-2 text-line-strong">·</span>
                {totalSelected}/{totalPossible} points
              </>
            ) : questionError ? 'Scoring unavailable without questions' : 'Generating questions…'}
          </p>
          <div className="flex w-full gap-2 sm:w-auto">
            {can('candidate.status') && (
              <Button variant="danger-outline" onClick={() => setConfirmReject(true)} disabled={!candidate} className="flex-1 sm:flex-none">
                <XCircle aria-hidden="true" /> Reject
              </Button>
            )}
            <Button onClick={handleSubmit} disabled={!canSubmit} className="flex-[2] sm:flex-none">
              {submitting ? <Loader2 className="animate-spin" aria-hidden="true" /> : <Send aria-hidden="true" />}
              {submitting ? 'Submitting…' : `Submit evaluation${hasScore ? ` · ${aggregatePercent}%` : ''}`}
            </Button>
          </div>
        </div>
      </div>

      {isPanelOpen && candidate && (
        <aside id="interview-panel" aria-label={`${candidate.name}: candidate, scorecard and fact checker`}
          className="fixed inset-0 z-[45] flex flex-col bg-surface md:inset-y-0 md:left-auto md:right-0 md:w-[380px] md:border-l md:border-line md:shadow-pop"
          onKeyDown={(e) => { if (e.key === 'Escape') { e.stopPropagation(); closePanel(); } }}>
          <div className="flex h-14 shrink-0 items-center justify-between gap-2 border-b border-line px-3">
            <div role="tablist" aria-label="Interview side panel" className="inline-flex gap-0.5 rounded-md border border-line bg-subtle p-0.5">
              {PANEL_TABS.map((t) => {
                const active = panel === t.id;
                return (
                  <button key={t.id} type="button" role="tab" id={`panel-tab-${t.id}`} aria-controls={`panel-${t.id}`}
                    aria-selected={active} tabIndex={active ? 0 : -1} ref={(el) => { tabRefs.current[t.id] = el; }}
                    onClick={() => setPanel(t.id)} onKeyDown={onTabKeyDown}
                    className={cn('whitespace-nowrap rounded px-3 py-1.5 text-sm font-medium transition-colors',
                      active ? 'bg-surface text-ink shadow-sm' : 'text-ink-3 hover:text-ink')}>
                    {t.label}
                  </button>
                );
              })}
            </div>
            <IconButton label="Close panel" onClick={closePanel}><X aria-hidden="true" /></IconButton>
          </div>
          {mounted.candidate && (
            <div role="tabpanel" id="panel-candidate" aria-labelledby="panel-tab-candidate" tabIndex={0}
              className={cn('min-h-0 flex-1 overflow-y-auto outline-none', panel !== 'candidate' && 'hidden')}>
              <CandidateDossier compact candidate={candidate} job={job} prefs={prefs} />
            </div>
          )}
          {mounted.scorecard && (
            <div role="tabpanel" id="panel-scorecard" aria-labelledby="panel-tab-scorecard" tabIndex={0}
              className={cn('min-h-0 flex-1 overflow-y-auto outline-none', panel !== 'scorecard' && 'hidden')}>
              <ScorecardForm jobId={jobId} candidateId={candidateId} />
            </div>
          )}
          {mounted.factChecker && (
            <div role="tabpanel" id="panel-factChecker" aria-labelledby="panel-tab-factChecker"
              className={cn('min-h-0 flex-1 flex-col', panel === 'factChecker' ? 'flex' : 'hidden')}>
              <FactCheckerBot showHeader={false} candidateId={candidate.id} candidateName={candidate.name} onClose={closePanel} />
            </div>
          )}
        </aside>
      )}

      <ConfirmDialog
        open={confirmReject}
        onOpenChange={setConfirmReject}
        title={`Reject ${candidate?.name || 'this candidate'}?`}
        description={`They'll be marked Rejected for ${job?.title || 'this job'}. You can change the status later from the pipeline.`}
        confirmLabel="Reject candidate"
        onConfirm={handleReject}
      />
    </div>
  );
};

export default QAPage;
