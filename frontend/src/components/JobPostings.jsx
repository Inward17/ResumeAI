import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import {
  Plus, MoreVertical, Eye, Edit, Trash2, Archive, RotateCcw, MapPin, Clock, Users, ArrowUpRight, Briefcase,
} from 'lucide-react';
import { getJobs, createJob, updateJob, deleteJob } from '../services/jobService';
import JobModal from './JobModal';
import { useToast } from '../hooks/use-toast';
import { cn } from '../lib/utils';
import { Card, PageContainer, PageHeader, JobStatusPill, EmptyState, PrimaryButton, formatDate } from './common';

const FILTERS = [
  { id: 'All', label: 'All' },
  { id: 'Active', label: 'Active' },
  { id: 'Draft', label: 'Drafts' },
  { id: 'Closed', label: 'Closed' },
];

const ActionMenu = ({ job, onEdit, onToggleClosed, onDelete }) => {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  const navigate = useNavigate();

  useEffect(() => {
    if (!open) return undefined;
    const close = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    const onKey = (e) => { if (e.key === 'Escape') setOpen(false); };
    document.addEventListener('mousedown', close);
    document.addEventListener('keydown', onKey);
    return () => { document.removeEventListener('mousedown', close); document.removeEventListener('keydown', onKey); };
  }, [open]);

  const item = 'flex w-full items-center gap-3 px-4 py-2.5 text-sm transition-colors';
  const isClosed = job.status === 'Closed';
  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-label={`Actions for ${job.title}`}
        aria-haspopup="menu"
        aria-expanded={open}
        className="rounded-lg p-1.5 text-slate-500 transition-colors hover:bg-slate-100 hover:text-slate-800"
      >
        <MoreVertical className="h-5 w-5" aria-hidden="true" />
      </button>
      {open && (
        <div role="menu" className="absolute right-0 top-9 z-20 w-48 rounded-xl border border-slate-200 bg-white py-1.5 shadow-xl">
          <button role="menuitem" type="button" className={cn(item, 'text-slate-700 hover:bg-slate-50')} onClick={() => navigate(`/jobs/${job.id}`)}>
            <Eye className="h-4 w-4 text-slate-500" aria-hidden="true" /> View candidates
          </button>
          <button role="menuitem" type="button" className={cn(item, 'text-slate-700 hover:bg-slate-50')} onClick={() => { setOpen(false); onEdit(job); }}>
            <Edit className="h-4 w-4 text-slate-500" aria-hidden="true" /> Edit job
          </button>
          <button role="menuitem" type="button" className={cn(item, 'text-slate-700 hover:bg-slate-50')} onClick={() => { setOpen(false); onToggleClosed(job); }}>
            {isClosed
              ? <><RotateCcw className="h-4 w-4 text-slate-500" aria-hidden="true" /> Reopen job</>
              : <><Archive className="h-4 w-4 text-slate-500" aria-hidden="true" /> Close job</>}
          </button>
          <div className="my-1 border-t border-slate-100" />
          <button role="menuitem" type="button" className={cn(item, 'text-red-700 hover:bg-red-50')} onClick={() => { setOpen(false); onDelete(job); }}>
            <Trash2 className="h-4 w-4" aria-hidden="true" /> Delete
          </button>
        </div>
      )}
    </div>
  );
};

const JobCard = ({ job, ...handlers }) => (
  <Card className="flex flex-col gap-4 p-5 transition-shadow hover:shadow-md">
    <div className="flex items-start justify-between gap-2">
      <div className="min-w-0 flex-1">
        <JobStatusPill status={job.status} />
        <h3 className="mt-2 text-base font-bold leading-tight text-slate-900">
          <Link to={`/jobs/${job.id}`} className="hover:text-brand-accent">{job.title}</Link>
        </h3>
        {job.department && <p className="mt-0.5 text-xs font-semibold text-slate-500">{job.department}</p>}
        <p className="mt-1.5 line-clamp-2 text-sm text-slate-600">{job.description}</p>
      </div>
      <ActionMenu job={job} {...handlers} />
    </div>

    <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-600">
      {job.location && <span className="flex items-center gap-1"><MapPin className="h-3.5 w-3.5" aria-hidden="true" />{job.location}</span>}
      {job.employmentType && <span className="flex items-center gap-1"><Clock className="h-3.5 w-3.5" aria-hidden="true" />{job.employmentType}</span>}
      <span className="flex items-center gap-1"><Users className="h-3.5 w-3.5" aria-hidden="true" />{job.totalCandidates} candidates</span>
    </div>

    {job.requirements?.length > 0 && (
      <div className="flex flex-wrap gap-1.5">
        {job.requirements.slice(0, 4).map((skill) => (
          <span key={skill} className="rounded-full bg-brand-light px-2 py-0.5 text-[11px] font-semibold text-brand">{skill}</span>
        ))}
        {job.requirements.length > 4 && (
          <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[11px] font-semibold text-slate-600">+{job.requirements.length - 4}</span>
        )}
      </div>
    )}

    <div className="mt-auto flex items-center justify-between border-t border-slate-100 pt-3">
      <span className="text-xs text-slate-500">Posted {formatDate(job.postedAt)}</span>
      <Link to={`/jobs/${job.id}`} className="flex items-center gap-1 text-xs font-bold text-brand-accent hover:underline">
        View pipeline <ArrowUpRight className="h-3.5 w-3.5" aria-hidden="true" />
      </Link>
    </div>
  </Card>
);

