import React, { useState, useEffect, useRef } from 'react';
import {
  Plus, MoreVertical, Eye, Edit, Trash2, Archive,
  MapPin, Clock, Users, Zap, TrendingUp, ArrowUpRight
} from 'lucide-react';
import { getJobs, createJob, updateJob, deleteJob } from '../services/jobService';
import JobModal from './JobModal';
import { useToast } from '../hooks/use-toast';
import { C } from '../theme';

const FILTERS = ['All', 'Active', 'Drafts', 'Closed'];

/* ─────────────────── Shared Card ─────────────────── */
const Panel = ({ children, className = '' }) => (
  <div className={`bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden ${className}`}>
    {children}
  </div>
);

/* ─────────────────── Status pill ─────────────────── */
const StatusPill = ({ status }) => {
  const cfg = {
    Active:  { bg: '#cffafe', text: '#0e7490', dot: '#22d3ee' },
    Closed:  { bg: '#f1f5f9', text: '#64748b', dot: '#94a3b8' },
    Draft:   { bg: '#fef9c3', text: '#854d0e', dot: '#fbbf24' },
  };
  const c = cfg[status] || cfg.Closed;
  return (
    <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-bold uppercase"
      style={{ background: c.bg, color: c.text }}>
      <span className="w-1.5 h-1.5 rounded-full inline-block" style={{ background: c.dot }} />
      {status}
    </span>
  );
};

/* ─────────────────── Action Menu ─────────────────── */
const ActionMenu = ({ job, onEdit, onViewCandidates, onDelete }) => {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    const handler = (e) => {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={(e) => { e.stopPropagation(); setOpen(o => !o); }}
        className="p-1.5 rounded-lg hover:bg-slate-100 text-slate-400 hover:text-slate-700 transition-colors"
      >
        <MoreVertical className="h-5 w-5" />
      </button>
      {open && (
        <div className="absolute right-0 top-8 z-50 w-44 bg-white rounded-xl border border-slate-200 shadow-xl py-1.5">
          <button onClick={() => { onViewCandidates(job); setOpen(false); }}
            className="flex items-center gap-3 w-full px-4 py-2.5 text-sm text-slate-700 hover:bg-slate-50 transition-colors">
            <Eye className="h-4 w-4 text-slate-400" /> View Candidates
          </button>
          <button onClick={() => { onEdit(job); setOpen(false); }}
            className="flex items-center gap-3 w-full px-4 py-2.5 text-sm text-slate-700 hover:bg-slate-50 transition-colors">
            <Edit className="h-4 w-4 text-slate-400" /> Edit Job
          </button>
          <button onClick={() => { setOpen(false); }}
            className="flex items-center gap-3 w-full px-4 py-2.5 text-sm text-slate-700 hover:bg-slate-50 transition-colors">
            <Archive className="h-4 w-4 text-slate-400" /> Archive
          </button>
          <div className="my-1 border-t border-slate-100" />
          <button onClick={() => { onDelete(job.id); setOpen(false); }}
            className="flex items-center gap-3 w-full px-4 py-2.5 text-sm text-red-600 hover:bg-red-50 transition-colors">
            <Trash2 className="h-4 w-4" /> Delete
          </button>
        </div>
      )}
    </div>
  );
};

/* ─────────────────── Job Card ─────────────────── */
const JobCard = ({ job, onEdit, onViewCandidates, onDelete }) => (
  <Panel
    className="p-5 flex flex-col gap-4 cursor-pointer hover:shadow-md transition-shadow"
  >
    <div className="flex items-start justify-between">
      <div className="flex-1 pr-2 cursor-pointer" onClick={() => onViewCandidates(job)}>
        <StatusPill status={job.status} />
        <h3 className="text-base font-bold text-slate-900 mt-2 leading-tight">{job.title}</h3>
        <p className="text-xs text-slate-400 mt-1 line-clamp-2">{job.description}</p>
      </div>
      <ActionMenu job={job} onEdit={onEdit} onViewCandidates={onViewCandidates} onDelete={onDelete} />
    </div>

    <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-400">
      {job.location    && <span className="flex items-center gap-1"><MapPin className="h-3 w-3" />{job.location}</span>}
      {job.employmentType && <span className="flex items-center gap-1"><Clock className="h-3 w-3" />{job.employmentType}</span>}
      <span className="flex items-center gap-1"><Users className="h-3 w-3" />{job.totalCandidates || 0} candidates</span>
    </div>

    {job.requirements?.length > 0 && (
      <div className="flex flex-wrap gap-1.5">
        {job.requirements.slice(0, 4).map(skill => (
          <span key={skill} className="text-[11px] px-2 py-0.5 rounded-full font-medium"
            style={{ background: '#eef2ff', color: C.accent }}>
            {skill}
          </span>
        ))}
        {job.requirements.length > 4 && (
          <span className="text-[11px] px-2 py-0.5 rounded-full bg-slate-100 text-slate-500 font-medium">
            +{job.requirements.length - 4}
          </span>
        )}
      </div>
    )}

    <div className="flex items-center justify-between pt-3 border-t border-slate-100">
      <span className="text-xs text-slate-400">
        {job.postedAt ? new Date(job.postedAt).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }) : '—'}
      </span>
      <button
        onClick={() => onViewCandidates(job)}
        className="flex items-center gap-1 text-xs font-bold transition-colors"
        style={{ color: C.accent }}
      >
        View Pipeline <ArrowUpRight className="h-3.5 w-3.5" />
      </button>
    </div>
  </Panel>
);

