import React, { useState, useEffect } from 'react';
import {
  Calendar, MapPin, Clock, Users, ChevronRight,
  CheckCircle, Star, Search, Filter, Zap, Phone,
  Mail, ArrowRight, User, Briefcase
} from 'lucide-react';
import { useToast } from '../hooks/use-toast';
import { getJobs, getJobCandidates, updateCandidateStatus } from '../services/jobService';
import CandidateModal from './CandidateModal';
import { C } from '../theme';

/* Statuses that qualify for the Interviews view */
const INTERVIEW_STATUSES = ['Interview', 'Shortlisted', 'shortlisted', 'interview'];

/* ── Status pill ── */
const StatusPill = ({ status }) => {
  const map = {
    'Interview':   { bg: '#d1fae5', text: '#065f46', label: 'INTERVIEW' },
    'interview':   { bg: '#d1fae5', text: '#065f46', label: 'INTERVIEW' },
    'Shortlisted': { bg: '#e0e7ff', text: '#3730a3', label: 'SHORTLISTED' },
    'shortlisted': { bg: '#e0e7ff', text: '#3730a3', label: 'SHORTLISTED' },
    'Under Review':{ bg: '#fef3c7', text: '#92400e', label: 'UNDER REVIEW' },
    'Rejected':    { bg: '#fee2e2', text: '#991b1b', label: 'REJECTED' },
  };
  const s = map[status] || { bg: '#f1f5f9', text: '#475569', label: status?.toUpperCase() };
  return (
    <span
      className="text-[10px] font-bold px-2.5 py-1 rounded-full tracking-wider"
      style={{ background: s.bg, color: s.text }}
    >
      {s.label}
    </span>
  );
};