const JobPostings = () => {
  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('All');
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingJob, setEditingJob] = useState(null);
  const [searchParams, setSearchParams] = useSearchParams();
  const { toast } = useToast();

  const fetchJobs = useCallback(async () => {
    try {
      setLoading(true);
      setJobs(await getJobs());
    } catch (err) {
      toast({ title: 'Could not load jobs', description: err.message, variant: 'destructive' });
    } finally {
      setLoading(false);
    }
  }, [toast]);

  useEffect(() => { fetchJobs(); }, [fetchJobs]);

  // /jobs?new=1 (e.g. from the dashboard) opens the create form
  useEffect(() => {
    if (searchParams.get('new') === '1') {
      setEditingJob(null);
      setIsModalOpen(true);
      setSearchParams({}, { replace: true });
    }
  }, [searchParams, setSearchParams]);

  const filteredJobs = filter === 'All' ? jobs : jobs.filter((j) => j.status === filter);
  const count = (id) => (id === 'All' ? jobs.length : jobs.filter((j) => j.status === id).length);

  // Errors propagate so the form can show them
  const handleSave = async (formData) => {
    if (editingJob) {
      await updateJob(editingJob.id, formData);
      toast({ title: 'Job updated', description: `"${formData.title}" was saved.` });
    } else {
      await createJob(formData);
      toast({
        title: formData.status === 'Draft' ? 'Draft saved' : 'Job created',
        description: `"${formData.title}" ${formData.status === 'Active' ? 'is now open for candidates' : `was saved as ${formData.status.toLowerCase()}`}.`,
      });
    }
    setIsModalOpen(false);
    setEditingJob(null);
    fetchJobs();
  };

  const handleToggleClosed = async (job) => {
    const status = job.status === 'Closed' ? 'Active' : 'Closed';
    try {
      const updated = await updateJob(job.id, { ...job, status });
      setJobs((prev) => prev.map((j) => (j.id === job.id ? { ...j, ...updated } : j)));
      toast({ title: status === 'Closed' ? 'Job closed' : 'Job reopened', description: job.title });
    } catch (err) {
      toast({ title: 'Could not update job', description: err.message, variant: 'destructive' });
    }
  };

  const handleDelete = async (job) => {
    if (!window.confirm(`Delete "${job.title}"? Its candidate pipeline will no longer be shown.`)) return;
    try {
      await deleteJob(job.id);
      setJobs((prev) => prev.filter((j) => j.id !== job.id));
      toast({ title: 'Job deleted', description: job.title });
    } catch (err) {
      toast({ title: 'Could not delete job', description: err.message, variant: 'destructive' });
    }
  };

  const openCreate = () => { setEditingJob(null); setIsModalOpen(true); };

  return (
    <PageContainer>
      <PageHeader
        eyebrow="Job postings"
        title="Manage your open roles"
        description="Create roles, upload resumes to them and review AI-ranked candidates."
        action={<PrimaryButton onClick={openCreate} className="w-full md:w-auto"><Plus className="h-4 w-4" aria-hidden="true" /> New job posting</PrimaryButton>}
      />

      <div className="no-scrollbar mb-6 flex gap-1 overflow-x-auto border-b border-slate-200" role="tablist" aria-label="Filter jobs">
        {FILTERS.map(({ id, label }) => (
          <button
            key={id}
            type="button"
            role="tab"
            aria-selected={filter === id}
            onClick={() => setFilter(id)}
            className={cn(
              '-mb-px whitespace-nowrap border-b-2 px-4 py-2.5 text-sm font-semibold transition-colors',
              filter === id ? 'border-brand text-brand' : 'border-transparent text-slate-600 hover:text-slate-900',
            )}
          >
            {label}
            <span className={cn('ml-2 rounded-full px-1.5 py-0.5 text-xs font-bold', filter === id ? 'bg-brand text-white' : 'bg-slate-100 text-slate-600')}>
              {count(id)}
            </span>
          </button>
        ))}
      </div>

      {loading ? (
        <div className="grid grid-cols-1 gap-5 md:grid-cols-2 xl:grid-cols-3">
          {[1, 2, 3].map((i) => <div key={i} className="h-56 animate-pulse rounded-2xl border border-slate-200 bg-white" />)}
        </div>
      ) : filteredJobs.length === 0 ? (
        <Card>
          <EmptyState
            icon={Briefcase}
            title={jobs.length === 0 ? 'No job postings yet' : `No ${FILTERS.find((f) => f.id === filter).label.toLowerCase()} jobs`}
            description={jobs.length === 0 ? 'Create your first job posting to start screening candidates.' : 'Try another filter.'}
            action={jobs.length === 0 && <PrimaryButton onClick={openCreate}><Plus className="h-4 w-4" aria-hidden="true" /> New job posting</PrimaryButton>}
          />
        </Card>
      ) : (
        <div className="grid grid-cols-1 gap-5 md:grid-cols-2 xl:grid-cols-3">
          {filteredJobs.map((job) => (
            <JobCard
              key={job.id}
              job={job}
              onEdit={(j) => { setEditingJob(j); setIsModalOpen(true); }}
              onToggleClosed={handleToggleClosed}
              onDelete={handleDelete}
            />
          ))}
        </div>
      )}

      <JobModal
        isOpen={isModalOpen}
        onClose={() => { setIsModalOpen(false); setEditingJob(null); }}
        job={editingJob}
        onSave={handleSave}
      />
    </PageContainer>
  );
};

export default JobPostings;
