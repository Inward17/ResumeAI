import React, { useState, useEffect, useCallback } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import {
  Plus, MoreHorizontal, Eye, Pencil, Trash2, Archive, RotateCcw, MapPin, Clock, Users, Briefcase, Search,
} from 'lucide-react';
import { getJobs, createJob, updateJob, deleteJob } from '../services/jobService';
import JobModal from './JobModal';
import { ConfirmDialog } from './Modal';
import { useToast } from '../hooks/use-toast';
import {
  Card, PageContainer, PageHeader, JobStatusPill, EmptyState, Button, IconButton, Menu, Segmented, SearchInput, Tag, Skeleton, RelativeDate,
} from './common';

const FILTERS = [
  { id: 'All', label: 'All' },
  { id: 'Active', label: 'Active' },
  { id: 'Draft', label: 'Drafts' },
  { id: 'Closed', label: 'Closed' },
];

const JobCard = ({ job, onEdit, onToggleClosed, onDelete }) => {
  const navigate = useNavigate();
  const isClosed = job.status === 'Closed';
  return (
    <Card className="group relative flex flex-col p-5 transition-colors hover:border-line-strong">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="font-serif text-[1.45rem] leading-tight text-ink">
            {/* Stretched link: the whole card opens the pipeline */}
            <Link to={`/jobs/${job.id}`} className="outline-none after:absolute after:inset-0 after:rounded-lg focus-visible:after:ring-2 focus-visible:after:ring-primary/60">
              {job.title}
            </Link>
          </h3>
          <p className="mt-0.5 truncate text-sm text-ink-3">{job.department || 'No department'}</p>
        </div>
        <div className="relative z-10 -mr-1.5 -mt-1 flex items-center gap-1">
          <JobStatusPill status={job.status} />
          <Menu
            label={`Actions for ${job.title}`}
            trigger={<IconButton label={`Actions for ${job.title}`}><MoreHorizontal aria-hidden="true" /></IconButton>}
            items={[
              { label: 'View candidates', Icon: Eye, onSelect: () => navigate(`/jobs/${job.id}`) },
              { label: 'Edit job', Icon: Pencil, onSelect: () => onEdit(job) },
              { label: isClosed ? 'Reopen job' : 'Close job', Icon: isClosed ? RotateCcw : Archive, onSelect: () => onToggleClosed(job) },
              { separator: true },
              { label: 'Delete job', Icon: Trash2, danger: true, onSelect: () => onDelete(job) },
            ]}
          />
        </div>
      </div>

      <p className="mt-3 line-clamp-2 text-sm leading-relaxed text-ink-2">{job.description}</p>

      {job.requirements?.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {job.requirements.slice(0, 4).map((skill) => <Tag key={skill}>{skill}</Tag>)}
          {job.requirements.length > 4 && <Tag className="text-ink-3">+{job.requirements.length - 4}</Tag>}
        </div>
      )}

      <div className="min-h-4 flex-1" />
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 border-t border-line pt-3 text-xs text-ink-3">
        <span className="flex items-center gap-1.5 font-medium text-ink-2">
          <Users className="h-3.5 w-3.5" aria-hidden="true" />{job.totalCandidates} candidate{job.totalCandidates === 1 ? '' : 's'}
        </span>
        {job.location && <span className="flex min-w-0 items-center gap-1.5"><MapPin className="h-3.5 w-3.5 shrink-0" aria-hidden="true" /><span className="truncate">{job.location}</span></span>}
        {job.employmentType && <span className="flex items-center gap-1.5"><Clock className="h-3.5 w-3.5" aria-hidden="true" />{job.employmentType}</span>}
        <span className="ml-auto"><RelativeDate value={job.postedAt} /></span>
      </div>
    </Card>
  );
};

const JobPostings = () => {
  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('All');
  const [query, setQuery] = useState('');
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingJob, setEditingJob] = useState(null);
  const [deleting, setDeleting] = useState(null);
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

  const q = query.trim().toLowerCase();
  const filteredJobs = jobs.filter((j) => (filter === 'All' || j.status === filter)
    && (!q || [j.title, j.department, j.location, ...(j.requirements || [])].some((v) => v && v.toLowerCase().includes(q))));
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

  const handleDelete = async () => {
    const job = deleting;
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
        title="Jobs"
        description="Create roles, upload resumes to them and review AI-ranked candidates."
        action={<Button onClick={openCreate}><Plus aria-hidden="true" /> New job</Button>}
      />

      {jobs.length > 0 && (
        <div className="mb-5 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <Segmented label="Filter jobs by status" value={filter} onChange={setFilter}
            items={FILTERS.map((f) => ({ ...f, count: count(f.id) }))} />
          <SearchInput value={query} onChange={setQuery} placeholder="Search jobs or skills" className="sm:w-64" />
        </div>
      )}

      {loading ? (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
          {[1, 2, 3].map((i) => <Skeleton key={i} className="h-48 rounded-lg" />)}
        </div>
      ) : filteredJobs.length === 0 ? (
        <Card>
          {jobs.length === 0 ? (
            <EmptyState icon={Briefcase} title="No jobs yet"
              description="Create your first job to start screening candidates."
              action={<Button onClick={openCreate}><Plus aria-hidden="true" /> New job</Button>} />
          ) : (
            <EmptyState icon={Search} title="No jobs match"
              description="Try another filter or search term."
              action={<Button variant="secondary" onClick={() => { setFilter('All'); setQuery(''); }}>Clear filters</Button>} />
          )}
        </Card>
      ) : (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
          {filteredJobs.map((job) => (
            <JobCard
              key={job.id}
              job={job}
              onEdit={(j) => { setEditingJob(j); setIsModalOpen(true); }}
              onToggleClosed={handleToggleClosed}
              onDelete={setDeleting}
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

      <ConfirmDialog
        open={!!deleting}
        onOpenChange={(o) => !o && setDeleting(null)}
        title={`Delete "${deleting?.title}"?`}
        description="The job and its candidate pipeline will no longer be shown. This can't be undone."
        confirmLabel="Delete job"
        onConfirm={handleDelete}
      />
    </PageContainer>
  );
};

export default JobPostings;
