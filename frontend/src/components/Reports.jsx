import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { AlertTriangle, BarChart3, CheckCircle2, Download, Info } from 'lucide-react';
import { getJobs } from '../services/jobService';
import { downloadReportCsv, getReport } from '../services/reportService';
import { useToast } from '../hooks/use-toast';
import { cn } from '../lib/utils';
import {
  Button, Card, CardHeader, EmptyState, Field, Input, PageContainer, PageHeader, RelativeDate, Select, Skeleton, StatStrip,
} from './common';

const SEVERITY = {
  high: { label: 'High', cls: 'bg-danger-soft text-danger' },
  medium: { label: 'Medium', cls: 'bg-warning-soft text-warning' },
  low: { label: 'Low', cls: 'bg-subtle text-ink-2' },
};

const STUCK_OPTIONS = [3, 7, 14, 30];

const fmtDays = (v) => (v == null ? '—' : `${Number(v).toLocaleString('en-US', { maximumFractionDigits: 1 })} d`);
const fmtPct = (v) => (v == null ? '—' : `${Number(v).toLocaleString('en-US', { maximumFractionDigits: 1 })}%`);

/** Where a pain point leads: the job's pipeline (on the stage) or a section of this page */
const linkFor = ({ jobId, status, section }) => {
  if (jobId) return `/jobs/${jobId}${status ? `?status=${encodeURIComponent(status)}` : ''}`;
  return section ? `#${section}` : null;
};

const Th = ({ children, className }) => (
  <th scope="col" className={cn('whitespace-nowrap px-4 py-2.5 text-left text-xs font-medium uppercase tracking-[0.06em] text-ink-3', className)}>{children}</th>
);
const Td = ({ children, className }) => <td className={cn('px-4 py-2.5 text-sm text-ink-2', className)}>{children}</td>;

const Table = ({ caption, head, children }) => (
  <div className="overflow-x-auto">
    <table className="w-full min-w-[32rem] border-collapse">
      <caption className="sr-only">{caption}</caption>
      <thead className="border-b border-line bg-canvas"><tr>{head}</tr></thead>
      <tbody className="divide-y divide-line">{children}</tbody>
    </table>
  </div>
);

const ExportButton = ({ report, filters, label }) => {
  const { toast } = useToast();
  const [busy, setBusy] = useState(false);
  const run = async () => {
    setBusy(true);
    try {
      await downloadReportCsv(report, filters);
    } catch (err) {
      toast({ title: 'Could not export the report', description: err.message, variant: 'destructive' });
    } finally {
      setBusy(false);
    }
  };
  return (
    <Button variant="secondary" size="sm" onClick={run} disabled={busy}>
      <Download aria-hidden="true" /> CSV<span className="sr-only"> export of {label}</span>
    </Button>
  );
};

const Section = ({ id, title, subtitle, action, children }) => (
  <Card id={id} className="scroll-mt-6 overflow-hidden">
    <CardHeader title={title} subtitle={subtitle} action={action} />
    {children}
  </Card>
);

const PainPoints = ({ items }) => (
  items.length === 0 ? (
    <EmptyState icon={CheckCircle2} title="No pain points right now" description="Nothing in these numbers needs attention." className="py-8" />
  ) : (
    <ul className="divide-y divide-line">
      {items.map((p) => {
        const href = linkFor(p.link || {});
        const sev = SEVERITY[p.severity] || SEVERITY.low;
        return (
          <li key={p.id} className="flex flex-col gap-2 px-5 py-3.5 sm:flex-row sm:items-start sm:gap-4">
            <span className={cn('inline-flex w-fit shrink-0 items-center rounded-md px-1.5 py-0.5 text-xs font-medium', sev.cls)}>
              <span className="sr-only">Severity: </span>{sev.label}
            </span>
            <div className="min-w-0 flex-1">
              <p className="text-sm font-medium text-ink">{p.title}</p>
              <p className="mt-0.5 text-sm text-ink-3">{p.suggestion}</p>
            </div>
            {href && (href.startsWith('#')
              ? <a href={href} className="shrink-0 text-sm font-medium text-primary-text hover:underline">Details</a>
              : <Link to={href} className="shrink-0 text-sm font-medium text-primary-text hover:underline">Open pipeline</Link>)}
          </li>
        );
      })}
    </ul>
  )
);

