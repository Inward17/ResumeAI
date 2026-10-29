import React, { useState, useEffect, useCallback } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { ArrowLeft, Mail, Phone, Send, XCircle, CheckCircle, Loader2, Award, Bot, Monitor, Briefcase, HelpCircle } from 'lucide-react';
import { getJob, getJobCandidate, getInterviewQuestions, submitEvaluation, updateCandidateStatus } from '../services/jobService';
import { useToast } from '../hooks/use-toast';
import { cn } from '../lib/utils';
import FactCheckerBot from './FactCheckerBot';
import { Card, PageContainer, ScoreRing, StatusPill, Initials, EmptyState, PrimaryButton, SecondaryButton } from './common';

const TopicTag = ({ label, selected, onClick }) => (
  <button
    type="button"
    onClick={onClick}
    aria-pressed={selected}
    className={cn(
      'rounded-full border px-3 py-1.5 text-xs font-semibold transition-colors',
      selected ? 'border-brand-accent bg-brand-accent text-white' : 'border-brand-soft bg-brand-light text-brand hover:border-brand-accent',
    )}
  >
    {label}
  </button>
);

const QuestionCard = ({ index, question, tags, selectedTags, onToggleTag }) => {
  const selected = selectedTags.length;
  const total = tags.length;
  return (
    <Card className="p-5 md:p-6">
      <div className="mb-2 flex items-center justify-between">
        <p className="text-xs font-bold uppercase tracking-widest text-brand-accent">Question {String(index).padStart(2, '0')}</p>
        <span className={cn('rounded-lg px-2.5 py-1 text-xs font-bold',
          selected === total && total > 0 ? 'bg-emerald-50 text-emerald-800' : selected > 0 ? 'bg-brand-light text-brand' : 'bg-slate-100 text-slate-600')}>
          {selected}/{total} covered
        </span>
      </div>
      <p className="mb-4 text-base font-semibold leading-relaxed text-slate-900">{question}</p>
      <p className="mb-2 text-xs text-slate-500">Tick the points the candidate covered:</p>
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
    if (!window.confirm(`Reject ${candidate?.name || 'this candidate'} for ${job?.title || 'this job'}?`)) return;
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
            action={<PrimaryButton onClick={() => navigate(`/jobs/${jobId}`)}>Back to pipeline</PrimaryButton>} />
        </Card>
      </PageContainer>
    );
  }

  return (
    <div className={cn('flex min-h-full flex-col', isFactCheckerOpen && 'md:pr-[400px]')}>
      <PageContainer className="flex-1 pb-8">
        <Link to={pipelineUrl} className="mb-5 inline-flex items-center gap-2 text-sm font-semibold text-slate-600 hover:text-slate-900">
          <ArrowLeft className="h-4 w-4" aria-hidden="true" /> Back to pipeline
        </Link>

        {/* Candidate header */}
        <div className="mb-8 flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          {candidate ? (
            <div className="flex items-center gap-4">
              <Initials name={candidate.name} className="h-16 w-16 rounded-2xl bg-brand-gradient text-2xl" />
              <div className="min-w-0">
                <p className="text-xs font-bold uppercase tracking-widest text-brand-accent">Interview</p>
                <h1 className="text-2xl font-extrabold tracking-tight text-slate-900 md:text-3xl">{candidate.name}</h1>
                <div className="mt-1 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-slate-600">
                  {job && <span className="flex items-center gap-1.5"><Briefcase className="h-3.5 w-3.5" aria-hidden="true" />{job.title}</span>}
                  {candidate.email && <span className="flex items-center gap-1.5"><Mail className="h-3.5 w-3.5" aria-hidden="true" />{candidate.email}</span>}
                  {candidate.phone && <span className="flex items-center gap-1.5"><Phone className="h-3.5 w-3.5" aria-hidden="true" />{candidate.phone}</span>}
                  <StatusPill status={candidate.status} />
                </div>
              </div>
            </div>
          ) : (
            <div className="flex items-center gap-4"><div className="h-16 w-16 animate-pulse rounded-2xl bg-slate-200" /><div className="h-8 w-56 animate-pulse rounded-lg bg-slate-200" /></div>
          )}
          {!isFactCheckerOpen && (
            <SecondaryButton onClick={() => setIsFactCheckerOpen(true)} disabled={!candidate}>
              <Bot className="h-4 w-4 text-brand-accent" aria-hidden="true" /> AI fact checker
            </SecondaryButton>
          )}
        </div>

        <div className="grid grid-cols-1 gap-6 lg:grid-cols-[340px_1fr]">
          {/* Left column */}
          <div className="space-y-6">
            <Card className="p-5">
              <p className="mb-4 text-xs font-bold uppercase tracking-widest text-slate-500">Screening scores</p>
              <div className="grid grid-cols-2 gap-3">
                <ScoreRing value={candidate?.jdMatchScore ?? null} label="Role match" size={72} stroke={6} />
                <ScoreRing value={candidate?.verificationScore ?? null} label="Credibility" size={72} stroke={6} />
              </div>
            </Card>

            {!loadingQuestions && questions.length > 0 && (
              <Card className="p-5">
                <div className="mb-4 flex items-center gap-2">
                  <Award className="h-4 w-4 text-brand-accent" aria-hidden="true" />
                  <p className="text-xs font-bold uppercase tracking-widest text-slate-500">Interview score</p>
                </div>
                <div className="mb-3 flex justify-center"><ScoreRing value={aggregatePercent} size={100} stroke={8} /></div>
                <p className="text-center text-sm text-slate-600">
                  <span className="font-bold text-slate-900">{totalSelected}</span> of <span className="font-bold text-slate-900">{totalPossible}</span> key points covered
                </p>
                <ul className="mt-4 space-y-2">
                  {questions.map((q, i) => {
                    const sel = (selectedKeywords[q.id] || []).length;
                    const tot = q.tags?.length || 0;
                    return (
                      <li key={q.id} className="flex items-center justify-between text-xs">
                        <span className="text-slate-600">Q{String(i + 1).padStart(2, '0')}</span>
                        <div className="mx-3 h-1.5 flex-1 overflow-hidden rounded-full bg-slate-100">
                          <div className={cn('h-full rounded-full transition-all', sel === tot && tot > 0 ? 'bg-emerald-500' : 'bg-brand-accent')}
                            style={{ width: tot ? `${(sel / tot) * 100}%` : '0%' }} />
                        </div>
                        <span className="font-bold text-slate-700">{sel}/{tot}</span>
                      </li>
                    );
                  })}
                </ul>
              </Card>
            )}
          </div>

          {/* Questions */}
          <div>
            <div className="mb-5 flex items-center gap-2">
              <Monitor className="h-5 w-5 text-brand" aria-hidden="true" />
              <h2 className="text-lg font-extrabold text-slate-900">Interview questions</h2>
            </div>

            {loadingQuestions && (
              <div className="space-y-5" role="status">
                <div className="flex items-center gap-3 rounded-2xl border border-brand-soft bg-brand-light p-4">
                  <Loader2 className="h-5 w-5 animate-spin text-brand-accent" aria-hidden="true" />
                  <div>
                    <p className="text-sm font-bold text-slate-900">Generating questions for this candidate…</p>
                    <p className="text-xs text-slate-600">Based on the job description and their resume.</p>
                  </div>
                </div>
                {[1, 2, 3].map((i) => <div key={i} className="h-40 animate-pulse rounded-2xl border border-slate-200 bg-white" />)}
              </div>
            )}

            {!loadingQuestions && questionError && (
              <Card className="border-red-200 bg-red-50 p-6 text-center">
                <p className="text-sm font-bold text-red-800">{questionError}</p>
                <p className="mt-1 text-xs text-red-700">The AI service may be temporarily unavailable.</p>
                <SecondaryButton onClick={loadQuestions} className="mt-4">Try again</SecondaryButton>
              </Card>
            )}

            {!loadingQuestions && !questionError && (
              <div className="space-y-5">
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
      <div className="sticky bottom-0 z-20 border-t border-slate-200 bg-white/95 shadow-[0_-4px_20px_rgba(0,0,0,0.06)] backdrop-blur">
        <div className="mx-auto flex max-w-7xl flex-col items-center justify-between gap-3 px-4 py-3 md:flex-row md:px-8">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-brand-light">
              <CheckCircle className="h-5 w-5 text-brand-accent" aria-hidden="true" />
            </div>
            <div>
              <p className="text-sm font-bold text-slate-900">
                Interview score: <span className="text-brand-accent">{aggregatePercent}%</span> ({totalSelected}/{totalPossible} points)
              </p>
              <p className="hidden text-xs text-slate-500 md:block">Tick the points the candidate covered, then submit your evaluation.</p>
            </div>
          </div>
          <div className="flex w-full gap-2 md:w-auto">
            <SecondaryButton onClick={handleReject} disabled={!candidate} className="flex-1 whitespace-nowrap py-2 md:flex-none md:py-2.5">
              <XCircle className="h-4 w-4" aria-hidden="true" /> Reject
            </SecondaryButton>
            <PrimaryButton onClick={handleSubmit} disabled={submitting || loadingQuestions || !!questionError || !candidate} className="flex-[2] whitespace-nowrap py-2 md:flex-none md:py-2.5">
              {submitting ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" /> : <Send className="h-4 w-4" aria-hidden="true" />}
              {submitting ? 'Submitting…' : 'Submit evaluation'}
            </PrimaryButton>
          </div>
        </div>
      </div>

      {isFactCheckerOpen && candidate && (
        <aside className="fixed inset-0 z-[60] flex flex-col bg-white md:inset-y-0 md:left-auto md:right-0 md:top-14 md:w-[400px] md:border-l md:border-slate-200 md:shadow-xl"
          aria-label="AI fact checker">
          <FactCheckerBot candidateId={candidate.id} candidateName={candidate.name} onClose={() => setIsFactCheckerOpen(false)} />
        </aside>
      )}
    </div>
  );
};

export default QAPage;
