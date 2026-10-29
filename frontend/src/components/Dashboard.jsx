import React, { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Briefcase, Users, Zap, CheckCircle, Plus, ArrowRight, BarChart2 } from 'lucide-react';
import { getJobs } from '../services/jobService';
import { useToast } from '../hooks/use-toast';
import {
  Card, CardHeader, PageContainer, PageHeader, JobStatusPill, EmptyState, PrimaryButton, formatDate,
} from './common';

const StatCard = ({ label, value, sub, Icon, hero = false, loading }) => (
  <Card className={hero ? 'border-0 bg-brand-gradient p-5 text-white' : 'p-5'}>
    <div className="mb-3 flex items-center justify-between">
      <p className={`text-xs font-bold uppercase tracking-wider ${hero ? 'text-indigo-200' : 'text-slate-500'}`}>{label}</p>
      {Icon && <Icon className={`h-4 w-4 ${hero ? 'text-brand-cyan' : 'text-brand-accent'}`} aria-hidden="true" />}
    </div>
    <p className={`font-display text-3xl font-extrabold md:text-4xl ${hero ? 'text-white' : 'text-slate-900'}`}>
      {loading ? <span className="inline-block h-9 w-14 animate-pulse rounded-lg bg-current opacity-10" /> : value}
    </p>
    {sub && <p className={`mt-1 text-xs ${hero ? 'text-indigo-100' : 'text-slate-500'}`}>{sub}</p>}
  </Card>
);