/** Bars for how many candidates reached each stage, with conversion to the next one */
const Funnel = ({ funnel }) => {
  const max = Math.max(1, ...funnel.stages.map((s) => s.reached));
  const conv = Object.fromEntries(funnel.conversions.map((c) => [c.from, c]));
  return (
    <div className="p-5">
      <ol className="space-y-3" aria-label="Candidates who reached each stage">
        {funnel.stages.map((s) => {
          const c = conv[s.stage];
          return (
            <li key={s.stage}>
              <div className="mb-1 flex flex-wrap justify-between gap-x-3 text-sm">
                <span className="text-ink-2">{s.stage}</span>
                <span className="tabular-nums text-ink">
                  <span className="font-medium">{s.reached}</span> reached
                  <span className="text-ink-3"> · {s.current} now</span>
                </span>
              </div>
              <div className="h-2 overflow-hidden rounded-full bg-subtle" aria-hidden="true">
                <div className="h-full rounded-full bg-primary" style={{ width: `${(s.reached / max) * 100}%` }} />
              </div>
              {c && (
                <p className={cn('mt-1 text-xs', c.biggestDrop ? 'font-medium text-warning' : 'text-ink-3')}>
                  {c.rate == null ? `No candidates to move on to ${c.to} yet` : `${fmtPct(c.rate)} moved on to ${c.to}`}
                  {c.biggestDrop && ' · biggest drop-off'}
                </p>
              )}
            </li>
          );
        })}
      </ol>
      <p className="mt-4 text-xs text-ink-3">{funnel.rejected} rejected. A candidate counts for every stage they reached, even if rejected later.</p>
    </div>
  );
};

const PeopleTable = ({ caption, rows, empty }) => (
  rows.length === 0 ? <p className="px-5 py-6 text-sm text-ink-3">{empty}</p> : (
    <Table caption={caption} head={<><Th>Candidate</Th><Th>Job</Th><Th>Stage</Th><Th className="text-right">Days</Th></>}>
      {rows.map((r) => (
        <tr key={`${r.jobId}-${r.candidateId}`}>
          <Td>
            <Link to={`/jobs/${r.jobId}?candidate=${encodeURIComponent(r.candidateId)}`} className="font-medium text-ink hover:text-primary-text hover:underline">{r.name}</Link>
          </Td>
          <Td>{r.jobTitle}</Td>
          <Td>{r.stage}</Td>
          <Td className="text-right tabular-nums">
            {Math.floor(r.days)}{r.partial && <span title="Estimated from older data" className="text-ink-3">*</span>}
          </Td>
        </tr>
      ))}
    </Table>
  )
);

const Meter = ({ label, value, sub }) => (
  <div>
    <div className="mb-1 flex justify-between gap-3 text-sm">
      <span className="text-ink-2">{label}</span>
      <span className="font-medium tabular-nums text-ink">{fmtPct(value)}</span>
    </div>
    <div className="h-1.5 overflow-hidden rounded-full bg-subtle" aria-hidden="true">
      <div className="h-full rounded-full bg-warning" style={{ width: `${Math.min(100, value || 0)}%` }} />
    </div>
    {sub && <p className="mt-1 text-xs text-ink-3">{sub}</p>}
  </div>
);

