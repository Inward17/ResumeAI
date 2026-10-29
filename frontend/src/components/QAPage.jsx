import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { Mail, Phone, Send, XCircle, Loader2, Bot, Briefcase, HelpCircle, Check, RefreshCw } from 'lucide-react';
import { getJob, getJobCandidate, getInterviewQuestions, submitEvaluation, updateCandidateStatus } from '../services/jobService';
import { useToast } from '../hooks/use-toast';
import { cn } from '../lib/utils';
import FactCheckerBot from './FactCheckerBot';
import { ConfirmDialog } from './Modal';
import {
  Card, CardHeader, PageContainer, BackLink, ScoreRing, StatusPill, Initials, EmptyState, Button, Skeleton,
} from './common';

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

const QAPage = () => {
  const { jobId, candidateId } = useParams();
  const navigate = useNavigate();
  const { toast } = useToast();
  const pipelineUrl = `/jobs/${jobId}?candidate=${candidateId}`;

  const [job, setJob] = useState(null);
  const [candidate, setCandidate] = useState(null);
  const [loadError, setLoadError] = useState(null);
  const [questions, setQuestions] = useState([]);
  const [loadingQuestions, setLoadingQuestions] = useState(true);
  const [questionError, setQuestionError] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [isFactCheckerOpen, setIsFactCheckerOpen] = useState(false);
  const [selectedKeywords, setSelectedKeywords] = useState({}); // { [questionId]: ["tag", ...] }
  const [confirmReject, setConfirmReject] = useState(false);

  useEffect(() => {
    Promise.all([getJob(jobId), getJobCandidate(jobId, candidateId)])
      .then(([j, c]) => { setJob(j); setCandidate(c); })
      .catch((err) => setLoadError(err.message));
  }, [jobId, candidateId]);

  const loadQuestions = useCallback(async () => {
    setLoadingQuestions(true);
    setQuestionError(null);
    try {
      const data = await getInterviewQuestions(jobId, candidateId);
      setQuestions(data.questions || []);
    } catch {
      setQuestionError('Could not generate interview questions.');
    } finally {
      setLoadingQuestions(false);
    }
  }, [jobId, candidateId]);

  useEffect(() => { loadQuestions(); }, [loadQuestions]);

  const handleToggleTag = (questionId, tag) => {
    setSelectedKeywords((prev) => {
      const current = prev[questionId] || [];
      return { ...prev, [questionId]: current.includes(tag) ? current.filter((t) => t !== tag) : [...current, tag] };
    });
  };

  const totalPossible = questions.reduce((sum, q) => sum + (q.tags?.length || 0), 0);
  const totalSelected = Object.values(selectedKeywords).reduce((sum, tags) => sum + tags.length, 0);
  const aggregatePercent = totalPossible > 0 ? Math.round((totalSelected / totalPossible) * 100) : 0;

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
      navigate(pipelineUrl);
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
      navigate(pipelineUrl);
    } catch (err) {
      toast({ title: 'Could not reject candidate', description: err.message, variant: 'destructive' });
    }
  };

  if (loadError) {
    return (
      <PageContainer>
        <Card>
          <EmptyState icon={HelpCircle} title="Candidate not found" description={loadError}
            action={<Button onClick={() => navigate(`/jobs/${jobId}`)}>Back to pipeline</Button>} />
        </Card>
      </PageContainer>
    );
  }

  const canSubmit = !submitting && !loadingQuestions && !questionError && !!candidate;

  return (
    <div className={cn('flex min-h-full flex-col', isFactCheckerOpen && 'md:pr-[380px]')}>
      <PageContainer className="flex-1 pb-8 md:pb-8">
        <BackLink to={pipelineUrl}>Back to pipeline</BackLink>

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
          {!isFactCheckerOpen && (
            <Button variant="secondary" onClick={() => setIsFactCheckerOpen(true)} disabled={!candidate}>
              <Bot className="text-primary-text" aria-hidden="true" /> Ask the fact checker
            </Button>
          )}
        </div>

        {/* With the fact checker open the page loses 380px, so only go two-column on very wide screens */}
        <div className={cn('grid grid-cols-1 items-start gap-6',
          isFactCheckerOpen ? '2xl:grid-cols-[300px_minmax(0,1fr)]' : 'lg:grid-cols-[300px_minmax(0,1fr)]')}>
          {/* Scores — stays in view while scrolling the questions */}
          <div className={cn('grid grid-cols-1 gap-4 sm:grid-cols-2',
            isFactCheckerOpen ? '2xl:sticky 2xl:top-6 2xl:grid-cols-1' : 'lg:sticky lg:top-6 lg:grid-cols-1')}>
            <Card>
              <CardHeader title="Interview score" />
              <div className="p-4">
                <div className="flex justify-center"><ScoreRing value={loadingQuestions ? null : aggregatePercent} size={96} stroke={8} /></div>
                <p className="mt-3 text-center text-sm text-ink-3">
                  <span className="font-medium tabular-nums text-ink">{totalSelected}</span> of <span className="font-medium tabular-nums text-ink">{totalPossible}</span> key points covered
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
                <EmptyState icon={XCircle} title={questionError} description="The AI service may be temporarily unavailable."
                  action={<Button variant="secondary" onClick={loadQuestions}><RefreshCw aria-hidden="true" /> Try again</Button>} />
              </Card>
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
            Score <span className="font-semibold tabular-nums text-ink">{aggregatePercent}%</span>
            <span className="mx-2 text-line-strong">·</span>
            {totalSelected}/{totalPossible} points
          </p>
          <div className="flex w-full gap-2 sm:w-auto">
            <Button variant="danger-outline" onClick={() => setConfirmReject(true)} disabled={!candidate} className="flex-1 sm:flex-none">
              <XCircle aria-hidden="true" /> Reject
            </Button>
            <Button onClick={handleSubmit} disabled={!canSubmit} className="flex-[2] sm:flex-none">
              {submitting ? <Loader2 className="animate-spin" aria-hidden="true" /> : <Send aria-hidden="true" />}
              {submitting ? 'Submitting…' : `Submit evaluation${loadingQuestions ? '' : ` · ${aggregatePercent}%`}`}
            </Button>
          </div>
        </div>
      </div>

      {isFactCheckerOpen && candidate && (
        <aside className="fixed inset-0 z-[45] flex flex-col bg-surface md:inset-y-0 md:left-auto md:right-0 md:w-[380px] md:border-l md:border-line md:shadow-pop"
          aria-label="AI fact checker">
          <FactCheckerBot candidateId={candidate.id} candidateName={candidate.name} onClose={() => setIsFactCheckerOpen(false)} />
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
