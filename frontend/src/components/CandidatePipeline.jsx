import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';
import {
  Upload, Clock, Users, MapPin, FileText, AlertTriangle, Search, Briefcase, ArrowDown, ArrowUp, Loader2, ChevronRight,
} from 'lucide-react';
import { useToast } from '../hooks/use-toast';
import CandidateModal from './CandidateModal';
import {
  getJob, getJobCandidates, getJobTasks, uploadResumes, updateCandidateStatus,
} from '../services/jobService';
import { CANDIDATE_STATUSES } from '../lib/statuses';
import { loadPreferences } from '../lib/preferences';
import { cn } from '../lib/utils';
import {
  Card, CardHeader, PageContainer, PageHeader, ScoreBar, ScoreRing, Initials, EmptyState, JobStatusPill, Button,
  Segmented, SearchInput, Tag, Skeleton, StatusSelect,
} from './common';

const ACCEPTED_TYPES = '.pdf,.docx,.doc,.txt';

// Failed uploads stay in the task log, so remember how many the user already dismissed
const dismissedKey = (jobId) => `resumeai:dismissed-failures:${jobId}`;
const readDismissed = (jobId) => {
  try { return Number(localStorage.getItem(dismissedKey(jobId))) || 0; } catch { return 0; }
};

const SORTS = {
  match: (a, b) => b.jdMatchScore - a.jdMatchScore,
  credibility: (a, b) => (b.verificationScore ?? -1) - (a.verificationScore ?? -1),
  name: (a, b) => a.name.localeCompare(b.name),
};

const SortHeader = ({ id, label, sort, setSort, className }) => {
  const active = sort === id;
  const Arrow = id === 'name' ? ArrowUp : ArrowDown;
  return (
    <th scope="col" aria-sort={active ? (id === 'name' ? 'ascending' : 'descending') : 'none'} className={cn('px-3 py-2.5 font-medium', className)}>
      <button type="button" onClick={() => setSort(id)}
        className={cn('inline-flex items-center gap-1 rounded uppercase tracking-[0.08em] transition-colors hover:text-ink', active && 'text-ink')}>
        {label}
        <Arrow className={cn('h-3.5 w-3.5', active ? 'opacity-100' : 'opacity-0')} aria-hidden="true" />
      </button>
    </th>
  );
};

