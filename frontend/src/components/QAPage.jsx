import React, { useState, useEffect, useCallback } from 'react';
import {
  ArrowLeft, Mail, Phone, Send,
  Zap, Clock, User, Monitor, XCircle, CheckCircle, Loader2, Award, Bot
} from 'lucide-react';
import { C } from '../theme';
import { getInterviewQuestions, submitEvaluation } from '../services/jobService';
import FactCheckerBot from './FactCheckerBot';

/* ── Clickable Tag pill ── */
const TopicTag = ({ label, selected, onClick }) => (
  <button
    type="button"
    onClick={onClick}
    className="inline-block text-xs font-semibold px-3 py-1.5 rounded-full transition-all duration-200 cursor-pointer"
    style={
      selected
        ? { background: C.accent, color: '#ffffff', border: `1px solid ${C.accent}`, transform: 'scale(1.05)' }
        : { background: '#eef2ff', color: '#4338ca', border: '1px solid #e0e7ff' }
    }
  >
    {label}
  </button>
);

/* ── Question Card with per-question scoring ── */
const QuestionCard = ({ index, question, tags, selectedTags, onToggleTag }) => {
  const selected = selectedTags.length;
  const total = tags.length;

  return (
    <div
      className="rounded-2xl p-6"
      style={{ background: '#f8fafc', border: '1px solid #e2e8f0' }}
    >
      <div className="flex items-center justify-between mb-2">
        <p
          className="text-[11px] font-bold uppercase tracking-widest"
          style={{ color: C.accent }}
        >
          Question {String(index).padStart(2, '0')}
        </p>
        <span
          className="text-xs font-bold px-2.5 py-1 rounded-lg"
          style={{
            background: selected === total && total > 0 ? '#d1fae5' : selected > 0 ? '#eef2ff' : '#f1f5f9',
            color: selected === total && total > 0 ? '#065f46' : selected > 0 ? C.accent : '#94a3b8',
          }}
        >
          {selected}/{total}
        </span>
      </div>
      <p className="text-base font-bold text-slate-900 leading-relaxed mb-4">
        "{question}"
      </p>
      <div className="flex flex-wrap gap-2">
        {tags.map((tag, i) => (
          <TopicTag
            key={i}
            label={tag}
            selected={selectedTags.includes(tag)}
            onClick={() => onToggleTag(tag)}
          />
        ))}
      </div>
    </div>
  );
};

/* ── Loading Skeleton ── */
const QuestionSkeleton = () => (
  <div className="space-y-5">
    {[1, 2, 3].map((i) => (
      <div
        key={i}
        className="rounded-2xl p-6 animate-pulse"
        style={{ background: '#f8fafc', border: '1px solid #e2e8f0' }}
      >
        <div className="h-3 w-24 bg-slate-200 rounded mb-3" />
        <div className="h-5 w-full bg-slate-200 rounded mb-2" />
        <div className="h-5 w-3/4 bg-slate-200 rounded mb-4" />
        <div className="flex gap-2">
          <div className="h-7 w-28 bg-slate-200 rounded-full" />
          <div className="h-7 w-32 bg-slate-200 rounded-full" />
          <div className="h-7 w-24 bg-slate-200 rounded-full" />
        </div>
      </div>
    ))}
  </div>
);

