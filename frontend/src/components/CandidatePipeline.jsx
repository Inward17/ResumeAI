import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import {
  ArrowLeft, Upload, Clock, Users, MapPin, ChevronRight, FileText, Calendar, AlertTriangle, CheckCircle, Search, Briefcase,
} from 'lucide-react';
import { useToast } from '../hooks/use-toast';
import CandidateModal from './CandidateModal';
import {
  getJob, getJobCandidates, getJobTasks, uploadResumes, updateCandidateStatus,
} from '../services/jobService';
import { CANDIDATE_STATUSES, INTERVIEW_STATUSES } from '../lib/statuses';
import { loadPreferences } from '../lib/preferences';
import { cn } from '../lib/utils';
import {
  Card, CardHeader, PageContainer, StatusPill, ScoreBadge, ScoreRing, Initials, EmptyState, JobStatusPill, PrimaryButton,
} from './common';

const ACCEPTED_TYPES = '.pdf,.docx,.doc,.txt';

const CandidateRow = ({ candidate, prefs, onOpen, onMoveToInterview }) => {
  const needsReview = candidate.verificationScore < prefs.verificationThreshold;
  const inInterviewTrack = INTERVIEW_STATUSES.includes(candidate.status);
  return (
    <li className="group flex flex-col gap-3 border-b border-slate-100 px-5 py-4 transition-colors last:border-0 hover:bg-brand-light/50 md:flex-row md:items-center md:justify-between">
      <button type="button" onClick={() => onOpen(candidate)} className="flex min-w-0 flex-1 items-center gap-3 text-left">
        <Initials name={candidate.name} />
        <div className="min-w-0">
          <p className="truncate text-sm font-semibold text-slate-900">{candidate.name}</p>
          <p className="truncate text-xs text-slate-500">{candidate.email || 'No email on resume'}</p>
        </div>
      </button>
      <div className="flex shrink-0 flex-wrap items-center gap-2 pl-12 md:justify-end md:pl-0">
        <ScoreBadge value={candidate.jdMatchScore} strong={prefs.matchThreshold} />
        <StatusPill status={candidate.status} />
        {needsReview ? (
          <span title={`Verification ${candidate.verificationScore}% — below your ${prefs.verificationThreshold}% threshold`}>
            <AlertTriangle className="h-4 w-4 text-amber-600" aria-label="Verification needs review" />
          </span>
        ) : (
          <span title={`Verification ${candidate.verificationScore}%`}>
            <CheckCircle className="h-4 w-4 text-emerald-600" aria-label="Verification above threshold" />
          </span>
        )}
        {!inInterviewTrack && (
          <button
            type="button"
            onClick={() => onMoveToInterview(candidate.id)}
            className="flex items-center gap-1 rounded-lg bg-emerald-50 px-2.5 py-1 text-[11px] font-bold text-emerald-800 ring-1 ring-inset ring-emerald-200 transition-opacity md:opacity-0 md:group-hover:opacity-100 md:focus:opacity-100"
          >
            <Calendar className="h-3 w-3" aria-hidden="true" /> Move to interview
          </button>
        )}
        <ChevronRight className="hidden h-4 w-4 text-slate-400 md:block" aria-hidden="true" />
      </div>
    </li>
  );
};

