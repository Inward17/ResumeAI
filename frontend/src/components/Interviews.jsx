import React, { useState, useEffect, useMemo, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { Calendar, Users, Star, CheckCircle, Search, Mail, User, Briefcase, ChevronDown } from 'lucide-react';
import { useToast } from '../hooks/use-toast';
import { getJobs, getJobCandidates, updateCandidateStatus } from '../services/jobService';
import { CANDIDATE_STATUSES, INTERVIEW_STATUSES } from '../lib/statuses';
import { loadPreferences } from '../lib/preferences';
import { cn } from '../lib/utils';
import CandidateModal from './CandidateModal';
import { Card, PageContainer, PageHeader, StatusPill, Initials, EmptyState, PrimaryButton } from './common';

const MoveMenu = ({ candidate, onMove }) => {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  useEffect(() => {
    if (!open) return undefined;
    const close = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    const onKey = (e) => { if (e.key === 'Escape') setOpen(false); };
    document.addEventListener('mousedown', close);
    document.addEventListener('keydown', onKey);
    return () => { document.removeEventListener('mousedown', close); document.removeEventListener('keydown', onKey); };
  }, [open]);
  return (
    <div className="relative" ref={ref}>
      <button type="button" onClick={() => setOpen((o) => !o)} aria-haspopup="menu" aria-expanded={open}
        className="flex items-center gap-1 rounded-xl border border-slate-200 px-3 py-2 text-xs font-bold text-slate-700 transition-colors hover:bg-slate-50">
        Move to <ChevronDown className="h-3.5 w-3.5" aria-hidden="true" />
      </button>
      {open && (
        <div role="menu" className="absolute bottom-full right-0 z-20 mb-1 w-44 overflow-hidden rounded-xl border border-slate-200 bg-white py-1 shadow-xl">
          {CANDIDATE_STATUSES.filter((s) => s !== candidate.status).map((s) => (
            <button key={s} role="menuitem" type="button" onClick={() => { setOpen(false); onMove(s); }}
              className="w-full px-4 py-2 text-left text-sm text-slate-700 transition-colors hover:bg-slate-50">
              {s}
            </button>
          ))}
        </div>
      )}
    </div>
  );
};

const InterviewCard = ({ candidate, job, onView, onMove }) => (
  <Card className="p-5 transition-shadow hover:shadow-md">
    <div className="mb-4 flex items-start justify-between gap-3">
      <div className="flex min-w-0 items-center gap-3">
        <Initials name={candidate.name} className="h-10 w-10 text-sm" />
        <div className="min-w-0">
          <p className="truncate text-sm font-bold text-slate-900">{candidate.name}</p>
          <p className="mt-0.5 flex items-center gap-1 truncate text-xs text-slate-600">
            <Briefcase className="h-3 w-3 shrink-0" aria-hidden="true" />{job.title}
          </p>
        </div>
      </div>
      <StatusPill status={candidate.status} />
    </div>

    <div className="mb-3">
      <div className="mb-1 flex justify-between text-xs">
        <span className="font-semibold text-slate-600">Role match</span>
        <span className="font-bold text-brand">{candidate.jdMatchScore}%</span>
      </div>
      <div className="h-1.5 overflow-hidden rounded-full bg-slate-100">
        <div className={cn('h-full rounded-full', candidate.jdMatchScore >= 75 ? 'bg-emerald-500' : candidate.jdMatchScore >= 50 ? 'bg-brand-accent' : 'bg-amber-500')}
          style={{ width: `${candidate.jdMatchScore}%` }} />
      </div>
    </div>

    <div className="mb-4 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-slate-600">
      {candidate.email && <span className="flex min-w-0 items-center gap-1"><Mail className="h-3 w-3 shrink-0" aria-hidden="true" /><span className="truncate">{candidate.email}</span></span>}
      <span className="flex items-center gap-1"><CheckCircle className="h-3 w-3 text-emerald-600" aria-hidden="true" />{candidate.verificationScore}% credibility</span>
    </div>

    <div className="flex items-center gap-2 border-t border-slate-100 pt-3">
      <PrimaryButton onClick={onView} className="flex-1 py-2 text-xs">
        <User className="h-3.5 w-3.5" aria-hidden="true" /> View dossier
      </PrimaryButton>
      <MoveMenu candidate={candidate} onMove={onMove} />
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

  const handleMove = async (candidateId, jobId, status) => {
    try {
      await updateCandidateStatus(jobId, candidateId, status);
      setEntries((prev) => prev
        .map((e) => (e.candidate.id === candidateId && e.job.id === jobId ? { ...e, candidate: { ...e.candidate, status } } : e))
        .filter((e) => INTERVIEW_STATUSES.includes(e.candidate.status)));
      toast({ title: `Moved to ${status}` });
    } catch (err) {
      toast({ title: 'Could not update status', description: err.message, variant: 'destructive' });
    }
  };

  const q = search.trim().toLowerCase();
  const filtered = entries.filter(({ candidate, job }) =>
    (filterStatus === 'All' || candidate.status === filterStatus)
    && (!q || candidate.name.toLowerCase().includes(q) || job.title.toLowerCase().includes(q) || candidate.email.toLowerCase().includes(q)));

  const total = entries.length;
  const avgMatch = total ? Math.round(entries.reduce((s, e) => s + e.candidate.jdMatchScore, 0) / total) : null;
  const countOf = (status) => entries.filter((e) => e.candidate.status === status).length;
  const selectedEntry = selected && entries.find((e) => e.candidate.id === selected.candidateId && e.job.id === selected.jobId);

  return (
    <PageContainer>
      <PageHeader
        eyebrow="Interviews"
        title="Interview pipeline"
        description="Shortlisted and interview-stage candidates across all your job postings."
      />

      <div className="mb-6 grid grid-cols-2 gap-3 md:grid-cols-4 md:gap-4">
        {[
          { label: 'In pipeline', value: total, Icon: Users },
          { label: 'Avg role match', value: avgMatch == null ? '—' : `${avgMatch}%`, Icon: Star },
          { label: 'Shortlisted', value: countOf('Shortlisted'), Icon: CheckCircle },
          { label: 'Interview stage', value: countOf('Interview'), Icon: Calendar },
        ].map(({ label, value, Icon }) => (
          <Card key={label} className="p-5">
            <div className="mb-2 flex items-center justify-between">
              <p className="text-xs font-bold uppercase tracking-wider text-slate-500">{label}</p>
              <Icon className="h-4 w-4 text-brand-accent" aria-hidden="true" />
            </div>
            <p className="font-display text-2xl font-extrabold text-slate-900">{loading ? '…' : value}</p>
          </Card>
        ))}
      </div>

      <div className="mb-6 flex flex-col gap-3 md:flex-row md:items-center">
        <div className="relative w-full md:max-w-xs">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500" aria-hidden="true" />
          <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search candidates or jobs" aria-label="Search candidates or jobs"
            className="w-full rounded-xl border border-slate-200 bg-white py-2.5 pl-9 pr-4 text-sm outline-none focus:border-brand-accent focus:ring-2 focus:ring-brand-soft" />
        </div>
        <div className="no-scrollbar flex gap-1 overflow-x-auto rounded-xl border border-slate-200 bg-white p-1" role="tablist" aria-label="Filter by status">
          {['All', ...INTERVIEW_STATUSES].map((s) => (
            <button key={s} type="button" role="tab" aria-selected={filterStatus === s} onClick={() => setFilterStatus(s)}
              className={cn('whitespace-nowrap rounded-lg px-4 py-1.5 text-sm font-semibold transition-colors',
                filterStatus === s ? 'bg-brand text-white' : 'text-slate-600 hover:text-slate-900')}>
              {s}
            </button>
          ))}
        </div>
      </div>

      {loading ? (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
          {[1, 2, 3].map((i) => <div key={i} className="h-52 animate-pulse rounded-2xl border border-slate-200 bg-white" />)}
        </div>
      ) : filtered.length === 0 ? (
        <Card>
          <EmptyState
            icon={Calendar}
            title={total === 0 ? 'No interview candidates yet' : 'No matching candidates'}
            description={total === 0
              ? 'Move candidates to "Shortlisted" or "Interview" from a job pipeline and they will appear here.'
              : 'Try a different search or filter.'}
            action={total === 0 && <PrimaryButton onClick={() => navigate('/jobs')}>Go to job postings</PrimaryButton>}
          />
        </Card>
      ) : (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
          {filtered.map(({ candidate, job }) => (
            <InterviewCard
              key={`${job.id}-${candidate.id}`}
              candidate={candidate}
              job={job}
              onView={() => setSelected({ candidateId: candidate.id, jobId: job.id })}
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
        onTakeInterview={(c) => navigate(`/jobs/${selectedEntry.job.id}/candidates/${c.id}/interview`)}
      />
    </PageContainer>
  );
};

export default Interviews;
