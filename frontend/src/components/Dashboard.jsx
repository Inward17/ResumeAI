import React, { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Briefcase, Plus, ArrowRight, BarChart3, Upload, ListChecks } from 'lucide-react';
import { getJobs } from '../services/jobService';
import { useToast } from '../hooks/use-toast';
import {
  Card, CardHeader, PageContainer, PageHeader, JobStatusPill, EmptyState, Button, StatStrip, Skeleton, RelativeDate,
} from './common';

const GETTING_STARTED = [
  { Icon: Briefcase, title: 'Create a job', body: 'Paste the description and the skills that matter.' },
  { Icon: Upload, title: 'Upload resumes', body: 'Drop in PDFs, DOCX or TXT — large batches are fine.' },
  { Icon: ListChecks, title: 'Review the ranking', body: 'Candidates are scored, verified and ranked for you.' },
];

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
  const recentJobs = jobs.slice(0, 6);
  const byVolume = [...jobs].filter((j) => j.totalCandidates > 0)
    .sort((a, b) => b.totalCandidates - a.totalCandidates).slice(0, 6);
  const maxVolume = Math.max(1, ...byVolume.map((j) => j.totalCandidates));
  const shortlistRate = totalCandidates ? Math.round((totalShortlisted / totalCandidates) * 100) : null;

  const createJob = (
    <Button onClick={() => navigate('/jobs?new=1')}>
      <Plus aria-hidden="true" /> New job
    </Button>
  );

  const firstRun = !loading && jobs.length === 0;

  return (
    <PageContainer>
      <PageHeader
        title="Overview"
        description="Your open roles and how candidates are moving through screening."
        action={!firstRun && createJob}
      />

      {firstRun ? (
        <Card className="overflow-hidden">
          <div className="border-b border-line px-6 py-8 text-center md:py-10">
            <h2 className="font-serif text-3xl text-ink md:text-4xl">Screen your first candidates</h2>
            <p className="mx-auto mt-2 max-w-md text-sm text-ink-3">
              ResumeAI parses every resume, checks claims against GitHub, LinkedIn and the web, and ranks candidates against your job.
            </p>
            <div className="mt-5">{createJob}</div>
          </div>
          <ol className="grid divide-y divide-line md:grid-cols-3 md:divide-x md:divide-y-0">
            {GETTING_STARTED.map(({ Icon, title, body }, i) => (
              <li key={title} className="flex gap-3 p-5">
                <span className="w-6 shrink-0 font-serif text-2xl leading-none text-ink-3">{i + 1}</span>
                <div>
                  <p className="flex items-center gap-1.5 text-sm font-medium text-ink"><Icon className="h-4 w-4 text-ink-3" aria-hidden="true" />{title}</p>
                  <p className="mt-0.5 text-sm text-ink-3">{body}</p>
                </div>
              </li>
            ))}
          </ol>
        </Card>
      ) : (
        <>
          <div className="mb-6">
            <StatStrip loading={loading} items={[
              { label: 'Candidates', value: totalCandidates, sub: `Across ${jobs.length} job${jobs.length === 1 ? '' : 's'}` },
              { label: 'Active jobs', value: activeJobs.length,
                sub: jobs.length - activeJobs.length ? `${jobs.length - activeJobs.length} draft or closed` : 'All jobs open' },
              { label: 'Shortlisted', value: totalShortlisted },
              { label: 'Shortlist rate', value: shortlistRate == null ? '—' : `${shortlistRate}%`, sub: 'Shortlisted ÷ candidates' },
            ]} />
          </div>

          <div className="grid grid-cols-1 gap-6 xl:grid-cols-[minmax(0,1fr)_340px]">
            {/* Recent jobs */}
            <Card className="overflow-hidden">
              <CardHeader
                title="Recent jobs"
                action={jobs.length > 0 && (
                  <Link to="/jobs" className="inline-flex items-center gap-1 text-sm font-medium text-primary-text hover:underline">
                    All jobs <ArrowRight className="h-3.5 w-3.5" aria-hidden="true" />
                  </Link>
                )}
              />
              {loading ? (
                <div className="space-y-3 p-5">{[1, 2, 3].map((i) => <Skeleton key={i} className="h-10" />)}</div>
              ) : (
                <ul className="divide-y divide-line">
                  {recentJobs.map((job) => (
                    <li key={job.id}>
                      <Link to={`/jobs/${job.id}`}
                        className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-x-4 gap-y-1 px-5 py-3 transition-colors hover:bg-subtle md:grid-cols-[minmax(0,1fr)_7rem_6rem_7rem]">
                        <div className="min-w-0">
                          <p className="truncate text-sm font-medium text-ink">{job.title}</p>
                          <p className="truncate text-xs text-ink-3">{[job.department, job.location, job.employmentType].filter(Boolean).join(' · ') || 'No details'}</p>
                        </div>
                        <div className="md:order-none"><JobStatusPill status={job.status} /></div>
                        <p className="text-xs text-ink-3 md:text-right md:text-sm">
                          <span className="font-medium tabular-nums text-ink-2">{job.totalCandidates}</span> candidates
                        </p>
                        <p className="text-right text-xs text-ink-3"><RelativeDate value={job.postedAt} /></p>
                      </Link>
                    </li>
                  ))}
                </ul>
              )}
            </Card>

            {/* Candidates per job — real counts */}
            <Card className="flex flex-col">
              <CardHeader title="Candidates per job" />
              <div className="flex-1 p-5">
                {loading ? (
                  <div className="space-y-4">{[1, 2, 3].map((i) => <Skeleton key={i} className="h-7" />)}</div>
                ) : byVolume.length === 0 ? (
                  <EmptyState icon={BarChart3} title="No candidates yet" description="Upload resumes to a job to see volumes here." className="py-6" />
                ) : (
                  <ul className="space-y-3.5">
                    {byVolume.map((job) => (
                      <li key={job.id}>
                        <div className="mb-1.5 flex justify-between gap-3 text-sm">
                          <Link to={`/jobs/${job.id}`} className="truncate text-ink-2 hover:text-primary-text">{job.title}</Link>
                          <span className="shrink-0 font-medium tabular-nums text-ink">{job.totalCandidates}</span>
                        </div>
                        <div className="h-1.5 overflow-hidden rounded-full bg-subtle">
                          <div className="h-full rounded-full bg-primary" style={{ width: `${(job.totalCandidates / maxVolume) * 100}%` }} />
                        </div>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </Card>
          </div>
        </>
      )}
    </PageContainer>
  );
};

export default Dashboard;