const CandidatePipeline = () => {
  const { jobId } = useParams();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const { toast } = useToast();
  const prefs = useMemo(loadPreferences, []);

  const [job, setJob] = useState(null);
  const [jobError, setJobError] = useState(null);
  const [candidates, setCandidates] = useState([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(null); // {processed, total} files sent
  const [taskCounts, setTaskCounts] = useState(null); // backend processing status
  const [batch, setBatch] = useState(null); // {base, total} — progress of the latest upload
  const [pollKey, setPollKey] = useState(0);
  const [dragOver, setDragOver] = useState(false);
  const [mobileTab, setMobileTab] = useState('pipeline');
  const [query, setQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('All');
  const lastFinished = useRef(null);
  const fileInputRef = useRef(null);

  const selectedId = searchParams.get('candidate');
  const selectedCandidate = candidates.find((c) => c.id === selectedId) || null;

  useEffect(() => {
    setJob(null);
    setJobError(null);
    getJob(jobId).then(setJob).catch((err) => setJobError(err.message));
  }, [jobId]);

  const fetchCandidates = useCallback(async (silent = false) => {
    try {
      if (!silent) setLoading(true);
      setCandidates(await getJobCandidates(jobId));
    } catch (err) {
      if (!silent) toast({ title: 'Could not load candidates', description: err.message, variant: 'destructive' });
    } finally {
      if (!silent) setLoading(false);
    }
  }, [jobId, toast]);

  useEffect(() => { fetchCandidates(); }, [fetchCandidates]);

  // Poll resume processing status while anything is queued/processing and
  // refresh the list as candidates finish (they appear once verified).
  useEffect(() => {
    let cancelled = false;
    let timer = null;
    const tick = async () => {
      try {
        const { counts } = await getJobTasks(jobId);
        if (cancelled) return;
        setTaskCounts(counts);
        const finished = counts.done + counts.failed;
        if (lastFinished.current !== null && finished !== lastFinished.current) fetchCandidates(true);
        lastFinished.current = finished;
        if (counts.queued + counts.processing > 0) timer = setTimeout(tick, 3000);
      } catch {
        if (!cancelled) timer = setTimeout(tick, 10000);
      }
    };
    tick();
    return () => { cancelled = true; clearTimeout(timer); };
  }, [jobId, pollKey, fetchCandidates]);

  const uploadFiles = async (fileList) => {
    const files = Array.from(fileList || []);
    if (files.length === 0) return;
    setUploading(true);
    setUploadProgress({ processed: 0, total: files.length });
    setBatch({ base: taskCounts ? taskCounts.done + taskCounts.failed : 0, total: files.length });
    try {
      await uploadResumes(jobId, files, (processed, total) => setUploadProgress({ processed, total }));
      toast({ title: 'Resumes queued', description: `${files.length} resume(s) uploaded. Screening runs in the background.` });
    } catch (err) {
      toast({ title: 'Upload failed', description: err.message, variant: 'destructive' });
    } finally {
      setUploading(false);
      setUploadProgress(null);
      if (fileInputRef.current) fileInputRef.current.value = '';
      setPollKey((k) => k + 1);
    }
  };

  const handleStatusUpdate = async (candidateId, status) => {
    try {
      await updateCandidateStatus(jobId, candidateId, status);
      setCandidates((prev) => prev.map((c) => (c.id === candidateId ? { ...c, status } : c)));
      toast({ title: `Moved to ${status}` });
    } catch (err) {
      toast({ title: 'Could not update status', description: err.message, variant: 'destructive' });
    }
  };

  const openCandidate = (c) => setSearchParams({ candidate: c.id });
  const closeCandidate = () => setSearchParams({}, { replace: true });

  const activeTasks = taskCounts ? taskCounts.queued + taskCounts.processing : 0;
  const processingPct = (() => {
    if (!taskCounts || activeTasks === 0) return 100;
    if (batch) {
      const finished = taskCounts.done + taskCounts.failed - batch.base;
      return Math.max(0, Math.min(100, Math.round((finished / batch.total) * 100)));
    }
    return Math.round(((taskCounts.done + taskCounts.failed) / (taskCounts.total || 1)) * 100);
  })();

  const ranked = [...candidates].sort((a, b) => b.jdMatchScore - a.jdMatchScore);
  const visible = ranked.filter((c) => {
    const q = query.trim().toLowerCase();
    return (statusFilter === 'All' || c.status === statusFilter)
      && (!q || c.name.toLowerCase().includes(q) || c.email.toLowerCase().includes(q));
  });
  const avg = (key) => (candidates.length ? Math.round(candidates.reduce((s, c) => s + (c[key] || 0), 0) / candidates.length) : null);
  const topMatch = candidates.length ? ranked[0].jdMatchScore : null;
  const strongMatches = candidates.filter((c) => c.jdMatchScore >= prefs.matchThreshold).length;

  if (jobError) {
    return (
      <PageContainer>
        <Card>
          <EmptyState icon={Briefcase} title="Job not found" description="It may have been deleted, or it belongs to another account."
            action={<PrimaryButton onClick={() => navigate('/jobs')}>Back to job postings</PrimaryButton>} />
        </Card>
      </PageContainer>
    );
  }

  return (
    <PageContainer>
      <Link to="/jobs" className="mb-4 inline-flex items-center gap-2 text-sm font-semibold text-slate-600 hover:text-slate-900">
        <ArrowLeft className="h-4 w-4" aria-hidden="true" /> Back to postings
      </Link>

      <div className="mb-6">
        {job ? (
          <>
            <div className="flex flex-wrap items-center gap-3">
              <h1 className="text-2xl font-extrabold tracking-tight text-slate-900 md:text-[1.75rem]">{job.title}</h1>
              <JobStatusPill status={job.status} />
            </div>
            <div className="mt-1.5 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-slate-600">
              {job.department && <span className="flex items-center gap-1"><Briefcase className="h-3.5 w-3.5" aria-hidden="true" />{job.department}</span>}
              {job.location && <span className="flex items-center gap-1"><MapPin className="h-3.5 w-3.5" aria-hidden="true" />{job.location}</span>}
              {job.employmentType && <span className="flex items-center gap-1"><Clock className="h-3.5 w-3.5" aria-hidden="true" />{job.employmentType}</span>}
              <span className="flex items-center gap-1"><Users className="h-3.5 w-3.5" aria-hidden="true" />{candidates.length} candidates</span>
            </div>
          </>
        ) : (
          <div className="space-y-2"><div className="h-8 w-72 animate-pulse rounded-lg bg-slate-200" /><div className="h-4 w-48 animate-pulse rounded bg-slate-200" /></div>
        )}
      </div>

      {/* Mobile tab switcher */}
      <div className="mb-5 flex rounded-xl bg-slate-200/60 p-1 lg:hidden" role="tablist">
        {[['pipeline', 'Pipeline'], ['analysis', 'Analysis']].map(([id, label]) => (
          <button key={id} type="button" role="tab" aria-selected={mobileTab === id} onClick={() => setMobileTab(id)}
            className={cn('flex-1 rounded-lg py-2 text-sm font-bold transition-all', mobileTab === id ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-600')}>
            {label}
          </button>
        ))}
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1fr_320px]">
        <div className={cn('flex-col gap-5', mobileTab === 'pipeline' ? 'flex' : 'hidden lg:flex')}>
          {/* Upload zone */}
          <div
            className={cn(
              'flex flex-col items-center gap-3 rounded-2xl border-2 border-dashed p-6 text-center transition-colors',
              dragOver ? 'border-brand-accent bg-brand-light' : 'border-brand-soft bg-white',
            )}
            onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
            onDragLeave={() => setDragOver(false)}
            onDrop={(e) => { e.preventDefault(); setDragOver(false); uploadFiles(e.dataTransfer.files); }}
          >
            <input ref={fileInputRef} id="resume-upload" type="file" multiple accept={ACCEPTED_TYPES} className="sr-only"
              onChange={(e) => uploadFiles(e.target.files)} />
            <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-brand-light">
              <Upload className="h-6 w-6 text-brand-accent" aria-hidden="true" />
            </div>
            <div>
              <p className="font-bold text-slate-900">Upload resumes</p>
              <p className="mt-0.5 text-sm text-slate-600">Drag and drop PDF, DOCX or TXT files, or choose them. Large batches are fine.</p>
            </div>
            <PrimaryButton onClick={() => fileInputRef.current?.click()} disabled={uploading}>
              {uploading ? 'Uploading…' : 'Choose files'}
            </PrimaryButton>

            {uploading && uploadProgress && (
              <div className="w-full" aria-live="polite">
                <div className="mb-1 flex justify-between text-xs text-slate-600">
                  <span>Uploading… {uploadProgress.processed}/{uploadProgress.total}</span>
                  <span>{Math.round((uploadProgress.processed / uploadProgress.total) * 100)}%</span>
                </div>
                <div className="h-1.5 overflow-hidden rounded-full bg-slate-200">
                  <div className="h-full rounded-full bg-brand-accent transition-all" style={{ width: `${(uploadProgress.processed / uploadProgress.total) * 100}%` }} />
                </div>
              </div>
            )}
            {!uploading && activeTasks > 0 && (
              <div className="w-full" aria-live="polite">
                <div className="mb-1 flex justify-between text-xs text-slate-600">
                  <span>AI screening… {taskCounts.processing} in progress · {taskCounts.queued} queued</span>
                  <span>{processingPct}%</span>
                </div>
                <div className="h-1.5 overflow-hidden rounded-full bg-slate-200">
                  <div className="h-full rounded-full bg-brand-accent transition-all" style={{ width: `${processingPct}%` }} />
                </div>
              </div>
            )}
            {taskCounts?.failed > 0 && (
              <p className="text-xs text-red-700">{taskCounts.failed} resume(s) could not be processed. Re-upload them to retry.</p>
            )}
          </div>

          {/* Candidate list */}
          <Card className="overflow-hidden">
            <CardHeader title="Candidates" subtitle="Ranked by role match" action={<span className="text-sm text-slate-500">{visible.length} of {candidates.length}</span>} />
            {candidates.length > 0 && (
              <div className="flex flex-col gap-3 border-b border-slate-100 px-5 py-3 md:flex-row md:items-center">
                <div className="relative md:w-64">
                  <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500" aria-hidden="true" />
                  <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search name or email" aria-label="Search candidates"
                    className="w-full rounded-xl border border-slate-200 bg-white py-2 pl-9 pr-3 text-sm outline-none focus:border-brand-accent focus:ring-2 focus:ring-brand-soft" />
                </div>
                <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} aria-label="Filter by status"
                  className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 outline-none focus:border-brand-accent focus:ring-2 focus:ring-brand-soft">
                  <option value="All">All statuses</option>
                  {CANDIDATE_STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
                </select>
              </div>
            )}
            {loading ? (
              <div className="space-y-3 p-5">{[1, 2, 3].map((i) => <div key={i} className="h-12 animate-pulse rounded-xl bg-slate-100" />)}</div>
            ) : candidates.length === 0 ? (
              <EmptyState icon={FileText} title="No candidates yet"
                description={activeTasks > 0 ? 'Resumes are being screened — candidates appear here as each one finishes.' : 'Upload resumes above to get started.'} />
            ) : visible.length === 0 ? (
              <EmptyState icon={Search} title="No matching candidates" description="Try a different search or status." />
            ) : (
              <ul>
                {visible.map((c) => (
                  <CandidateRow key={c.id} candidate={c} prefs={prefs} onOpen={openCandidate}
                    onMoveToInterview={(id) => handleStatusUpdate(id, 'Interview')} />
                ))}
              </ul>
            )}
          </Card>
        </div>

        {/* Analysis column */}
        <div className={cn('flex-col gap-5', mobileTab === 'analysis' ? 'flex' : 'hidden lg:flex')}>
          <div className="rounded-2xl bg-brand-gradient p-5 text-white">
            <p className="mb-3 text-xs font-bold uppercase tracking-widest text-indigo-200">Screening status</p>
            <div className="mb-4 flex items-center gap-5">
              <div>
                <p className="text-xs font-semibold text-indigo-200">Top match</p>
                <p className="font-display text-3xl font-extrabold">{topMatch == null ? '—' : `${topMatch}%`}</p>
              </div>
              <div className="h-10 w-px bg-white/20" />
              <div>
                <p className="text-xs font-semibold text-indigo-200">In queue</p>
                <p className="font-display text-3xl font-extrabold">{activeTasks}</p>
              </div>
            </div>
            {activeTasks > 0 ? (
              <div>
                <div className="mb-1.5 flex justify-between text-xs text-indigo-100"><span>AI processing</span><span>{processingPct}%</span></div>
                <div className="h-1.5 overflow-hidden rounded-full bg-white/20">
                  <div className="h-full rounded-full bg-brand-cyan transition-all" style={{ width: `${processingPct}%` }} />
                </div>
              </div>
            ) : (
              <p className="text-sm leading-relaxed text-indigo-100">
                {candidates.length > 0
                  ? `${strongMatches} of ${candidates.length} candidates have a role match of ${prefs.matchThreshold}% or more.`
                  : 'Upload resumes to begin screening.'}
              </p>
            )}
          </div>

          {candidates.length > 0 && (
            <Card className="p-5">
              <p className="mb-4 font-semibold text-slate-900">Score overview</p>
              <div className="grid grid-cols-3 gap-2">
                <ScoreRing value={topMatch} label="Top match" />
                <ScoreRing value={avg('jdMatchScore')} label="Avg match" />
                <ScoreRing value={avg('verificationScore')} label="Avg verified" />
              </div>
            </Card>
          )}

          <Card className="p-5">
            <p className="mb-2 font-semibold text-slate-900">About this role</p>
            <p className="line-clamp-6 text-sm leading-relaxed text-slate-600">{job?.description || 'No description provided.'}</p>
            {job?.requirements?.length > 0 && (
              <div className="mt-3 flex flex-wrap gap-1.5">
                {job.requirements.map((skill) => (
                  <span key={skill} className="rounded-full bg-brand-light px-2 py-0.5 text-[11px] font-semibold text-brand">{skill}</span>
                ))}
              </div>
            )}
          </Card>
        </div>
      </div>

      <CandidateModal
        open={!!selectedCandidate}
        candidate={selectedCandidate}
        job={job}
        prefs={prefs}
        onClose={closeCandidate}
        onStatusUpdate={handleStatusUpdate}
        onTakeInterview={(c) => navigate(`/jobs/${jobId}/candidates/${c.id}/interview`)}
      />
    </PageContainer>
  );
};

export default CandidatePipeline;
