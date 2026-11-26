/**
 * Interview scheduling UI: the "Schedule interview" dialog (common free times, book one or send the
 * candidate a link) and the list of upcoming interviews with reschedule / cancel.
 */
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { AlertTriangle, CalendarClock, Check, Copy, ExternalLink, Loader2, Video } from 'lucide-react';
import { useToast } from '../hooks/use-toast';
import { cn } from '../lib/utils';
import Modal, { ConfirmDialog } from './Modal';
import { Card, CardHeader, Button, Field, Input, Select, Textarea, Skeleton, Tag } from './common';
import { Checkbox } from './ui/checkbox';
import {
  getTeamCalendars, findAvailability, bookInterview, createSchedulingLink, listInterviews, rescheduleInterview, cancelInterview,
} from '../services/schedulingService';

export const localZone = () => Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC';
const ZONES = (() => {
  try { return Intl.supportedValuesOf('timeZone'); } catch { return ['UTC']; }
})();
const isoDay = (d) => d.toLocaleDateString('en-CA');
const addDays = (n) => { const d = new Date(); d.setDate(d.getDate() + n); return isoDay(d); };
const fmt = (iso, tz, opts) => new Intl.DateTimeFormat(undefined, { timeZone: tz, ...opts }).format(new Date(iso));
export const formatWhen = (iso, tz) => fmt(iso, tz, { weekday: 'short', day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' });
const safeUrl = (u) => (typeof u === 'string' && u.startsWith('https://') ? u : null);

const useCopy = () => {
  const { toast } = useToast();
  const [copied, setCopied] = useState(false);
  const copy = async (text) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      toast({ title: 'Could not copy', description: 'Select the text and copy it manually.', variant: 'destructive' });
    }
  };
  return { copy, copied };
};

/** Email outcome; when it couldn't be sent, the message to copy and send yourself */
const EmailResult = ({ email }) => {
  const { copy, copied } = useCopy();
  if (!email) return null;
  if (email.sent) return <p className="text-sm text-ink-2">Email sent to {email.to}{email.via === 'composio' ? ' (from the workspace mailbox)' : ''}.</p>;
  const text = `Subject: ${email.subject}\n\n${email.body}`;
  return (
    <div className="space-y-2">
      <p className="flex items-start gap-2 text-sm text-warning">
        <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
        <span>The candidate wasn't emailed{email.error ? `: ${email.error}` : ''}. Send this yourself{email.to ? ` to ${email.to}` : ''}.</span>
      </p>
      <Textarea readOnly value={text} aria-label="Message for the candidate" className="min-h-[9rem] text-xs" />
      <Button size="sm" variant="secondary" onClick={() => copy(text)}>{copied ? <Check aria-hidden="true" /> : <Copy aria-hidden="true" />} Copy message</Button>
    </div>
  );
};

const SlackResult = ({ slack }) => (slack?.configured && slack.errors?.length
  ? <p className="text-xs text-warning">Slack: {slack.errors.join('; ')}</p> : null);