/* ─────────────────── Smart Tip Card ─────────────────── */
const SmartTip = () => (
  <div className="rounded-2xl p-5 col-span-full md:col-span-1"
    style={{ background: `linear-gradient(135deg, ${C.primary} 0%, #312e81 60%, ${C.accent} 100%)` }}>
    <p className="text-[10px] font-bold uppercase tracking-widest mb-2" style={{ color: '#818cf8' }}>Weekly Pipeline Health</p>
    <p className="font-bold text-white text-base leading-snug mb-2">AI-Curated Talent Pool</p>
    <p className="text-sm leading-relaxed mb-3" style={{ color: '#c7d2fe' }}>
      Your talent pool grew by 14% this week. Total quality leads: 128.
      Update the "Senior UX Designer" role skills to increase match accuracy by 22%.
    </p>
    <button className="flex items-center gap-1 text-sm font-bold" style={{ color: '#818cf8' }}>
      View Analytics <ArrowUpRight className="h-3.5 w-3.5" />
    </button>
  </div>
);

/* ─────────────────── Main Component ─────────────────── */
const JobPostings = ({ onViewCandidates }) => {
  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('All');
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingJob, setEditingJob] = useState(null);
  const { toast } = useToast();

  const fetchJobs = async () => {
    try {
      setLoading(true);
      const data = await getJobs();
      setJobs(data || []);
    } catch (err) {
      toast({ title: 'Error loading jobs', description: err.message, variant: 'destructive' });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchJobs(); }, []);

  const filteredJobs = filter === 'All'
    ? jobs
    : jobs.filter(j => j.status === filter || (filter === 'Drafts' && j.status === 'Draft'));

  const handleSave = async (formData) => {
    if (editingJob) {
      await updateJob(editingJob.id, formData);
      toast({ title: 'Job updated', description: `"${formData.title}" has been updated.` });
    } else {
      await createJob(formData);
      toast({ title: 'Job created', description: `"${formData.title}" is now live.` });
    }
    setIsModalOpen(false);
    setEditingJob(null);
    fetchJobs();
  };

  const handleDelete = async (id) => {
    try {
      await deleteJob(id);
      setJobs(prev => prev.filter(j => j.id !== id));
      toast({ title: 'Job deleted' });
    } catch (err) {
      toast({ title: 'Error deleting job', description: err.message, variant: 'destructive' });
    }
  };

  const handleEdit = (job) => {
    setEditingJob(job);
    setIsModalOpen(true);
  };

  return (
    <div className="min-h-full md:p-8 p-4" style={{ background: C.pageGray }}>
      {/* Header */}
      <div className="mb-8">
        <p className="text-xs font-bold uppercase tracking-widest text-slate-400 mb-1">Job Postings</p>
        <div className="flex flex-col md:flex-row md:items-end justify-between gap-4">
          <div>
            <h1 className="text-2xl font-black text-slate-900 leading-tight">Manage Talent Pipeline.</h1>
            <p className="text-sm text-slate-400 mt-0.5 max-w-sm md:max-w-none">
              Organize, track, and optimize your open positions with AI-driven candidate scoring and market insights.
            </p>
          </div>
          <button
            onClick={() => { setEditingJob(null); setIsModalOpen(true); }}
            className="flex items-center justify-center gap-2 px-5 py-2.5 rounded-xl text-sm font-bold text-white shadow-sm hover:opacity-90 transition-opacity w-full md:w-auto"
            style={{ background: C.primary }}
          >
            <Plus className="h-4 w-4" /> Create New Job
          </button>
        </div>
      </div>

      {/* Filter tabs */}
      <div className="flex gap-1 border-b border-slate-200 mb-7 overflow-x-auto whitespace-nowrap pb-px no-scrollbar">
        {FILTERS.map(f => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={`px-5 py-2.5 text-sm font-semibold border-b-2 -mb-px transition-colors whitespace-nowrap
              ${filter === f ? 'border-indigo-800 text-indigo-900' : 'border-transparent text-slate-500 hover:text-slate-700'}`}
          >
            {f}
            <span className="ml-2 text-xs px-1.5 py-0.5 rounded-full font-bold"
              style={filter === f ? { background: C.primary, color: 'white' } : { background: '#f1f5f9', color: '#64748b' }}>
              {f === 'All' ? jobs.length
                : f === 'Drafts' ? jobs.filter(j => j.status === 'Draft').length
                : jobs.filter(j => j.status === f).length}
            </span>
          </button>
        ))}
      </div>

      {/* Cards grid */}
      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-5">
          {[1, 2, 3].map(i => (
            <div key={i} className="bg-white rounded-2xl border border-slate-200 h-52 animate-pulse" />
          ))}
        </div>
      ) : filteredJobs.length === 0 ? (
        <div className="text-center py-20">
          <p className="text-slate-400 text-sm">No jobs found. Create your first job posting.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-5">
          {filteredJobs.map(job => (
            <JobCard
              key={job.id}
              job={job}
              onEdit={handleEdit}
              onViewCandidates={onViewCandidates}
              onDelete={handleDelete}
            />
          ))}
          {/* Smart Tip card at the end */}
          <SmartTip />
        </div>
      )}

      {/* Job modal */}
      <JobModal
        isOpen={isModalOpen}
        onClose={() => { setIsModalOpen(false); setEditingJob(null); }}
        job={editingJob}
        onSave={handleSave}
      />
    </div>
  );
};

export default JobPostings;