/* ── Candidate card ── */
const InterviewCard = ({ candidate, job, onView, onStatusChange }) => {
  const match = Math.round(candidate.jdMatchScore ?? 0);
  const [menuOpen, setMenuOpen] = useState(false);

  return (
    <div className="bg-white rounded-2xl border border-slate-200 shadow-sm hover:shadow-md transition-shadow p-5">
      {/* Top row */}
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-3">
          {/* Avatar */}
          <div
            className="h-10 w-10 rounded-full flex items-center justify-center text-white text-sm font-bold shrink-0"
            style={{ background: C.primary }}
          >
            {(candidate.name || '?').charAt(0).toUpperCase()}
          </div>
          <div>
            <p className="font-bold text-slate-900 text-sm">{candidate.name || 'Unknown'}</p>
            <p className="text-xs text-slate-400 mt-0.5 flex items-center gap-1">
              <Briefcase className="h-3 w-3" />
              {job?.title || 'Job Posting'}
            </p>
          </div>
        </div>
        <StatusPill status={candidate.status} />
      </div>

      {/* Score bar */}
      <div className="mb-3">
        <div className="flex justify-between text-[11px] mb-1">
          <span className="text-slate-400 font-semibold">JD Match</span>
          <span className="font-bold" style={{ color: C.primary }}>{match}%</span>
        </div>
        <div className="h-1.5 rounded-full bg-slate-100 overflow-hidden">
          <div
            className="h-full rounded-full"
            style={{
              width: `${match}%`,
              background: match >= 80
                ? `linear-gradient(90deg, ${C.accent}, ${C.cyan})`
                : match >= 60
                ? `linear-gradient(90deg, #818cf8, ${C.accent})`
                : '#fbbf24',
            }}
          />
        </div>
      </div>

      {/* Contact info */}
      <div className="flex items-center gap-3 text-xs text-slate-400 mb-4">
        {candidate.email && (
          <span className="flex items-center gap-1 truncate">
            <Mail className="h-3 w-3 shrink-0" />
            <span className="truncate max-w-[140px]">{candidate.email}</span>
          </span>
        )}
        {candidate.verificationScore > 0 && (
          <span className="flex items-center gap-1">
            <CheckCircle className="h-3 w-3" style={{ color: C.cyan }} />
            <span className="font-semibold">{Math.round(candidate.verificationScore)}% verified</span>
          </span>
        )}
      </div>

      {/* Actions */}
      <div className="flex items-center gap-2 pt-3 border-t border-slate-100">
        <button
          onClick={() => onView(candidate, job)}
          className="flex-1 flex items-center justify-center gap-1.5 py-2 rounded-xl text-xs font-bold transition-colors hover:opacity-90 text-white"
          style={{ background: C.primary }}
        >
          <User className="h-3.5 w-3.5" />
          View Dossier
        </button>
        <div className="relative">
          <button
            onClick={() => setMenuOpen(o => !o)}
            className="px-3 py-2 rounded-xl text-xs font-bold border border-slate-200 hover:bg-slate-50 transition-colors text-slate-600"
          >
            Move To ▾
          </button>
          {menuOpen && (
            <div className="absolute bottom-full right-0 mb-1 w-44 bg-white rounded-xl border border-slate-200 shadow-xl z-20 overflow-hidden">
              {['Under Review', 'Shortlisted', 'Interview', 'Rejected'].map(s => (
                <button
                  key={s}
                  onClick={() => { onStatusChange(candidate.id, job?.id, s); setMenuOpen(false); }}
                  className="w-full text-left px-4 py-2.5 text-sm hover:bg-slate-50 text-slate-700 transition-colors"
                >
                  {s}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

/* ── Main Component ── */
const Interviews = ({ onTakeInterview }) => {
  const { toast } = useToast();
  const [interviewCandidates, setInterviewCandidates] = useState([]); // [{candidate, job}]
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [filterStatus, setFilterStatus] = useState('All');
  const [selectedEntry, setSelectedEntry] = useState(null); // {candidate, job}

  /* Fetch all jobs then all their candidates, filter to interview-track ones */
  const loadData = async () => {
    setLoading(true);
    try {
      const jobs = await getJobs();
      const results = [];
      await Promise.all(
        jobs.map(async (job) => {
          try {
            const candidates = await getJobCandidates(job.id);
            candidates
              .filter(c => INTERVIEW_STATUSES.includes(c.status))
              .forEach(c => results.push({ candidate: c, job }));
          } catch {
            // skip failed job
          }
        })
      );
      // Sort by jdMatchScore descending
      results.sort((a, b) => (b.candidate.jdMatchScore ?? 0) - (a.candidate.jdMatchScore ?? 0));
      setInterviewCandidates(results);
    } catch (err) {
      toast({ title: 'Failed to load interviews', variant: 'destructive' });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadData(); }, []);

  const handleStatusChange = async (candidateId, jobId, newStatus) => {
    try {
      await updateCandidateStatus(jobId, candidateId, newStatus);
      // Optimistic update: remove from list if no longer an interview status
      if (!INTERVIEW_STATUSES.includes(newStatus)) {
        setInterviewCandidates(prev =>
          prev.filter(({ candidate }) => candidate.id !== candidateId)
        );
      } else {
        setInterviewCandidates(prev =>
          prev.map(({ candidate, job }) =>
            candidate.id === candidateId
              ? { candidate: { ...candidate, status: newStatus }, job }
              : { candidate, job }
          )
        );
      }
      toast({ title: `Status updated to "${newStatus}"` });
    } catch {
      toast({ title: 'Failed to update status', variant: 'destructive' });
    }
  };

  /* Filter */
  const filtered = interviewCandidates.filter(({ candidate, job }) => {
    const q = search.toLowerCase();
    const matchSearch = !q ||
      candidate.name?.toLowerCase().includes(q) ||
      job?.title?.toLowerCase().includes(q) ||
      candidate.email?.toLowerCase().includes(q);
    const matchStatus = filterStatus === 'All' || candidate.status === filterStatus;
    return matchSearch && matchStatus;
  });

  /* Stats */
  const total = interviewCandidates.length;
  const avgMatch = total
    ? Math.round(interviewCandidates.reduce((s, { candidate }) => s + (candidate.jdMatchScore ?? 0), 0) / total)
    : 0;
  const shortlisted = interviewCandidates.filter(({ candidate }) =>
    candidate.status === 'Shortlisted' || candidate.status === 'shortlisted'
  ).length;
  const toInterview = interviewCandidates.filter(({ candidate }) =>
    candidate.status === 'Interview' || candidate.status === 'interview'
  ).length;

  return (
    <div className="min-h-full p-8" style={{ background: C.pageGray }}>
      {/* ── Header ── */}
      <div className="mb-6">
        <h1 className="text-2xl font-black text-slate-900">Interview Pipeline</h1>
        <p className="text-sm text-slate-400 mt-1">
          Candidates shortlisted or scheduled for interview across all job postings.
        </p>
      </div>

      {/* ── Stat cards ── */}
      <div className="grid grid-cols-4 gap-4 mb-6">
        {[
          { label: 'Total in Pipeline', value: total, icon: Users, color: C.primary },
          { label: 'Avg Match Score',   value: `${avgMatch}%`, icon: Star, color: C.accent },
          { label: 'Shortlisted',       value: shortlisted, icon: CheckCircle, color: '#0e7490' },
          { label: 'Interview Stage',   value: toInterview, icon: Calendar, color: '#059669' },
        ].map(({ label, value, icon: Icon, color }) => (
          <div key={label} className="bg-white rounded-2xl border border-slate-200 shadow-sm p-5">
            <div className="flex items-center justify-between mb-2">
              <p className="text-[11px] font-bold uppercase tracking-widest text-slate-400">{label}</p>
              <Icon className="h-4 w-4" style={{ color }} />
            </div>
            <p className="text-2xl font-black" style={{ color }}>{value}</p>
          </div>
        ))}
      </div>

      {/* ── Filter bar ── */}
      <div className="flex items-center gap-3 mb-6">
        {/* Search */}
        <div className="relative flex-1 max-w-xs">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
          <input
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="Search candidates or jobs..."
            className="w-full pl-9 pr-4 py-2.5 rounded-xl border border-slate-200 bg-white text-sm text-slate-700 outline-none focus:ring-2 focus:ring-indigo-200"
          />
        </div>

        {/* Status filter tabs */}
        <div className="flex items-center bg-white border border-slate-200 rounded-xl p-1 gap-1">
          {['All', 'Interview', 'Shortlisted'].map(s => (
            <button
              key={s}
              onClick={() => setFilterStatus(s)}
              className="px-4 py-1.5 rounded-lg text-sm font-semibold transition-all"
              style={filterStatus === s
                ? { background: C.primary, color: 'white' }
                : { background: 'transparent', color: '#64748b' }
              }
            >
              {s}
            </button>
          ))}
        </div>
      </div>

      {/* ── Cards grid ── */}
      {loading ? (
        <div className="flex flex-col items-center justify-center py-20 gap-3">
          <div className="h-10 w-10 rounded-xl animate-pulse" style={{ background: C.activeBg ?? '#eef2ff' }} />
          <p className="text-slate-400 text-sm">Loading interview pipeline…</p>
        </div>
      ) : filtered.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-24 gap-4">
          <div
            className="h-16 w-16 rounded-2xl flex items-center justify-center"
            style={{ background: '#eef2ff' }}
          >
            <Calendar className="h-8 w-8" style={{ color: C.accent }} />
          </div>
          <div className="text-center">
            <p className="font-bold text-slate-900">No interview candidates yet</p>
            <p className="text-sm text-slate-400 mt-1">
              {search
                ? 'No results match your search.'
                : 'Move candidates to "Shortlisted" or "Interview" status from a job pipeline to see them here.'}
            </p>
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {filtered.map(({ candidate, job }) => (
            <InterviewCard
              key={`${job?.id}-${candidate.id}`}
              candidate={candidate}
              job={job}
              onView={(c, j) => setSelectedEntry({ candidate: c, job: j })}
              onStatusChange={handleStatusChange}
            />
          ))}
        </div>
      )}

      {/* ── AI smart tip ── */}
      {!loading && total > 0 && (
        <div
          className="mt-6 rounded-2xl p-5 flex items-start gap-4"
          style={{ background: `linear-gradient(135deg, ${C.primary} 0%, #312e81 100%)` }}
        >
          <Zap className="h-5 w-5 shrink-0 mt-0.5" style={{ color: C.cyan }} />
          <div>
            <p className="text-sm font-bold text-white mb-1">AI Interview Insight</p>
            <p className="text-xs leading-relaxed" style={{ color: '#c7d2fe' }}>
              You have <strong className="text-white">{total} candidates</strong> in your interview pipeline
              with an average JD match of <strong className="text-white">{avgMatch}%</strong>.
              {avgMatch >= 75
                ? ' Your pipeline quality is excellent — candidates are strongly aligned with job requirements.'
                : ' Consider reviewing match thresholds to improve pipeline quality.'}
            </p>
          </div>
        </div>
      )}

      {/* ── Candidate Dossier Modal ── */}
      {selectedEntry && (
        <CandidateModal
          candidate={selectedEntry.candidate}
          job={selectedEntry.job}
          onClose={() => setSelectedEntry(null)}
          onStatusUpdate={(candidateId, status) =>
            handleStatusChange(candidateId, selectedEntry.job?.id, status)
          }
          onTakeInterview={(candidate, job) => {
            setSelectedEntry(null);
            if (onTakeInterview) onTakeInterview(candidate, job);
          }}
        />
      )}
    </div>
  );
};

export default Interviews;