/* ── Main Component ── */
const QAPage = ({ candidate, job, onBack }) => {
  const [questions, setQuestions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [isFactCheckerOpen, setIsFactCheckerOpen] = useState(false);

  // selectedKeywords: { [questionId]: ["tag1", "tag2"] }
  const [selectedKeywords, setSelectedKeywords] = useState({});

  useEffect(() => {
    const fetchQuestions = async () => {
      if (!job?.id || !candidate?.id) {
        setLoading(false);
        setError('Missing job or candidate data');
        return;
      }
      try {
        setLoading(true);
        setError(null);
        const data = await getInterviewQuestions(job.id, candidate.id);
        setQuestions(data.questions || []);
      } catch (err) {
        console.error('Failed to fetch interview questions:', err);
        setError('Failed to generate questions. Please try again.');
      } finally {
        setLoading(false);
      }
    };
    fetchQuestions();
  }, [job?.id, candidate?.id]);

  // Toggle a keyword for a specific question
  const handleToggleTag = useCallback((questionId, tag) => {
    setSelectedKeywords(prev => {
      const current = prev[questionId] || [];
      if (current.includes(tag)) {
        return { ...prev, [questionId]: current.filter(t => t !== tag) };
      } else {
        return { ...prev, [questionId]: [...current, tag] };
      }
    });
  }, []);

  // Computed scores
  const totalPossible = questions.reduce((sum, q) => sum + (q.tags?.length || 0), 0);
  const totalSelected = Object.values(selectedKeywords).reduce((sum, tags) => sum + tags.length, 0);
  const aggregatePercent = totalPossible > 0 ? Math.round((totalSelected / totalPossible) * 100) : 0;

  // Submit evaluation to backend
  const handleSubmit = async () => {
    if (!job?.id || !candidate?.id) return;
    setSubmitting(true);
    try {
      const evaluationData = {
        candidate_name: candidate.name || 'Unknown',
        job_title: job.title || 'N/A',
        questions: questions.map(q => ({
          question_id: q.id,
          question: q.question,
          total_tags: q.tags?.length || 0,
          selected_tags: selectedKeywords[q.id] || [],
          score: q.tags?.length > 0
            ? (selectedKeywords[q.id]?.length || 0) / q.tags.length
            : 0,
        })),
        total_score: aggregatePercent,
        total_selected: totalSelected,
        total_possible: totalPossible,
      };
      await submitEvaluation(job.id, candidate.id, evaluationData);
      onBack();
    } catch (err) {
      console.error('Failed to submit evaluation:', err);
      setError('Failed to submit evaluation. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  if (!candidate) return null;

  const name = candidate.name || 'Unknown Candidate';
  const title = candidate.currentTitle || 'Senior Developer';
  const email = candidate.email || 'candidate@example.com';
  const phone = candidate.phone || '+91 98200 45XXX';
  const matchScore = candidate.jdMatchScore ?? candidate.matchScore ?? 94;
  const cultureFit = matchScore;
  const aiSummary =
    candidate.persona ||
    candidate.summary ||
    candidate.aiSummary ||
    `"Demonstrates high architectural maturity. Strong emphasis on scalability and performance optimization in microservices."`;

  return (
    <div className="flex h-full w-full overflow-hidden" style={{ background: C.pageGray }}>
      {/* ── Main Scrollable Content ── */}
      <div className="flex-1 overflow-y-auto min-h-full pb-28 relative">
        <div className="max-w-7xl mx-auto px-8 pt-6">
        {/* Back link */}
        <button
          onClick={onBack}
          className="flex items-center gap-2 text-sm font-semibold text-slate-600 hover:text-slate-900 transition-colors mb-6"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to Pipeline
        </button>

        {/* ── Candidate Header ── */}
        <div className="flex items-start justify-between mb-8">
          <div className="flex items-center gap-5">
            {/* Avatar */}
            <div
              className="h-20 w-20 rounded-2xl flex items-center justify-center text-3xl font-black text-white shrink-0 shadow-lg"
              style={{
                background: `linear-gradient(135deg, ${C.primary}, ${C.accent})`,
              }}
            >
              {name.charAt(0).toUpperCase()}
            </div>
            <div>
              <p
                className="text-[10px] font-bold uppercase tracking-widest mb-1"
                style={{ color: C.accent }}
              >
                Candidate Dossier
              </p>
              <h1 className="text-3xl font-black text-slate-900 flex items-center gap-3">
                {name}
                {!isFactCheckerOpen && (
                  <button 
                    onClick={() => setIsFactCheckerOpen(true)}
                    className="w-8 h-8 rounded-full flex items-center justify-center hover:scale-105 transition-transform"
                    style={{ background: '#e0e7ff', color: C.accent }}
                    title="Open AI Fact Checker"
                  >
                    <Bot className="h-4 w-4" />
                  </button>
                )}
              </h1>
              <p className="text-sm text-slate-500 font-medium">{title}</p>
              <div className="flex items-center gap-4 mt-2 text-xs text-slate-400">
                <span className="flex items-center gap-1.5">
                  <Mail className="h-3.5 w-3.5" />
                  {email}
                </span>
                <span className="flex items-center gap-1.5">
                  <Phone className="h-3.5 w-3.5" />
                  {phone}
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* ── Two Column Layout ── */}
        <div className="grid grid-cols-[380px_1fr] gap-6">
          {/* LEFT COLUMN */}
          <div className="space-y-6">
            {/* AI Insight Summary */}
            <div
              className="rounded-2xl p-6"
              style={{
                background: `linear-gradient(135deg, ${C.primary} 0%, #312e81 100%)`,
              }}
            >
              <div className="flex items-center gap-2 mb-4">
                <div
                  className="h-7 w-7 rounded-lg flex items-center justify-center"
                  style={{ background: 'rgba(255,255,255,0.15)' }}
                >
                  <Zap className="h-4 w-4" style={{ color: C.cyan }} />
                </div>
                <p className="text-xs font-bold uppercase tracking-widest text-indigo-200">
                  AI Insight Summary
                </p>
              </div>
              <p className="text-sm leading-relaxed text-indigo-100 mb-6">
                {aiSummary}
              </p>
              <div className="flex items-center gap-8">
                <div>
                  <p className="text-3xl font-black text-white">{cultureFit}%</p>
                  <p className="text-[10px] font-bold uppercase tracking-widest text-indigo-300 mt-1">
                    Role Match
                  </p>
                </div>
              </div>
            </div>

            {/* Interview Metadata */}
            <div
              className="rounded-2xl p-6 bg-white"
              style={{ border: '1px solid #e2e8f0' }}
            >
              <p className="text-[10px] font-bold uppercase tracking-widest text-slate-400 mb-4">
                Interview Metadata
              </p>
              <div className="space-y-4">
                {[
                  { icon: Monitor, label: 'Interview Type', value: 'Technical Round' },
                  { icon: User, label: 'Job Role', value: job?.title || 'N/A' },
                  { icon: Clock, label: 'Questions', value: loading ? '...' : `${questions.length} Generated` },
                ].map(({ icon: Icon, label, value }) => (
                  <div key={label} className="flex items-center justify-between">
                    <span className="flex items-center gap-2 text-sm text-slate-500">
                      <Icon className="h-4 w-4 text-slate-400" />
                      {label}
                    </span>
                    <span className="text-sm font-bold text-slate-900">{value}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Live Interview Score Card */}
            {!loading && questions.length > 0 && (
              <div
                className="rounded-2xl p-6 bg-white"
                style={{ border: '1px solid #e2e8f0' }}
              >
                <div className="flex items-center gap-2 mb-4">
                  <Award className="h-4 w-4" style={{ color: C.accent }} />
                  <p className="text-[10px] font-bold uppercase tracking-widest text-slate-400">
                    Interview Score
                  </p>
                </div>
                {/* Score ring */}
                <div className="flex items-center justify-center mb-4">
                  <div className="relative" style={{ width: 100, height: 100 }}>
                    <svg viewBox="0 0 100 100" width={100} height={100} className="-rotate-90">
                      <circle cx="50" cy="50" r="40" fill="none" stroke="#e0e7ff" strokeWidth="8" />
                      <circle
                        cx="50" cy="50" r="40" fill="none"
                        stroke={aggregatePercent >= 70 ? '#059669' : aggregatePercent >= 40 ? C.accent : '#f59e0b'}
                        strokeWidth="8"
                        strokeDasharray={`${(aggregatePercent / 100) * 251.2} 251.2`}
                        strokeLinecap="round"
                      />
                    </svg>
                    <div className="absolute inset-0 flex items-center justify-center">
                      <span className="text-xl font-black" style={{ color: C.primary }}>{aggregatePercent}%</span>
                    </div>
                  </div>
                </div>
                <p className="text-center text-xs text-slate-500">
                  <span className="font-bold text-slate-900">{totalSelected}</span> of{' '}
                  <span className="font-bold text-slate-900">{totalPossible}</span> keywords covered
                </p>
                {/* Per-question breakdown */}
                <div className="mt-4 space-y-2">
                  {questions.map(q => {
                    const sel = (selectedKeywords[q.id] || []).length;
                    const tot = q.tags?.length || 0;
                    return (
                      <div key={q.id} className="flex items-center justify-between text-xs">
                        <span className="text-slate-500">Q{String(q.id).padStart(2, '0')}</span>
                        <div className="flex-1 mx-3 h-1.5 rounded-full bg-slate-100 overflow-hidden">
                          <div
                            className="h-full rounded-full transition-all duration-300"
                            style={{
                              width: tot > 0 ? `${(sel / tot) * 100}%` : '0%',
                              background: sel === tot && tot > 0
                                ? '#059669'
                                : `linear-gradient(90deg, ${C.accent}, ${C.cyan})`,
                            }}
                          />
                        </div>
                        <span className="font-bold text-slate-700">{sel}/{tot}</span>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </div>

          {/* RIGHT COLUMN — Q&A Transcript */}
          <div>
            <div className="flex items-center gap-2 mb-5">
              <Monitor className="h-5 w-5" style={{ color: C.primary }} />
              <h2 className="text-lg font-black text-slate-900">
                Response Transcript Analysis
              </h2>
            </div>

            {/* Loading state */}
            {loading && (
              <div>
                <div className="flex items-center gap-3 mb-5 p-4 rounded-2xl" style={{ background: '#eef2ff', border: '1px solid #e0e7ff' }}>
                  <Loader2 className="h-5 w-5 animate-spin" style={{ color: C.accent }} />
                  <div>
                    <p className="text-sm font-bold text-slate-900">Generating AI-tailored questions…</p>
                    <p className="text-xs text-slate-500">Analyzing JD and candidate profile via Groq</p>
                  </div>
                </div>
                <QuestionSkeleton />
              </div>
            )}

            {/* Error state */}
            {!loading && error && (
              <div className="p-6 rounded-2xl text-center" style={{ background: '#fef2f2', border: '1px solid #fecaca' }}>
                <p className="text-sm font-bold text-red-700 mb-1">{error}</p>
                <p className="text-xs text-red-500">The AI service may be temporarily unavailable.</p>
              </div>
            )}

            {/* Questions */}
            {!loading && !error && (
              <div className="space-y-5">
                {questions.map((q) => (
                  <QuestionCard
                    key={q.id}
                    index={q.id}
                    question={q.question}
                    tags={q.tags}
                    selectedTags={selectedKeywords[q.id] || []}
                    onToggleTag={(tag) => handleToggleTag(q.id, tag)}
                  />
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
      </div>

      {/* ── Sticky Bottom Action Bar ── */}
      <div
        className="fixed bottom-0 left-0 md:left-56 z-40 transition-all duration-300"
        style={{
          right: isFactCheckerOpen ? '400px' : '0',
          background: 'white',
          borderTop: '1px solid #e2e8f0',
          boxShadow: '0 -4px 20px rgba(0,0,0,0.06)',
        }}
      >
        <div className="max-w-7xl mx-auto px-8 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div
              className="h-9 w-9 rounded-lg flex items-center justify-center"
              style={{ background: '#eef2ff' }}
            >
              <CheckCircle className="h-5 w-5" style={{ color: C.accent }} />
            </div>
            <div>
              <p className="text-sm font-bold text-slate-900">
                Interview Score: <span style={{ color: C.accent }}>{aggregatePercent}%</span> ({totalSelected}/{totalPossible} keywords)
              </p>
              <p className="text-xs text-slate-400">
                Click on keywords the candidate covered, then submit your evaluation.
              </p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={onBack}
              className="flex items-center gap-2 px-6 py-2.5 rounded-xl text-sm font-bold border-2 border-slate-200 text-slate-600 hover:bg-slate-50 transition-colors"
            >
              <XCircle className="h-4 w-4" />
              Reject Candidate
            </button>
            <button
              onClick={handleSubmit}
              disabled={submitting || loading}
              className="flex items-center gap-2 px-6 py-2.5 rounded-xl text-sm font-bold text-white transition-opacity hover:opacity-90 disabled:opacity-50"
              style={{ background: C.primary }}
            >
              {submitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
              {submitting ? 'Submitting…' : 'Submit Evaluation'}
            </button>
          </div>
        </div>
      </div>
      
      {/* ── Docked AI Assistant Sidebar ── */}
      {isFactCheckerOpen && (
        <div className="w-[400px] flex flex-col bg-white border-l border-slate-200 shrink-0 h-full relative z-40">
          <FactCheckerBot 
            candidateId={candidate.id}
            candidateName={name} 
            onClose={() => setIsFactCheckerOpen(false)} 
          />
        </div>
      )}
    </div>
  );
};

export default QAPage;