const CredibilityCell = ({ candidate, prefs }) => {
  const low = candidate.verificationScore != null && candidate.verificationScore < prefs.verificationThreshold;
  return (
    <div className="flex items-center gap-1.5">
      <ScoreBar value={candidate.verificationScore} strong={prefs.verificationThreshold} label="Credibility" className="flex-1" />
      {low && (
        <span title={`Below your ${prefs.verificationThreshold}% review threshold`}>
          <AlertTriangle className="h-4 w-4 shrink-0 text-warning" aria-label="Needs manual review" />
        </span>
      )}
    </div>
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
  const [query, setQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('All');
  const [sort, setSort] = useState('match');
  const [showFullDescription, setShowFullDescription] = useState(false);
  const [dismissedFailures, setDismissedFailures] = useState(() => readDismissed(jobId));
  const lastFinished = useRef(null);
  const fileInputRef = useRef(null);
  const dragDepth = useRef(0);

  const selectedId = searchParams.get('candidate');
  const selectedCandidate = candidates.find((c) => c.id === selectedId) || null;

  useEffect(() => {
    setDismissedFailures(readDismissed(jobId));
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
    if (files.length === 0 || uploading) return;
    setUploading(true);
    setUploadProgress({ processed: 0, total: files.length });
    setBatch({ base: taskCounts ? taskCounts.done + taskCounts.failed : 0, total: files.length });
    try {
      await uploadResumes(jobId, files, (processed, total) => setUploadProgress({ processed, total }));
      toast({ title: `${files.length} resume${files.length === 1 ? '' : 's'} uploaded`, description: 'Screening runs in the background — candidates appear as each one finishes.' });
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
    const previous = candidates.find((c) => c.id === candidateId)?.status;
    setCandidates((prev) => prev.map((c) => (c.id === candidateId ? { ...c, status } : c)));
    try {
      await updateCandidateStatus(jobId, candidateId, status);
      toast({ title: `Moved to ${status}` });
    } catch (err) {
      setCandidates((prev) => prev.map((c) => (c.id === candidateId ? { ...c, status: previous } : c)));
      toast({ title: 'Could not update status', description: err.message, variant: 'destructive' });
    }
  };

  const openCandidate = (c) => setSearchParams({ candidate: c.id });
  const closeCandidate = () => setSearchParams({}, { replace: true });

  // Page-wide drag and drop (dragenter/leave fire for every child, so count depth)
  const dragProps = {
    onDragEnter: (e) => { if (e.dataTransfer.types.includes('Files')) { dragDepth.current += 1; setDragOver(true); } },
    onDragOver: (e) => e.preventDefault(),
    onDragLeave: () => { dragDepth.current = Math.max(0, dragDepth.current - 1); if (!dragDepth.current) setDragOver(false); },
    onDrop: (e) => { e.preventDefault(); dragDepth.current = 0; setDragOver(false); uploadFiles(e.dataTransfer.files); },
  };

  const activeTasks = taskCounts ? taskCounts.queued + taskCounts.processing : 0;
  const newFailures = taskCounts ? Math.max(0, taskCounts.failed - dismissedFailures) : 0;
  const dismissFailures = () => {
    setDismissedFailures(taskCounts.failed);
    try { localStorage.setItem(dismissedKey(jobId), String(taskCounts.failed)); } catch { /* storage blocked: hides until reload */ }
  };
  const processingPct = (() => {
    if (!taskCounts || activeTasks === 0) return 100;
    if (batch) {
      const finished = taskCounts.done + taskCounts.failed - batch.base;
      return Math.max(0, Math.min(100, Math.round((finished / batch.total) * 100)));
    }
    return Math.round(((taskCounts.done + taskCounts.failed) / (taskCounts.total || 1)) * 100);
  })();

  const q = query.trim().toLowerCase();
  const visible = [...candidates].sort(SORTS[sort]).filter((c) => (statusFilter === 'All' || c.status === statusFilter)
    && (!q || c.name.toLowerCase().includes(q) || (c.email || '').toLowerCase().includes(q)));
  const rankOf = new Map([...candidates].sort(SORTS.match).map((c, i) => [c.id, i + 1]));
  const avg = (key) => {
    const vals = candidates.map((c) => c[key]).filter((v) => v != null);
    return vals.length ? Math.round(vals.reduce((s, v) => s + v, 0) / vals.length) : null;
  };
  const topMatch = candidates.length ? Math.max(...candidates.map((c) => c.jdMatchScore)) : null;
  const strongMatches = candidates.filter((c) => c.jdMatchScore >= prefs.matchThreshold).length;
  const needsReview = candidates.filter((c) => c.verificationScore != null && c.verificationScore < prefs.verificationThreshold).length;
  const statusItems = [
    { id: 'All', label: 'All', count: candidates.length },
    ...CANDIDATE_STATUSES.map((s) => ({ id: s, label: s, count: candidates.filter((c) => c.status === s).length }))
      .filter((s) => s.count > 0 || s.id === statusFilter),
  ];

  if (jobError) {
    return (
      <PageContainer>
        <Card>
          <EmptyState icon={Briefcase} title="Job not found" description="It may have been deleted, or it belongs to another account."
            action={<Button onClick={() => navigate('/jobs')}>Back to jobs</Button>} />
        </Card>
      </PageContainer>
    );
  }

  const chooseFiles = () => fileInputRef.current?.click();
  const showBigDropzone = !loading && candidates.length === 0 && activeTasks === 0 && !uploading;

  return (
    <div className="relative min-h-full" {...dragProps}>
      <input ref={fileInputRef} type="file" multiple accept={ACCEPTED_TYPES} className="sr-only" tabIndex={-1}
        aria-hidden="true" onChange={(e) => uploadFiles(e.target.files)} />

      {dragOver && (
        <div className="pointer-events-none absolute inset-3 z-30 flex items-center justify-center rounded-lg border-2 border-dashed border-primary bg-primary-soft/85 backdrop-blur-sm">
          <p className="flex items-center gap-2 text-base font-semibold text-primary-soft-fg"><Upload className="h-5 w-5" aria-hidden="true" />Drop resumes to upload</p>
        </div>
      )}

      <PageContainer>
        <PageHeader
          back={{ to: '/jobs', label: 'Jobs' }}
          title={job ? (
            <span className="flex flex-wrap items-center gap-x-3 gap-y-1">{job.title}<JobStatusPill status={job.status} /></span>
          ) : <Skeleton className="h-8 w-64" />}
          meta={job && (
            <>
              {job.department && <span className="flex items-center gap-1.5"><Briefcase className="h-3.5 w-3.5" aria-hidden="true" />{job.department}</span>}
              {job.location && <span className="flex items-center gap-1.5"><MapPin className="h-3.5 w-3.5" aria-hidden="true" />{job.location}</span>}
              {job.employmentType && <span className="flex items-center gap-1.5"><Clock className="h-3.5 w-3.5" aria-hidden="true" />{job.employmentType}</span>}
              <span className="flex items-center gap-1.5"><Users className="h-3.5 w-3.5" aria-hidden="true" />{candidates.length} candidate{candidates.length === 1 ? '' : 's'}</span>
            </>
          )}
          action={!showBigDropzone && (
            <Button onClick={chooseFiles} disabled={uploading}>
              {uploading ? <Loader2 className="animate-spin" aria-hidden="true" /> : <Upload aria-hidden="true" />}
              {uploading ? 'Uploading…' : 'Upload resumes'}
            </Button>
          )}
        />

        {/* Upload / screening progress */}
        {(uploading || activeTasks > 0 || newFailures > 0) && (
          <Card className="mb-5 p-4" aria-live="polite">
            {(uploading && uploadProgress) || activeTasks > 0 ? (
              <>
                <div className="mb-2 flex items-center justify-between gap-3 text-sm">
                  <span className="flex items-center gap-2 font-medium text-ink">
                    <Loader2 className="h-4 w-4 animate-spin text-primary-text" aria-hidden="true" />
                    {uploading
                      ? `Uploading ${uploadProgress.processed} of ${uploadProgress.total}…`
                      : `Screening resumes — ${taskCounts.processing} in progress, ${taskCounts.queued} queued`}
                  </span>
                  <span className="tabular-nums text-ink-3">
                    {uploading ? Math.round((uploadProgress.processed / uploadProgress.total) * 100) : processingPct}%
                  </span>
                </div>
                <div className="h-1.5 overflow-hidden rounded-full bg-subtle">
                  <div className="h-full rounded-full bg-primary transition-all duration-500"
                    style={{ width: `${uploading ? (uploadProgress.processed / uploadProgress.total) * 100 : processingPct}%` }} />
                </div>
                {!uploading && <p className="mt-2 text-xs text-ink-3">You can leave this page — screening continues in the background.</p>}
              </>
            ) : null}
            {newFailures > 0 && !uploading && (
              <div className={cn('flex items-center gap-2 text-sm text-danger', activeTasks > 0 && 'mt-3 border-t border-line pt-3')}>
                <AlertTriangle className="h-4 w-4 shrink-0" aria-hidden="true" />
                <p className="flex-1">{newFailures} resume{newFailures === 1 ? '' : 's'} could not be processed. Re-upload to retry.</p>
                <Button variant="ghost" size="sm" onClick={dismissFailures}>Dismiss</Button>
              </div>
            )}
          </Card>
        )}

        {showBigDropzone ? (
          <Card className="border-dashed border-line-strong">
            <div className="flex flex-col items-center px-6 py-14 text-center">
              <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-full border border-line bg-canvas">
                <Upload className="h-5 w-5 text-ink-2" aria-hidden="true" />
              </div>
              <p className="font-serif text-3xl text-ink">Upload resumes to start screening</p>
              <p className="mt-1 max-w-md text-sm text-ink-3">
                Drag and drop PDF, DOCX or TXT files anywhere on this page. Each resume is parsed, verified and ranked against this job.
              </p>
              <Button onClick={chooseFiles} className="mt-5"><Upload aria-hidden="true" /> Choose files</Button>
            </div>
          </Card>
        ) : (
          <div className="grid grid-cols-1 items-start gap-6 xl:grid-cols-[minmax(0,1fr)_300px]">
            {/* Candidates */}
            <Card className="overflow-hidden">
              <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line p-3">
                <Segmented label="Filter by status" items={statusItems} value={statusFilter} onChange={setStatusFilter} />
                <SearchInput value={query} onChange={setQuery} placeholder="Search name or email" className="w-full sm:w-56" />
              </div>

              {loading ? (
                <div className="space-y-3 p-5">{[1, 2, 3, 4].map((i) => <Skeleton key={i} className="h-10" />)}</div>
              ) : candidates.length === 0 ? (
                <EmptyState icon={FileText} title="No candidates yet"
                  description="Resumes are being screened — candidates appear here as each one finishes." />
              ) : visible.length === 0 ? (
                <EmptyState icon={Search} title="No matching candidates" description="Try a different search or status."
                  action={<Button variant="secondary" onClick={() => { setQuery(''); setStatusFilter('All'); }}>Clear filters</Button>} />
              ) : (
                <>
                  {/* Desktop table */}
                  <div className="hidden overflow-x-auto md:block">
                  <table className="w-full min-w-[680px] text-sm">
                    <thead className="border-b border-line text-left text-[11px] uppercase tracking-[0.08em] text-ink-3">
                      <tr>
                        <th scope="col" className="w-12 py-2.5 pl-5 pr-1 font-medium">#</th>
                        <SortHeader id="name" label="Candidate" sort={sort} setSort={setSort} />
                        <SortHeader id="match" label="Role match" sort={sort} setSort={setSort} className="w-[22%]" />
                        <SortHeader id="credibility" label="Credibility" sort={sort} setSort={setSort} className="w-[22%]" />
                        <th scope="col" className="w-36 px-3 py-2.5 font-medium">Status</th>
                        <th scope="col" className="w-8"><span className="sr-only">Open</span></th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-line">
                      {visible.map((c) => (
                        <tr key={c.id} onClick={() => openCandidate(c)} className="group cursor-pointer transition-colors hover:bg-subtle/70">
                          <td className="py-3 pl-5 pr-1 text-xs tabular-nums text-ink-3">{rankOf.get(c.id)}</td>
                          <td className="px-3 py-3">
                            <div className="flex min-w-0 items-center gap-3">
                              <Initials name={c.name} className="h-8 w-8" />
                              <div className="min-w-0">
                                <button type="button" onClick={(e) => { e.stopPropagation(); openCandidate(c); }}
                                  className="block max-w-full truncate rounded text-left font-medium text-ink hover:text-primary-text">
                                  {c.name}
                                </button>
                                <p className="truncate text-xs text-ink-3">{c.email || 'No email on resume'}</p>
                              </div>
                            </div>
                          </td>
                          <td className="px-3 py-3"><ScoreBar value={c.jdMatchScore} strong={prefs.matchThreshold} label="Role match" /></td>
                          <td className="px-3 py-3"><CredibilityCell candidate={c} prefs={prefs} /></td>
                          <td className="px-3 py-3"><StatusSelect candidate={c} onChange={handleStatusUpdate} /></td>
                          <td className="pr-4"><ChevronRight className="h-4 w-4 text-ink-3 opacity-0 transition-opacity group-hover:opacity-100" aria-hidden="true" /></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  </div>

                  {/* Phone list */}
                  <ul className="divide-y divide-line md:hidden">
                    {visible.map((c) => (
                      <li key={c.id} className="space-y-3 p-4">
                        <div className="flex items-start justify-between gap-3">
                          <button type="button" onClick={() => openCandidate(c)} className="flex min-w-0 items-center gap-3 text-left">
                            <Initials name={c.name} />
                            <div className="min-w-0">
                              <p className="truncate text-sm font-medium text-ink">{c.name}</p>
                              <p className="truncate text-xs text-ink-3">{c.email || 'No email on resume'}</p>
                            </div>
                          </button>
                          <StatusSelect candidate={c} onChange={handleStatusUpdate} />
                        </div>
                        <div className="grid grid-cols-2 gap-4 text-xs text-ink-3">
                          <div><p className="mb-1">Role match</p><ScoreBar value={c.jdMatchScore} strong={prefs.matchThreshold} /></div>
                          <div><p className="mb-1">Credibility</p><CredibilityCell candidate={c} prefs={prefs} /></div>
                        </div>
                      </li>
                    ))}
                  </ul>
                </>
              )}
            </Card>

            {/* Summary */}
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:sticky xl:top-6 xl:grid-cols-1">
              {candidates.length > 0 && (
                <Card>
                  <CardHeader title="Score overview" />
                  <div className="grid grid-cols-3 gap-2 p-4">
                    <ScoreRing value={topMatch} label="Top match" strong={prefs.matchThreshold} />
                    <ScoreRing value={avg('jdMatchScore')} label="Avg match" strong={prefs.matchThreshold} />
                    <ScoreRing value={avg('verificationScore')} label="Avg credibility" strong={prefs.verificationThreshold} />
                  </div>
                  <dl className="divide-y divide-line border-t border-line text-sm">
                    <div className="flex justify-between px-4 py-2.5">
                      <dt className="text-ink-3">Strong matches (≥{prefs.matchThreshold}%)</dt>
                      <dd className="font-medium tabular-nums text-ink">{strongMatches}</dd>
                    </div>
                    <div className="flex justify-between px-4 py-2.5">
                      <dt className="text-ink-3">Need manual review</dt>
                      <dd className={cn('font-medium tabular-nums', needsReview ? 'text-warning' : 'text-ink')}>{needsReview}</dd>
                    </div>
                  </dl>
                </Card>
              )}

              <Card>
                <CardHeader title="About this role" />
                <div className="p-4">
                  {job ? (
                    <>
                      <p className={cn('whitespace-pre-line text-sm leading-relaxed text-ink-2', !showFullDescription && 'line-clamp-5')}>
                        {job.description || 'No description provided.'}
                      </p>
                      {job.description?.length > 280 && (
                        <button type="button" onClick={() => setShowFullDescription((v) => !v)}
                          className="mt-1.5 text-sm font-medium text-primary-text hover:underline">
                          {showFullDescription ? 'Show less' : 'Show more'}
                        </button>
                      )}
                      {job.requirements?.length > 0 && (
                        <div className="mt-4">
                          <p className="mb-2 text-xs font-medium text-ink-3">Required skills</p>
                          <div className="flex flex-wrap gap-1.5">{job.requirements.map((skill) => <Tag key={skill}>{skill}</Tag>)}</div>
                        </div>
                      )}
                    </>
                  ) : <div className="space-y-2"><Skeleton className="h-4" /><Skeleton className="h-4 w-4/5" /><Skeleton className="h-4 w-3/5" /></div>}
                </div>
              </Card>
            </div>
          </div>
        )}
      </PageContainer>

      <CandidateModal
        open={!!selectedCandidate}
        candidate={selectedCandidate}
        job={job}
        prefs={prefs}
        onClose={closeCandidate}
        onStatusUpdate={handleStatusUpdate}
        onTakeInterview={(c) => navigate(`/jobs/${jobId}/candidates/${c.id}/interview`)}
      />
    </div>
  );
};

export default CandidatePipeline;
