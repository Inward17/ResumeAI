/**
 * /schedule/:token: the candidate picks an interview time. No sign-in; the page shows only
 * the job title, workspace name, interviewer names and the offered times (in the visitor's time zone).
 */
import React, { useEffect, useMemo, useState } from 'react';
import { useParams } from 'react-router-dom';
import { AlertTriangle, CalendarCheck, Loader2, Video } from 'lucide-react';
import { cn } from '../lib/utils';
import { getPublicSchedule, pickPublicSlot } from '../services/schedulingService';
import { Card, Button, EmptyState, Select } from './common';
import BrandMark from './BrandMark';

const ZONES = (() => {
  try { return Intl.supportedValuesOf('timeZone'); } catch { return ['UTC']; }
})();
const fmt = (iso, tz, opts) => new Intl.DateTimeFormat(undefined, { timeZone: tz, ...opts }).format(new Date(iso));
const WHEN = { weekday: 'long', day: 'numeric', month: 'long', hour: '2-digit', minute: '2-digit' };

const PublicSchedule = () => {
  const { token } = useParams();
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [tz, setTz] = useState(() => Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC');
  const [picked, setPicked] = useState(null);
  const [busy, setBusy] = useState(false);
  const [pickError, setPickError] = useState(null);

  const load = () => getPublicSchedule(token).then(setData).catch((e) => setError(e.message));
  useEffect(() => { load(); }, [token]); // eslint-disable-line react-hooks/exhaustive-deps

  const byDay = useMemo(() => {
    const days = new Map();
    (data?.slots || []).forEach((s) => {
      const key = fmt(s, tz, { weekday: 'long', day: 'numeric', month: 'long' });
      days.set(key, [...(days.get(key) || []), s]);
    });
    return [...days];
  }, [data, tz]);

  const confirm = async () => {
    setBusy(true); setPickError(null);
    try {
      setData(await pickPublicSlot(token, picked, tz));
    } catch (e) {
      setPickError(e.message);
      setPicked(null);
      load();
    } finally {
      setBusy(false);
    }
  };

  const join = data?.joinUrl?.startsWith('https://') ? data.joinUrl : null;
  return (
    <div className="min-h-[100dvh] bg-canvas px-4 py-8">
      <main className="mx-auto w-full max-w-xl">
        <div className="mb-6"><BrandMark /></div>
        <Card>
          {error ? (
            <EmptyState icon={AlertTriangle} title="This link can't be used" description={error} />
          ) : !data ? (
            <div className="flex justify-center p-12"><Loader2 className="h-5 w-5 animate-spin text-ink-3" aria-label="Loading" /></div>
          ) : data.status === 'scheduled' ? (
            <div className="p-6 text-center sm:p-8">
              <CalendarCheck className="mx-auto h-8 w-8 text-success" aria-hidden="true" />
              <h1 className="mt-3 font-serif text-3xl leading-tight text-ink">Your interview is booked</h1>
              <p className="mt-2 text-sm text-ink-2">{data.jobTitle} at {data.workspace}</p>
              <p className="mt-4 text-base font-medium text-ink">{fmt(data.start, tz, WHEN)}</p>
              <p className="text-sm text-ink-3">{data.durationMinutes} minutes · {tz}</p>
              {join && (
                <a href={join} target="_blank" rel="noreferrer" className="mt-4 inline-flex items-center gap-1.5 text-sm text-primary-text hover:underline">
                  <Video className="h-4 w-4" aria-hidden="true" /> Video link
                </a>
              )}
              <p className="mt-4 text-xs text-ink-3">A calendar invitation is on its way to your email.</p>
            </div>
          ) : (
            <div className="space-y-5 p-6 sm:p-8">
              <div>
                <p className="text-xs font-medium uppercase tracking-[0.08em] text-ink-3">Interview</p>
                <h1 className="mt-1 font-serif text-3xl leading-tight text-ink">{data.jobTitle}</h1>
                <p className="mt-1 text-sm text-ink-2">
                  {data.workspace} · {data.durationMinutes} minutes{data.locationType === 'video' ? ', video call' : data.locationType === 'phone' ? ', phone' : ', on site'}
                </p>
                {data.interviewers.length > 0 && <p className="mt-1 text-sm text-ink-3">With {data.interviewers.join(', ')}</p>}
              </div>
              <div>
                <label htmlFor="pub-tz" className="mb-1.5 block text-sm font-medium text-ink-2">Your time zone</label>
                <Select id="pub-tz" value={tz} onChange={(e) => setTz(e.target.value)}>
                  {(ZONES.includes(tz) ? ZONES : [tz, ...ZONES]).map((z) => <option key={z} value={z}>{z}</option>)}
                </Select>
              </div>
              {pickError && <p className="rounded-md border border-danger/30 bg-danger-soft p-3 text-sm text-danger" role="alert">{pickError}</p>}
              {byDay.length === 0 ? (
                <p className="text-sm text-ink-3">None of the offered times are still available. Please contact the recruiter for new ones.</p>
              ) : (
                <fieldset className="space-y-3">
                  <legend className="text-sm font-medium text-ink-2">Pick a time</legend>
                  {byDay.map(([day, slots]) => (
                    <div key={day}>
                      <h2 className="mb-1.5 text-xs font-medium uppercase tracking-[0.06em] text-ink-3">{day}</h2>
                      <div className="flex flex-wrap gap-1.5">
                        {slots.map((s) => (
                          <button key={s} type="button" aria-pressed={picked === s} onClick={() => setPicked(s)}
                            className={cn('rounded-md border px-3 py-1.5 text-sm tabular-nums transition-colors',
                              picked === s ? 'border-primary bg-primary-soft text-primary-soft-fg' : 'border-line-strong text-ink-2 hover:bg-subtle')}>
                            {fmt(s, tz, { hour: '2-digit', minute: '2-digit' })}
                          </button>
                        ))}
                      </div>
                    </div>
                  ))}
                </fieldset>
              )}
              <Button size="lg" className="w-full" onClick={confirm} disabled={!picked || busy}>
                {busy && <Loader2 className="animate-spin" aria-hidden="true" />}
                {picked ? `Book ${fmt(picked, tz, WHEN)}` : 'Pick a time'}
              </Button>
              {data.expiresAt && <p className="text-center text-xs text-ink-3">This link expires {fmt(data.expiresAt, tz, WHEN)}.</p>}
            </div>
          )}
        </Card>
      </main>
    </div>
  );
};

export default PublicSchedule;