const Dashboard = () => {
  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(true);
  const { toast } = useToast();
  const navigate = useNavigate();

  useEffect(() => {
    getJobs()
      .then((data) => setJobs(data || []))
      .catch((err) => toast({ title: 'Could not load jobs', description: err.message, variant: 'destructive' }))
      .finally(() => setLoading(false));
  }, [toast]);

  const activeJobs = jobs.filter((j) => j.status === 'Active');
  const totalCandidates = jobs.reduce((sum, j) => sum + (j.totalCandidates || 0), 0);
  const totalShortlisted = jobs.reduce((sum, j) => sum + (j.shortlisted || 0), 0);
  const recentJobs = jobs.slice(0, 5);
  const byVolume = [...jobs].filter((j) => j.totalCandidates > 0)
    .sort((a, b) => b.totalCandidates - a.totalCandidates).slice(0, 6);
  const maxVolume = Math.max(1, ...byVolume.map((j) => j.totalCandidates));
  const shortlistRate = totalCandidates ? Math.round((totalShortlisted / totalCandidates) * 100) : 0;

  const createJob = (
    <PrimaryButton onClick={() => navigate('/jobs?new=1')}>
      <Plus className="h-4 w-4" aria-hidden="true" /> New job posting
    </PrimaryButton>
  );

  return (
    <PageContainer>
      <PageHeader
        eyebrow="Overview"
        title="Recruitment dashboard"
        description="Your open roles and how candidates are moving through screening."
        action={createJob}
      />

      <div className="mb-6 grid grid-cols-2 gap-3 md:mb-8 md:grid-cols-4 md:gap-4">
        <StatCard hero label="Candidates" value={totalCandidates} Icon={Users} loading={loading}
          sub={`Screened across ${jobs.length} job${jobs.length === 1 ? '' : 's'}`} />
        <StatCard label="Job postings" value={jobs.length} Icon={Briefcase} loading={loading} />
        <StatCard label="Active jobs" value={activeJobs.length} Icon={Zap} loading={loading} />
        <StatCard label="Shortlisted" value={totalShortlisted} Icon={CheckCircle} loading={loading}
          sub={totalCandidates ? `${shortlistRate}% of candidates` : undefined} />
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1fr_320px]">
        {/* Recent job postings */}
        <Card className="overflow-hidden">
          <CardHeader
            title="Recent job postings"
            subtitle="Newest first"
            action={jobs.length > 0 && (
              <Link to="/jobs" className="inline-flex items-center gap-1 text-sm font-semibold text-brand-accent hover:underline">
                View all <ArrowRight className="h-3.5 w-3.5" aria-hidden="true" />
              </Link>
            )}
          />
          {loading ? (
            <div className="space-y-3 p-6">
              {[1, 2, 3].map((i) => <div key={i} className="h-12 animate-pulse rounded-xl bg-slate-100" />)}
            </div>
          ) : recentJobs.length === 0 ? (
            <EmptyState
              icon={Briefcase}
              title="No job postings yet"
              description="Create a job posting, then upload resumes to it. ResumeAI parses, verifies and ranks every candidate."
              action={createJob}
            />
          ) : (
            <>
              <table className="hidden min-w-full md:table">
                <thead className="bg-slate-50">
                  <tr>
                    {['Job title', 'Status', 'Candidates', 'Created'].map((h, i) => (
                      <th key={h} scope="col" className={`px-6 py-3 text-xs font-bold uppercase tracking-wider text-slate-500 ${i ? 'text-center' : 'text-left'}`}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {recentJobs.map((job) => (
                    <tr key={job.id} className="cursor-pointer transition-colors hover:bg-slate-50" onClick={() => navigate(`/jobs/${job.id}`)}>
                      <td className="px-6 py-4">
                        <Link to={`/jobs/${job.id}`} className="text-sm font-semibold text-slate-900 hover:text-brand-accent" onClick={(e) => e.stopPropagation()}>
                          {job.title}
                        </Link>
                        <p className="mt-0.5 text-xs text-slate-500">{[job.location, job.employmentType].filter(Boolean).join(' · ') || '—'}</p>
                      </td>
                      <td className="px-6 py-4 text-center"><JobStatusPill status={job.status} /></td>
                      <td className="px-6 py-4 text-center text-sm font-semibold text-slate-700">{job.totalCandidates}</td>
                      <td className="px-6 py-4 text-center text-xs text-slate-500">{formatDate(job.postedAt)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <ul className="divide-y divide-slate-100 md:hidden">
                {recentJobs.map((job) => (
                  <li key={job.id}>
                    <Link to={`/jobs/${job.id}`} className="flex flex-col gap-2 p-4 hover:bg-slate-50">
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0">
                          <p className="truncate text-sm font-semibold text-slate-900">{job.title}</p>
                          <p className="mt-0.5 text-xs text-slate-500">{[job.location, job.employmentType].filter(Boolean).join(' · ') || '—'}</p>
                        </div>
                        <JobStatusPill status={job.status} />
                      </div>
                      <div className="flex justify-between text-xs text-slate-500">
                        <span className="flex items-center gap-1.5"><Users className="h-3.5 w-3.5" aria-hidden="true" />{job.totalCandidates} candidates</span>
                        <span>{formatDate(job.postedAt)}</span>
                      </div>
                    </Link>
                  </li>
                ))}
              </ul>
            </>
          )}
        </Card>

        {/* Candidates per job — real counts */}
        <Card className="flex flex-col">
          <CardHeader title="Candidates per job" subtitle="Jobs with the most applicants" />
          <div className="flex-1 p-5">
            {loading ? (
              <div className="space-y-4">{[1, 2, 3].map((i) => <div key={i} className="h-8 animate-pulse rounded-lg bg-slate-100" />)}</div>
            ) : byVolume.length === 0 ? (
              <EmptyState icon={BarChart2} title="No candidates yet" description="Upload resumes to a job to see volumes here." className="py-8" />
            ) : (
              <ul className="space-y-4">
                {byVolume.map((job) => (
                  <li key={job.id}>
                    <div className="mb-1 flex justify-between gap-3 text-xs">
                      <Link to={`/jobs/${job.id}`} className="truncate font-semibold text-slate-700 hover:text-brand-accent">{job.title}</Link>
                      <span className="shrink-0 font-bold text-brand">{job.totalCandidates}</span>
                    </div>
                    <div className="h-2 overflow-hidden rounded-full bg-brand-light">
                      <div className="h-full rounded-full bg-brand-accent" style={{ width: `${(job.totalCandidates / maxVolume) * 100}%` }} />
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </div>
          {!loading && totalCandidates > 0 && (
            <div className="grid grid-cols-3 divide-x divide-slate-100 border-t border-slate-100 text-center">
              {[
                ['Total', totalCandidates],
                ['Screened', jobs.reduce((s, j) => s + (j.screened || 0), 0)],
                ['Shortlisted', totalShortlisted],
              ].map(([label, value]) => (
                <div key={label} className="px-2 py-3">
                  <p className="font-display text-lg font-extrabold text-slate-900">{value}</p>
                  <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">{label}</p>
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>
    </PageContainer>
  );
};

export default Dashboard;