const Reports = () => {
  const { toast } = useToast();
  const [jobs, setJobs] = useState([]);
  const [filters, setFilters] = useState({ jobId: '', from: '', to: '', stuckDays: 7 });
  const [report, setReport] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getJobs().then((data) => setJobs(data || [])).catch(() => {});
  }, []);

  useEffect(() => {
    let live = true;
    setLoading(true);
    getReport(filters)
      .then((data) => { if (live) { setReport(data); setError(null); } })
      .catch((err) => {
        if (!live) return;
        setError(err.message);
        toast({ title: 'Could not load reports', description: err.message, variant: 'destructive' });
      })
      .finally(() => live && setLoading(false));
    return () => { live = false; };
  }, [filters, toast]);

  const set = (key) => (e) => setFilters((f) => ({ ...f, [key]: e.target.value }));
  const r = report;
  const noData = r && r.totals.candidates === 0;

  return (
    <PageContainer>
      <PageHeader title="Reports" description="Where hiring slows down, with numbers you can act on." />

      <Card className="mb-6 grid grid-cols-1 gap-4 p-4 sm:grid-cols-2 lg:grid-cols-4">
        <Field label="Job" htmlFor="report-job">
          <Select id="report-job" value={filters.jobId} onChange={set('jobId')}>
            <option value="">All jobs</option>
            {jobs.map((j) => <option key={j.id} value={j.id}>{j.title}</option>)}
          </Select>
        </Field>
        <Field label="Applied from" htmlFor="report-from">
          <Input id="report-from" type="date" value={filters.from} max={filters.to || undefined} onChange={set('from')} />
        </Field>
        <Field label="Applied to" htmlFor="report-to">
          <Input id="report-to" type="date" value={filters.to} min={filters.from || undefined} onChange={set('to')} />
        </Field>
        <Field label="Stuck after" htmlFor="report-stuck">
          <Select id="report-stuck" value={filters.stuckDays} onChange={set('stuckDays')}>
            {STUCK_OPTIONS.map((d) => <option key={d} value={d}>{d} days in a stage</option>)}
          </Select>
        </Field>
      </Card>

      {error && !r ? (
        <Card><EmptyState icon={AlertTriangle} title="Reports are unavailable" description={error} /></Card>
      ) : !r ? (
        <div className="space-y-6" aria-busy="true">{[1, 2, 3].map((i) => <Skeleton key={i} className="h-40" />)}</div>
      ) : (
        <div className={cn('space-y-6 transition-opacity', loading && 'opacity-60')} aria-busy={loading}>
          {(r.partialData || r.truncated) && (
            <p className="flex items-start gap-2 rounded-lg bg-info-soft px-3 py-2 text-sm text-info" role="note">
              <Info className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
              <span>
                {r.partialData && `Partial data: ${r.partialCount} candidate${r.partialCount === 1 ? '' : 's'} predate status tracking, so their time in stage is estimated from the last update (marked *) and left out of stage timings. `}
                {r.truncated && 'Only the most recent candidates are included; narrow the filters for exact numbers.'}
              </span>
            </p>
          )}

          <Section id="pain-points" title="Pain points" subtitle="Most severe first">
            <PainPoints items={r.painPoints} />
          </Section>

          {noData ? (
            <Card><EmptyState icon={BarChart3} title="No candidates in this range" description="Upload resumes or widen the filters to see the funnel and timings." /></Card>
          ) : (
            <>
              <StatStrip items={[
                { label: 'Candidates', value: r.totals.candidates, sub: `Across ${r.totals.jobs} job${r.totals.jobs === 1 ? '' : 's'}` },
                { label: 'Stuck', value: r.stuck.count, sub: `Over ${r.stuck.thresholdDays} days in a stage` },
                { label: 'Feedback overdue', value: r.overdueFeedback.count, sub: `Interview, no evaluation after ${r.overdueFeedback.days} days` },
                { label: 'Time to shortlist', value: fmtDays(r.milestones.shortlist.medianDays), sub: 'Median, from application' },
              ]} />

              <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
                <Section id="funnel" title="Funnel" subtitle="Stage to stage conversion" action={<ExportButton report="funnel" filters={filters} label="funnel" />}>
                  <Funnel funnel={r.funnel} />
                </Section>

                <Section id="timing" title="Time in stage" subtitle="Days, from candidates who left the stage">
                  <Table caption="Median and 90th percentile days spent in each stage" head={<><Th>Stage</Th><Th className="text-right">Median</Th><Th className="text-right">90th pct</Th><Th className="text-right">Measured</Th></>}>
                    {r.timeInStage.map((s) => (
                      <tr key={s.stage}>
                        <Td>{s.stage}</Td>
                        <Td className="text-right tabular-nums">{fmtDays(s.medianDays)}</Td>
                        <Td className="text-right tabular-nums">{fmtDays(s.p90Days)}</Td>
                        <Td className="text-right tabular-nums">{s.count}</Td>
                      </tr>
                    ))}
                  </Table>
                  <dl className="grid grid-cols-3 gap-px border-t border-line bg-line text-center">
                    {[['First review', r.milestones.firstReview], ['Shortlist', r.milestones.shortlist], ['Hire', r.milestones.hire]].map(([label, m]) => (
                      <div key={label} className="bg-surface px-2 py-3">
                        <dt className="text-xs text-ink-3">Time to {label.toLowerCase()}</dt>
                        <dd className="mt-1 text-sm font-medium tabular-nums text-ink">{fmtDays(m.medianDays)}</dd>
                      </div>
                    ))}
                  </dl>
                </Section>
              </div>

              <Section id="stuck" title="Stuck candidates" subtitle={`In a stage for over ${r.stuck.thresholdDays} days, longest first`}
                action={<ExportButton report="stuck" filters={filters} label="stuck candidates" />}>
                <PeopleTable caption="Stuck candidates" rows={r.stuck.candidates} empty="Nobody is stuck. Candidates are moving through every stage." />
              </Section>

              <Section id="feedback" title="Overdue interview feedback" subtitle={`At Interview for over ${r.overdueFeedback.days} days with no evaluation`}>
                <PeopleTable caption="Candidates waiting for interview feedback" rows={r.overdueFeedback.candidates} empty="Every interview has feedback." />
              </Section>

              <Section id="screening" title="Screening quality">
                <div className="grid grid-cols-1 gap-6 p-5 md:grid-cols-2">
                  <div className="space-y-4">
                    <Meter label="Low credibility (under 60)" value={r.screening.lowCredibilityPct}
                      sub={r.screening.scored ? `${r.screening.lowCredibility} of ${r.screening.scored} verified candidates` : 'No verified candidates yet'} />
                    <Meter label="Verification red flags" value={r.screening.redFlagsPct}
                      sub={`${r.screening.redFlags} of ${r.screening.candidates} candidates`} />
                    <Meter label="Resume uploads failed" value={r.screening.tasksFailedPct}
                      sub={r.screening.tasksTotal ? `${r.screening.tasksFailed} of ${r.screening.tasksTotal} uploads, ${r.screening.verificationFailures} in verification` : 'No uploads in this range'} />
                  </div>
                  <div>
                    <h3 className="mb-2 text-xs font-medium uppercase tracking-[0.06em] text-ink-3">Failure reasons</h3>
                    {r.screening.failureReasons.length === 0 ? <p className="text-sm text-ink-3">No failed uploads.</p> : (
                      <ul className="divide-y divide-line text-sm">
                        {r.screening.failureReasons.map((f) => (
                          <li key={f.reason} className="flex justify-between gap-3 py-1.5">
                            <span className="text-ink-2">{f.reason}</span><span className="font-medium tabular-nums text-ink">{f.count}</span>
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                </div>
              </Section>
            </>
          )}

          <Section id="jobs" title="Job health" subtitle="Jobs with the most stuck candidates and overdue feedback first"
            action={<ExportButton report="jobs" filters={filters} label="job health" />}>
            {r.jobs.length === 0 ? <p className="px-5 py-6 text-sm text-ink-3">No jobs yet.</p> : (
              <Table caption="Job health" head={<><Th>Job</Th><Th className="text-right">Open</Th><Th className="text-right">Candidates</Th><Th className="text-right">Shortlisted</Th><Th className="text-right">Stuck</Th><Th className="text-right">Feedback due</Th><Th>Last activity</Th></>}>
                {r.jobs.map((j) => (
                  <tr key={j.jobId}>
                    <Td>
                      <Link to={`/jobs/${j.jobId}`} className="font-medium text-ink hover:text-primary-text hover:underline">{j.title}</Link>
                      <span className="block text-xs text-ink-3">
                        {j.status}
                        {j.noNewCandidates && <span className="text-warning"> · no new candidates in 14 days</span>}
                      </span>
                    </Td>
                    <Td className="text-right tabular-nums">{j.openDays == null ? '—' : `${j.openDays} d`}</Td>
                    <Td className="text-right tabular-nums">{j.candidates}</Td>
                    <Td className="text-right tabular-nums">{fmtPct(j.shortlistedPct)}</Td>
                    <Td className={cn('text-right tabular-nums', j.stuck > 0 && 'font-medium text-warning')}>{j.stuck}</Td>
                    <Td className={cn('text-right tabular-nums', j.overdueFeedback > 0 && 'font-medium text-warning')}>{j.overdueFeedback}</Td>
                    <Td><RelativeDate value={j.lastActivity} /></Td>
                  </tr>
                ))}
              </Table>
            )}
          </Section>

          <Section id="ai-usage" title="AI usage today" subtitle="Workspace daily limits reset at 00:00 UTC"
            action={<Link to="/settings?tab=ai" className="text-sm font-medium text-primary-text hover:underline">Details</Link>}>
            <div className="grid grid-cols-1 gap-4 p-5 sm:grid-cols-2">
              {Object.entries(r.aiUsage || {}).map(([kind, u]) => (
                <div key={kind}>
                  <div className="mb-1 flex justify-between gap-3 text-sm">
                    <span className="capitalize text-ink-2">{u.label}</span>
                    <span className="tabular-nums text-ink"><span className="font-medium">{u.used}</span> of {u.limit}</span>
                  </div>
                  <div className="h-1.5 overflow-hidden rounded-full bg-subtle" aria-hidden="true">
                    <div className={cn('h-full rounded-full', u.used >= u.limit ? 'bg-danger' : u.used >= 0.8 * u.limit ? 'bg-warning' : 'bg-primary')}
                      style={{ width: `${Math.min(100, u.limit ? (u.used / u.limit) * 100 : 0)}%` }} />
                  </div>
                </div>
              ))}
            </div>
          </Section>
        </div>
      )}
    </PageContainer>
  );
};

export default Reports;