export const ScheduleDialog = ({ open, onOpenChange, job, candidate, onDone }) => {
  const { toast } = useToast();
  const [team, setTeam] = useState(null);
  const [form, setForm] = useState(() => ({
    uids: [], duration: 60, startDate: addDays(1), endDate: addDays(7), tz: localZone(),
    workStart: '09:00', workEnd: '17:00', weekends: false, locationType: 'video', locationText: '',
  }));
  const [result, setResult] = useState(null); // availability
  const [picked, setPicked] = useState([]);
  const [busy, setBusy] = useState(null);
  const [error, setError] = useState(null);
  const [done, setDone] = useState(null); // {kind: 'booked'|'link', ...}
  const { copy, copied } = useCopy();
  const set = (patch) => { setForm((f) => ({ ...f, ...patch })); setResult(null); setPicked([]); };

  useEffect(() => {
    if (!open) return;
    setResult(null); setPicked([]); setDone(null); setError(null);
    getTeamCalendars().then((t) => {
      setTeam(t);
      setForm((f) => ({ ...f, uids: f.uids.length ? f.uids : [t.me] }));
    }).catch((e) => setError(e.message));
  }, [open]);

  const me = team?.members.find((m) => m.uid === team.me);
  const common = () => ({
    interviewer_uids: form.uids, duration_minutes: Number(form.duration), timezone: form.tz,
    location_type: form.locationType, location_text: form.locationType === 'video' ? '' : form.locationText,
  });
  const run = async (kind, fn) => {
    setBusy(kind); setError(null);
    try { await fn(); } catch (e) { setError(e.message); } finally { setBusy(null); }
  };

  const find = (e) => {
    e.preventDefault();
    run('find', async () => {
      setResult(await findAvailability(job.id, candidate.id, {
        interviewer_uids: form.uids, duration_minutes: Number(form.duration), timezone: form.tz,
        start_date: form.startDate, end_date: form.endDate, work_start: form.workStart, work_end: form.workEnd,
        include_weekends: form.weekends,
      }));
      setPicked([]);
    });
  };
  const book = () => run('book', async () => {
    const r = await bookInterview(job.id, candidate.id, { ...common(), start: picked[0] });
    setDone({ kind: 'booked', ...r });
    toast({ title: 'Interview booked', description: formatWhen(r.interview.start, form.tz) });
    onDone?.(r);
  });
  const sendLink = () => run('link', async () => {
    const r = await createSchedulingLink(job.id, candidate.id, { ...common(), slots: picked });
    setDone({ kind: 'link', ...r });
    onDone?.(r);
  });

  const byDay = useMemo(() => {
    const days = new Map();
    (result?.slots || []).forEach((s) => {
      const key = fmt(s.start, form.tz, { weekday: 'long', day: 'numeric', month: 'long' });
      days.set(key, [...(days.get(key) || []), s]);
    });
    return [...days];
  }, [result, form.tz]);
  const toggle = (start) => setPicked((p) => (p.includes(start) ? p.filter((x) => x !== start) : p.length >= 30 ? p : [...p, start]));

  const footer = !done && result && (
    <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
      <span className="text-sm text-ink-3" aria-live="polite">{picked.length ? `${picked.length} time${picked.length > 1 ? 's' : ''} picked` : 'Pick one time to book, or several to offer'}</span>
      <div className="flex flex-wrap gap-2">
        <Button variant="secondary" onClick={sendLink} disabled={!picked.length || !!busy || !me?.calendar}>
          {busy === 'link' && <Loader2 className="animate-spin" aria-hidden="true" />} Send candidate a link
        </Button>
        <Button onClick={book} disabled={picked.length !== 1 || !!busy || !me?.calendar}>
          {busy === 'book' && <Loader2 className="animate-spin" aria-hidden="true" />} Book this time
        </Button>
      </div>
    </div>
  );

  return (
    <Modal open={open} onOpenChange={onOpenChange} title="Schedule interview"
      description={candidate && job ? `${candidate.name} for ${job.title}` : undefined} footer={footer}>
      <div className="space-y-5 p-5">
        {error && <p className="rounded-md border border-danger/30 bg-danger-soft p-3 text-sm text-danger" role="alert">{error}</p>}
        {done ? (
          <div className="space-y-4">
            {done.kind === 'booked' ? (
              <>
                <p className="text-sm text-ink">
                  Booked for <span className="font-medium">{formatWhen(done.interview.start, form.tz)}</span> ({form.tz}).
                  Interviewers and the candidate got a calendar invitation.
                </p>
                {safeUrl(done.interview.joinUrl) && (
                  <a href={safeUrl(done.interview.joinUrl)} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1.5 text-sm text-primary-text hover:underline">
                    <Video className="h-4 w-4" aria-hidden="true" /> Video link
                  </a>
                )}
                {done.candidateStatus && <p className="text-sm text-ink-3">Candidate moved to {done.candidateStatus}.</p>}
              </>
            ) : (
              <Field label="Scheduling link for the candidate" htmlFor="schedule-link"
                hint="Shown once. It works until a time is picked or it expires in 7 days.">
                <div className="flex gap-2">
                  <Input id="schedule-link" readOnly value={done.url} onFocus={(e) => e.target.select()} />
                  <Button variant="secondary" onClick={() => copy(done.url)} aria-label="Copy scheduling link">
                    {copied ? <Check aria-hidden="true" /> : <Copy aria-hidden="true" />}
                  </Button>
                </div>
              </Field>
            )}
            <EmailResult email={done.email} />
            <SlackResult slack={done.slack} />
            <Button variant="secondary" onClick={() => onOpenChange(false)}>Done</Button>
          </div>
        ) : !team ? (
          !error && <Skeleton className="h-64" />
        ) : (
          <>
            {!me?.calendar && (
              <p className="flex items-start gap-2 rounded-md border border-warning/30 bg-warning-soft p-3 text-sm text-warning">
                <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
                <span>Connect your calendar in <Link to="/settings?tab=integrations" className="underline">Settings → Integrations</Link> to book interviews. You can still check free times.</span>
              </p>
            )}
            <form onSubmit={find} className="space-y-4">
              <fieldset>
                <legend className="mb-1.5 text-sm font-medium text-ink-2">Interviewers</legend>
                <div className="max-h-44 space-y-1 overflow-y-auto rounded-md border border-line p-2">
                  {team.members.map((m) => {
                    const id = `iv-${m.uid}`;
                    return (
                      <label key={m.uid} htmlFor={id} className="flex cursor-pointer items-center gap-2.5 rounded px-1.5 py-1 text-sm hover:bg-subtle">
                        <Checkbox id={id} checked={form.uids.includes(m.uid)}
                          onCheckedChange={(c) => set({ uids: c ? [...form.uids, m.uid] : form.uids.filter((u) => u !== m.uid) })} />
                        <span className="min-w-0 flex-1 truncate text-ink">{m.name || m.email}{m.uid === team.me && ' (you)'}</span>
                        <span className={cn('shrink-0 text-xs', m.calendar ? 'text-success' : 'text-ink-3')}>
                          {m.calendar ? 'Calendar connected' : 'No calendar'}
                        </span>
                      </label>
                    );
                  })}
                </div>
              </fieldset>
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
                <Field label="Duration" htmlFor="sch-duration">
                  <Select id="sch-duration" value={form.duration} onChange={(e) => set({ duration: e.target.value })}>
                    {[30, 45, 60, 90].map((d) => <option key={d} value={d}>{d} min</option>)}
                  </Select>
                </Field>
                <Field label="From" htmlFor="sch-from">
                  <Input id="sch-from" type="date" required min={addDays(0)} value={form.startDate} onChange={(e) => set({ startDate: e.target.value })} />
                </Field>
                <Field label="To" htmlFor="sch-to">
                  <Input id="sch-to" type="date" required min={form.startDate} value={form.endDate} onChange={(e) => set({ endDate: e.target.value })} />
                </Field>
                <Field label="Day starts" htmlFor="sch-ws">
                  <Input id="sch-ws" type="time" required value={form.workStart} onChange={(e) => set({ workStart: e.target.value })} />
                </Field>
                <Field label="Day ends" htmlFor="sch-we">
                  <Input id="sch-we" type="time" required value={form.workEnd} onChange={(e) => set({ workEnd: e.target.value })} />
                </Field>
                <Field label="Time zone" htmlFor="sch-tz" className="col-span-2 sm:col-span-1">
                  <Select id="sch-tz" value={form.tz} onChange={(e) => set({ tz: e.target.value })}>
                    {(ZONES.includes(form.tz) ? ZONES : [form.tz, ...ZONES]).map((z) => <option key={z} value={z}>{z}</option>)}
                  </Select>
                </Field>
              </div>
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-[12rem_minmax(0,1fr)]">
                <Field label="Where" htmlFor="sch-where">
                  <Select id="sch-where" value={form.locationType} onChange={(e) => setForm((f) => ({ ...f, locationType: e.target.value }))}>
                    <option value="video">Video call (Meet / Teams)</option>
                    <option value="phone">Phone</option>
                    <option value="onsite">On site</option>
                  </Select>
                </Field>
                {form.locationType !== 'video' && (
                  <Field label={form.locationType === 'phone' ? 'Phone details' : 'Address'} htmlFor="sch-loc" optional>
                    <Input id="sch-loc" maxLength={300} value={form.locationText} onChange={(e) => setForm((f) => ({ ...f, locationText: e.target.value }))} />
                  </Field>
                )}
              </div>
              <div className="flex flex-wrap items-center justify-between gap-3">
                <label htmlFor="sch-weekends" className="flex items-center gap-2 text-sm text-ink-2">
                  <Checkbox id="sch-weekends" checked={form.weekends} onCheckedChange={(c) => set({ weekends: !!c })} /> Include weekends
                </label>
                <Button type="submit" disabled={!form.uids.length || busy === 'find'}>
                  {busy === 'find' ? <Loader2 className="animate-spin" aria-hidden="true" /> : <CalendarClock aria-hidden="true" />} Find free times
                </Button>
              </div>
            </form>

            {result && (
              <div className="space-y-3 border-t border-line pt-4">
                {result.unchecked.length > 0 && (
                  <div className="rounded-md border border-warning/30 bg-warning-soft p-3 text-sm text-warning">
                    <p className="font-medium">Not checked, so these times may clash for:</p>
                    <ul className="mt-1 list-disc pl-5">
                      {result.unchecked.map((u) => <li key={u.uid}>{u.name || 'Member'}: {u.reason}</li>)}
                    </ul>
                  </div>
                )}
                {byDay.length === 0 ? (
                  <p className="text-sm text-ink-3">No common free time in this range. Try more days or longer working hours.</p>
                ) : byDay.map(([day, slots]) => (
                  <div key={day}>
                    <h3 className="mb-1.5 text-xs font-medium uppercase tracking-[0.06em] text-ink-3">{day}</h3>
                    <div className="flex flex-wrap gap-1.5">
                      {slots.map((s) => {
                        const on = picked.includes(s.start);
                        return (
                          <button key={s.start} type="button" aria-pressed={on} onClick={() => toggle(s.start)}
                            className={cn('rounded-md border px-2.5 py-1 text-sm tabular-nums transition-colors',
                              on ? 'border-primary bg-primary-soft text-primary-soft-fg' : 'border-line-strong text-ink-2 hover:bg-subtle')}>
                            {fmt(s.start, form.tz, { hour: '2-digit', minute: '2-digit' })}
                          </button>
                        );
                      })}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </>
        )}
      </div>
    </Modal>
  );
};

const toLocalInput = (iso) => {
  const d = new Date(iso);
  const pad = (n) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
};

const RescheduleDialog = ({ interview, onClose, onSaved }) => {
  const [value, setValue] = useState(() => toLocalInput(interview.start));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [done, setDone] = useState(null);
  const save = async (e) => {
    e.preventDefault();
    setBusy(true); setError(null);
    try {
      const r = await rescheduleInterview(interview.id, new Date(value).toISOString());
      setDone(r);
      onSaved(r.interview);
    } catch (err) { setError(err.message); } finally { setBusy(false); }
  };
  return (
    <Modal open onOpenChange={(o) => !o && onClose()} title="Move interview" maxWidth="md:max-w-lg"
      description={`${interview.candidateName} for ${interview.jobTitle}`}>
      <div className="space-y-4 p-5">
        {done ? (
          <>
            <p className="text-sm text-ink">Moved to <span className="font-medium">{formatWhen(done.interview.start, localZone())}</span>. Everyone's calendar is updated.</p>
            <EmailResult email={done.email} />
            <SlackResult slack={done.slack} />
            <Button variant="secondary" onClick={onClose}>Done</Button>
          </>
        ) : (
          <form onSubmit={save} className="space-y-4">
            <Field label={`New start time (${localZone()})`} htmlFor="resched-start" error={error}
              hint={`${interview.durationMinutes} minutes. Checked against the interviewers' calendars.`}>
              <Input id="resched-start" type="datetime-local" required value={value} onChange={(e) => setValue(e.target.value)} />
            </Field>
            <Button type="submit" disabled={busy}>{busy && <Loader2 className="animate-spin" aria-hidden="true" />} Move interview</Button>
          </form>
        )}
      </div>
    </Modal>
  );
};

/** Upcoming interviews of the workspace (optionally one job); `refreshKey` reloads it */
export const UpcomingInterviews = ({ jobId, refreshKey }) => {
  const { toast } = useToast();
  const [items, setItems] = useState(null);
  const [error, setError] = useState(null);
  const [mine, setMine] = useState(false);
  const [moving, setMoving] = useState(null);
  const [cancelling, setCancelling] = useState(null);
  const tz = localZone();

  const load = useCallback(() => {
    setError(null);
    listInterviews({ jobId, mine }).then((d) => setItems(d.interviews)).catch((e) => setError(e.message));
  }, [jobId, mine]);
  useEffect(() => { load(); }, [load, refreshKey]);

  const update = (iv) => setItems((list) => list.map((x) => (x.id === iv.id ? iv : x)));

  return (
    <Card className="mb-6">
      <CardHeader title="Upcoming interviews" subtitle={`Times in ${tz}`}
        action={(
          <label htmlFor="iv-mine" className="flex items-center gap-2 text-xs text-ink-2">
            <Checkbox id="iv-mine" checked={mine} onCheckedChange={(c) => setMine(!!c)} /> Only mine
          </label>
        )} />
      {error ? (
        <p className="p-5 text-sm text-danger" role="alert">Couldn't load interviews: {error}</p>
      ) : !items ? (
        <div className="p-5"><Skeleton className="h-12" /></div>
      ) : items.length === 0 ? (
        <p className="p-5 text-sm text-ink-3">Nothing booked yet. Use "Schedule" on a candidate to find a time.</p>
      ) : (
        <ul className="divide-y divide-line">
          {items.map((iv) => {
            const join = safeUrl(iv.joinUrl);
            const proposed = iv.status === 'proposed' || iv.status === 'booking';
            return (
              <li key={iv.id} className="flex flex-col gap-3 px-5 py-3.5 md:flex-row md:items-center md:justify-between">
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium text-ink">
                    {iv.candidateName} <span className="font-normal text-ink-3">· {iv.jobTitle}</span>
                  </p>
                  <p className="mt-0.5 text-xs text-ink-2">
                    {proposed ? (
                      <><Tag className="mr-1.5">Waiting for the candidate</Tag>{iv.offeredSlots.length} time{iv.offeredSlots.length === 1 ? '' : 's'} offered · link expires {formatWhen(iv.tokenExpiresAt, tz)}</>
                    ) : (
                      <>{formatWhen(iv.start, tz)} · {iv.durationMinutes} min</>
                    )}
                  </p>
                  <p className="mt-0.5 truncate text-xs text-ink-3">With {iv.interviewers.map((i) => i.name || i.email).join(', ')}</p>
                </div>
                <div className="flex shrink-0 flex-wrap gap-2">
                  {join && (
                    <a href={join} target="_blank" rel="noreferrer" className="inline-flex h-8 items-center gap-1.5 rounded-md px-3 text-xs font-medium text-primary-text hover:bg-subtle"
                      aria-label={`Join interview with ${iv.candidateName}`}>
                      <ExternalLink className="h-4 w-4" aria-hidden="true" /> Join
                    </a>
                  )}
                  {iv.status === 'scheduled' && (
                    <Button size="sm" variant="secondary" onClick={() => setMoving(iv)} aria-label={`Reschedule interview with ${iv.candidateName}`}>Reschedule</Button>
                  )}
                  {iv.status !== 'booking' && (
                    <Button size="sm" variant="ghost" onClick={() => setCancelling(iv)} aria-label={`Cancel interview with ${iv.candidateName}`}>Cancel</Button>
                  )}
                </div>
              </li>
            );
          })}
        </ul>
      )}
      {moving && <RescheduleDialog interview={moving} onClose={() => setMoving(null)} onSaved={update} />}
      <ConfirmDialog open={!!cancelling} onOpenChange={(o) => !o && setCancelling(null)}
        title={cancelling?.status === 'scheduled' ? 'Cancel this interview?' : 'Withdraw the scheduling link?'}
        description={cancelling?.status === 'scheduled'
          ? 'The calendar event is deleted and everyone gets a cancellation, including the candidate.'
          : 'The candidate can no longer pick a time with this link.'}
        confirmLabel={cancelling?.status === 'scheduled' ? 'Cancel interview' : 'Withdraw link'}
        onConfirm={async () => {
          try {
            const r = await cancelInterview(cancelling.id);
            setItems((list) => list.filter((x) => x.id !== cancelling.id));
            toast({ title: 'Cancelled', description: r.email && !r.email.sent ? "The candidate wasn't emailed; the calendar cancellation still reaches them if they had the invite." : undefined });
          } catch (e) {
            toast({ title: 'Could not cancel', description: e.message, variant: 'destructive' });
          }
        }} />
    </Card>
  );
};
