import React, { useState, useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { CalendarCheck, Briefcase, Mail, ArrowRight, Search } from 'lucide-react';
import { useToast } from '../hooks/use-toast';
import { getJobs, getJobCandidates, updateCandidateStatus } from '../services/jobService';
import { INTERVIEW_STATUSES } from '../lib/statuses';
import { loadPreferences } from '../lib/preferences';
import CandidateModal from './CandidateModal';
import {
  Card, PageContainer, PageHeader, Initials, EmptyState, Button, StatStrip, ScoreBar, Segmented, SearchInput, StatusSelect, Skeleton,
} from './common';

const InterviewCard = ({ candidate, job, prefs, onView, onStart, onMove }) => (
  <Card className="flex flex-col p-4 transition-colors hover:border-line-strong">
    <div className="flex items-start justify-between gap-3">
      <button type="button" onClick={onView} className="flex min-w-0 items-center gap-3 rounded-lg text-left">
        <Initials name={candidate.name} className="h-10 w-10 text-sm" />
        <div className="min-w-0">
          <p className="truncate text-sm font-semibold text-ink hover:text-primary-text">{candidate.name}</p>
          <p className="mt-0.5 flex items-center gap-1 truncate text-xs text-ink-3">
            <Briefcase className="h-3 w-3 shrink-0" aria-hidden="true" />{job.title}
          </p>
        </div>
      </button>
      <StatusSelect candidate={candidate} onChange={(_, status) => onMove(status)} />
    </div>

    <dl className="mt-4 grid grid-cols-2 gap-4 text-xs">
      <div><dt className="mb-1 text-ink-3">Role match</dt><dd><ScoreBar value={candidate.jdMatchScore} strong={prefs.matchThreshold} /></dd></div>
      <div><dt className="mb-1 text-ink-3">Credibility</dt><dd><ScoreBar value={candidate.verificationScore} strong={prefs.verificationThreshold} /></dd></div>
    </dl>

    {candidate.email && (
      <a href={`mailto:${candidate.email}`} className="mt-3 flex min-w-0 items-center gap-1.5 text-xs text-ink-3 hover:text-primary-text">
        <Mail className="h-3.5 w-3.5 shrink-0" aria-hidden="true" /><span className="truncate">{candidate.email}</span>
      </a>
    )}

    <div className="mt-4 flex gap-2 border-t border-line pt-3">
      <Button variant="secondary" size="sm" onClick={onView} className="flex-1">View dossier</Button>
      <Button size="sm" onClick={onStart} className="flex-1">Start interview <ArrowRight aria-hidden="true" /></Button>
    </div>
  </Card>
);

const Interviews = () => {
  const { toast } = useToast();
  const navigate = useNavigate();
  const prefs = useMemo(loadPreferences, []);
  const [entries, setEntries] = useState([]); // [{candidate, job}]
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [filterStatus, setFilterStatus] = useState('All');
  const [selected, setSelected] = useState(null); // {candidateId, jobId}

  useEffect(() => {
    const load = async () => {
      try {
        const jobs = await getJobs();
        const lists = await Promise.all(jobs.map(async (job) => {
          try {
            const candidates = await getJobCandidates(job.id);
            return candidates.filter((c) => INTERVIEW_STATUSES.includes(c.status)).map((candidate) => ({ candidate, job }));
          } catch {
            return [];
          }
        }));
        setEntries(lists.flat().sort((a, b) => b.candidate.jdMatchScore - a.candidate.jdMatchScore));
      } catch (err) {
        toast({ title: 'Could not load interviews', description: err.message, variant: 'destructive' });
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [toast]);

  // Candidates moved out of the interview track stay visible (with their new status)
  // until the next visit, so a mis-click can be undone from the same card.
  const handleMove = async (candidateId, jobId, status) => {
    const update = (s) => setEntries((prev) => prev.map((e) => (
      e.candidate.id === candidateId && e.job.id === jobId ? { ...e, candidate: { ...e.candidate, status: s } } : e)));
    const previous = entries.find((e) => e.candidate.id === candidateId && e.job.id === jobId)?.candidate.status;
    update(status);
    try {
      await updateCandidateStatus(jobId, candidateId, status);
      toast({ title: `Moved to ${status}` });
    } catch (err) {
      update(previous);
      toast({ title: 'Could not update status', description: err.message, variant: 'destructive' });
    }
  };

  const q = search.trim().toLowerCase();
  const filtered = entries.filter(({ candidate, job }) =>
    (filterStatus === 'All' || candidate.status === filterStatus)
    && (!q || candidate.name.toLowerCase().includes(q) || job.title.toLowerCase().includes(q) || (candidate.email || '').toLowerCase().includes(q)));

  const total = entries.length;
  const avgMatch = total ? Math.round(entries.reduce((s, e) => s + e.candidate.jdMatchScore, 0) / total) : null;
  const countOf = (status) => entries.filter((e) => e.candidate.status === status).length;
  const selectedEntry = selected && entries.find((e) => e.candidate.id === selected.candidateId && e.job.id === selected.jobId);
  const startInterview = (jobId, candidateId) => navigate(`/jobs/${jobId}/candidates/${candidateId}/interview`);

  return (
    <PageContainer>
      <PageHeader
        title="Interviews"
        description="Shortlisted and interview-stage candidates across all your jobs."
      />

      <div className="mb-6">
        <StatStrip loading={loading} items={[
          { label: 'In pipeline', value: total },
          { label: 'Shortlisted', value: countOf('Shortlisted') },
          { label: 'Interview stage', value: countOf('Interview') },
          { label: 'Avg role match', value: avgMatch == null ? '—' : `${avgMatch}%` },
        ]} />
      </div>

      {total > 0 && (
        <div className="mb-5 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <Segmented label="Filter by status" value={filterStatus} onChange={setFilterStatus}
            items={[{ id: 'All', label: 'All', count: total }, ...INTERVIEW_STATUSES.map((s) => ({ id: s, label: s, count: countOf(s) }))]} />
          <SearchInput value={search} onChange={setSearch} placeholder="Search candidates or jobs" className="sm:w-64" />
        </div>
      )}

      {loading ? (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
          {[1, 2, 3].map((i) => <Skeleton key={i} className="h-52 rounded-lg" />)}
        </div>
      ) : filtered.length === 0 ? (
        <Card>
          {total === 0 ? (
            <EmptyState
              icon={CalendarCheck}
              title="No interview candidates yet"
              description='Set a candidate to "Shortlisted" or "Interview" in a job pipeline and they will appear here.'
              action={<Button onClick={() => navigate('/jobs')}>Go to jobs</Button>}
            />
          ) : (
            <EmptyState icon={Search} title="No matching candidates" description="Try a different search or filter."
              action={<Button variant="secondary" onClick={() => { setSearch(''); setFilterStatus('All'); }}>Clear filters</Button>} />
          )}
        </Card>
      ) : (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
          {filtered.map(({ candidate, job }) => (
            <InterviewCard
              key={`${job.id}-${candidate.id}`}
              candidate={candidate}
              job={job}
              prefs={prefs}
              onView={() => setSelected({ candidateId: candidate.id, jobId: job.id })}
              onStart={() => startInterview(job.id, candidate.id)}
              onMove={(status) => handleMove(candidate.id, job.id, status)}
            />
          ))}
        </div>
      )}

      <CandidateModal
        open={!!selectedEntry}
        candidate={selectedEntry?.candidate}
        job={selectedEntry?.job}
        prefs={prefs}
        onClose={() => setSelected(null)}
        onStatusUpdate={(candidateId, status) => handleMove(candidateId, selectedEntry.job.id, status)}
        onTakeInterview={(c) => startInterview(selectedEntry.job.id, c.id)}
      />
    </PageContainer>
  );
};

export default Interviews;
