/**
 * Settings sections backed by the organization API: team & invites, AI usage,
 * integrations (provider keys and their live limits), workspace API keys, and plan & usage.
 */
import React, { useCallback, useEffect, useState } from 'react';
import {
  Copy, Check, Mail, Link2, Trash2, KeyRound, RefreshCw, AlertTriangle, MoreHorizontal, LogOut, Loader2, ExternalLink,
} from 'lucide-react';
import { useToast } from '../hooks/use-toast';
import { cn } from '../lib/utils';
import {
  getOrg, renameOrg, changeMemberRole, removeMember, inviteMember, revokeInvite,
  listApiKeys, createApiKey, revokeApiKey, getUsage,
  getAiUsage, getIntegrations, testIntegration, saveProviderKey, removeProviderKey,
} from '../services/orgService';
import { ConfirmDialog } from './Modal';
import { API_BASE_URL } from '../services/api';
import { ROLE_LABEL, ASSIGNABLE_ROLES } from '../lib/permissions';
import {
  Card, CardHeader, Button, IconButton, Field, Input, Select, Initials, EmptyState, Skeleton, Menu, StatStrip, RelativeDate, formatDate, Segmented,
} from './common';
import { SkeletonRegion, RowsSkeleton, PanelSkeleton } from './ui/skeleton';

const useCopy = () => {
  const { toast } = useToast();
  const [copied, setCopied] = useState(null);
  const copy = async (text, id = text) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(id);
      setTimeout(() => setCopied((c) => (c === id ? null : c)), 1500);
    } catch {
      toast({ title: 'Could not copy', description: 'Select the text and copy it manually.', variant: 'destructive' });
    }
  };
  return { copy, copied };
};

const ErrorCard = ({ error, onRetry }) => (
  <Card>
    <EmptyState icon={AlertTriangle} title="Couldn't load this section" description={error}
      action={<Button variant="secondary" onClick={onRetry}>Try again</Button>} />
  </Card>
);

/* ── Team ──────────────────────────────────────────────────────────── */

export const TeamSettings = () => {
  const { toast } = useToast();
  const { copy, copied } = useCopy();
  const [org, setOrg] = useState(null);
  const [error, setError] = useState(null);
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [role, setRole] = useState('member');
  const [sending, setSending] = useState(false);
  const [lastInvite, setLastInvite] = useState(null);
  const [confirm, setConfirm] = useState(null); // { title, description, label, run }

  const load = useCallback(async () => {
    setError(null);
    try {
      const data = await getOrg();
      setOrg(data);
      setName(data.name);
    } catch (err) {
      setError(err.message);
    }
  }, []);
  useEffect(() => { load(); }, [load]);

  if (error) return <ErrorCard error={error} onRetry={load} />;
  if (!org) return <SkeletonRegion label="Loading workspace" className="space-y-4"><PanelSkeleton rows={2} /><PanelSkeleton rows={4} avatar /></SkeletonRegion>;

  const manager = org.role === 'owner' || org.role === 'admin';
  const run = (fn, success) => async (...args) => {
    try {
      await fn(...args);
      if (success) toast({ title: success });
      window.dispatchEvent(new Event('resumeai:org'));
      await load();
    } catch (err) {
      toast({ title: 'Something went wrong', description: err.message, variant: 'destructive' });
    }
  };

  const sendInvite = async (e) => {
    e.preventDefault();
    setSending(true);
    try {
      const invite = await inviteMember(email.trim(), role);
      setLastInvite(invite);
      setEmail('');
      toast(invite.email_sent
        ? { title: 'Invitation sent', description: `${invite.email} will get an email with a join link.` }
        : { title: 'Invitation created', description: 'Email isn’t set up, so share the link yourself.' });
      await load();
    } catch (err) {
      toast({ title: 'Could not invite', description: err.message, variant: 'destructive' });
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader title="Workspace" subtitle="Everyone in the workspace shares its jobs and candidates." />
        <form className="flex flex-col gap-3 p-5 sm:flex-row sm:items-end"
          onSubmit={(e) => { e.preventDefault(); run(() => renameOrg(name.trim()), 'Workspace renamed')(); }}>
          <Field label="Workspace name" htmlFor="org-name" className="flex-1">
            <Input id="org-name" value={name} onChange={(e) => setName(e.target.value)} disabled={!manager} maxLength={80} />
          </Field>
          {manager && <Button type="submit" variant="secondary" disabled={!name.trim() || name.trim() === org.name}>Save</Button>}
        </form>
      </Card>

      {manager && (
        <Card>
          <CardHeader title="Invite people" subtitle={org.email_delivery
            ? 'They get an email with a link to join. You can also copy the link.'
            : 'Email sending isn’t configured (COMPOSIO_API_KEY), so you’ll get a link to share.'} />
          <form onSubmit={sendInvite} className="grid grid-cols-1 gap-3 p-5 sm:grid-cols-[minmax(0,1fr)_11rem_auto] sm:items-end">
            <Field label="Email" htmlFor="invite-email">
              <Input id="invite-email" type="email" required placeholder="colleague@company.com" autoComplete="off"
                value={email} onChange={(e) => setEmail(e.target.value)} />
            </Field>
            <Field label="Role" htmlFor="invite-role">
              <Select id="invite-role" value={role} onChange={(e) => setRole(e.target.value)} aria-describedby="invite-role-help">
                {ASSIGNABLE_ROLES.map((r) => <option key={r.id} value={r.id}>{ROLE_LABEL[r.id]}</option>)}
              </Select>
            </Field>
            <Button type="submit" disabled={sending || !email.trim()}>
              {sending ? <Loader2 className="animate-spin" aria-hidden="true" /> : <Mail aria-hidden="true" />}
              {sending ? 'Sending…' : 'Send invite'}
            </Button>
          </form>
          <dl id="invite-role-help" className="-mt-2 space-y-1 px-5 pb-4 text-xs text-ink-3">
            {ASSIGNABLE_ROLES.map((r) => (
              <div key={r.id} className={cn('flex gap-1.5', r.id === role && 'text-ink-2')}>
                <dt className="shrink-0 font-medium">{ROLE_LABEL[r.id]}:</dt><dd>{r.description}</dd>
              </div>
            ))}
          </dl>
          {lastInvite && (
            <div className={cn('mx-5 mb-5 rounded-md border p-3 text-sm',
              lastInvite.email_sent ? 'border-success/30 bg-success-soft' : 'border-warning/30 bg-warning-soft')}>
              <p className={cn('font-medium', lastInvite.email_sent ? 'text-success' : 'text-warning')}>
                {lastInvite.email_sent ? `Email sent to ${lastInvite.email}` : `Email not sent to ${lastInvite.email}`}
              </p>
              {!lastInvite.email_sent && lastInvite.email_error && <p className="mt-0.5 text-xs text-ink-2">{lastInvite.email_error}</p>}
              <div className="mt-2 flex items-center gap-2">
                <code className="min-w-0 flex-1 truncate rounded bg-surface px-2 py-1 text-xs text-ink-2">{lastInvite.join_url}</code>
                <Button size="sm" variant="secondary" onClick={() => copy(lastInvite.join_url, 'last')}>
                  {copied === 'last' ? <Check aria-hidden="true" /> : <Copy aria-hidden="true" />} {copied === 'last' ? 'Copied' : 'Copy link'}
                </Button>
              </div>
            </div>
          )}
        </Card>
      )}

      <Card>
        <CardHeader title="Members" subtitle={`${org.members.length} ${org.members.length === 1 ? 'person' : 'people'}`} />
        <ul className="divide-y divide-line">
          {org.members.map((m) => {
            const self = m.uid === org.me;
            const actions = [];
            if (self && m.role !== 'owner') {
              actions.push({ label: 'Leave workspace', Icon: LogOut, danger: true,
                onSelect: () => setConfirm({ title: 'Leave this workspace?', description: 'You’ll lose access to its jobs and candidates until someone invites you again.', label: 'Leave', run: () => removeMember(m.uid).then(() => window.location.assign(`${import.meta.env.BASE_URL}dashboard`)) }) });
            } else if (manager && !self && m.role !== 'owner') {
              ASSIGNABLE_ROLES.filter((r) => r.id !== m.role).forEach((r) => actions.push({
                label: `Make ${ROLE_LABEL[r.id].toLowerCase()}`, onSelect: run(() => changeMemberRole(m.uid, r.id), 'Role updated'),
              }));
              actions.push({ separator: true });
              actions.push({ label: 'Remove from workspace', Icon: Trash2, danger: true,
                onSelect: () => setConfirm({ title: `Remove ${m.name || m.email}?`, description: 'They lose access to every job in this workspace. You can invite them again later.', label: 'Remove', run: run(() => removeMember(m.uid), 'Member removed') }) });
            }
            return (
              <li key={m.uid} className="flex items-center gap-3 px-5 py-3">
                {m.picture ? <img src={m.picture} alt="" referrerPolicy="no-referrer" className="h-9 w-9 rounded-full object-cover" />
                  : <Initials name={m.name || m.email} />}
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium text-ink">{m.name || m.email}{self && <span className="ml-1.5 font-normal text-ink-3">(you)</span>}</p>
                  <p className="truncate text-xs text-ink-3">{m.email}</p>
                </div>
                <span className="text-sm text-ink-2">{ROLE_LABEL[m.role]}</span>
                {actions.length > 0 ? (
                  <Menu label={`Actions for ${m.email}`} items={actions}
                    trigger={<IconButton label={`Actions for ${m.email}`}><MoreHorizontal aria-hidden="true" /></IconButton>} />
                ) : <span className="w-8" />}
              </li>
            );
          })}
        </ul>
      </Card>

      {manager && org.invites.length > 0 && (
        <Card className="overflow-hidden">
          <CardHeader title="Pending invitations" />
          <ul className="divide-y divide-line">
            {org.invites.map((inv) => (
              <li key={inv.id} className="flex flex-col gap-2 px-5 py-3 sm:flex-row sm:items-center">
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium text-ink">{inv.email}</p>
                  <p className="text-xs text-ink-3">
                    {ROLE_LABEL[inv.role]} · {inv.email_sent ? 'Emailed' : 'Link only'} · invited by {inv.invited_by} · expires {formatDate(inv.expires_at)}
                  </p>
                </div>
                <div className="flex gap-2">
                  <Button size="sm" variant="secondary" onClick={() => copy(inv.join_url, inv.id)}>
                    {copied === inv.id ? <Check aria-hidden="true" /> : <Link2 aria-hidden="true" />} {copied === inv.id ? 'Copied' : 'Copy link'}
                  </Button>
                  <Button size="sm" variant="ghost" onClick={run(() => revokeInvite(inv.id), 'Invitation revoked')}>Revoke</Button>
                </div>
              </li>
            ))}
          </ul>
        </Card>
      )}

      <ConfirmDialog open={!!confirm} onOpenChange={(o) => !o && setConfirm(null)}
        title={confirm?.title} description={confirm?.description} confirmLabel={confirm?.label} onConfirm={() => confirm.run()} />
    </div>
  );
};

/* ── API keys ──────────────────────────────────────────────────────── */

export const ApiKeysSettings = () => {
  const { toast } = useToast();
  const { copy, copied } = useCopy();
  const [keys, setKeys] = useState(null);
  const [error, setError] = useState(null);
  const [name, setName] = useState('');
  const [creating, setCreating] = useState(false);
  const [newKey, setNewKey] = useState(null);
  const [revoking, setRevoking] = useState(null);
  const [canManage, setCanManage] = useState(false);

  const load = useCallback(async () => {
    setError(null);
    try {
      const [list, org] = await Promise.all([listApiKeys(), getOrg()]);
      setKeys(list);
      setCanManage(org.role === 'owner' || org.role === 'admin');
    } catch (err) {
      setError(err.message);
    }
  }, []);
  useEffect(() => { load(); }, [load]);

  const create = async (e) => {
    e.preventDefault();
    setCreating(true);
    try {
      setNewKey(await createApiKey(name.trim()));
      setName('');
      await load();
    } catch (err) {
      toast({ title: 'Could not create key', description: err.message, variant: 'destructive' });
    } finally {
      setCreating(false);
    }
  };

  if (error) return <ErrorCard error={error} onRetry={load} />;

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader title="Workspace API keys" subtitle="Call the ResumeAI API from your own tools. A key acts as the person who created it, inside this workspace." />
        <div className="space-y-4 p-5">
          <pre className="overflow-x-auto rounded-md bg-subtle px-3 py-2.5 text-xs leading-relaxed text-ink-2">
{`curl ${API_BASE_URL}/api/jobs \\
  -H "Authorization: Bearer rai_…"`}
          </pre>
          {canManage ? (
            <form onSubmit={create} className="flex flex-col gap-3 sm:flex-row sm:items-end">
              <Field label="Key name" htmlFor="key-name" className="flex-1">
                <Input id="key-name" required maxLength={60} placeholder="e.g. ATS sync" value={name} onChange={(e) => setName(e.target.value)} />
              </Field>
              <Button type="submit" disabled={creating || !name.trim()}><KeyRound aria-hidden="true" /> {creating ? 'Creating…' : 'Create key'}</Button>
            </form>
          ) : <p className="text-sm text-ink-3">Only owners and admins can create or revoke keys.</p>}

          {newKey && (
            <div className="rounded-md border border-warning/30 bg-warning-soft p-3">
              <p className="text-sm font-medium text-warning">Copy “{newKey.name}” now — it won’t be shown again.</p>
              <div className="mt-2 flex items-center gap-2">
                <code className="min-w-0 flex-1 truncate rounded bg-surface px-2 py-1 font-mono text-xs text-ink">{newKey.key}</code>
                <Button size="sm" variant="secondary" onClick={() => copy(newKey.key, 'new')}>
                  {copied === 'new' ? <Check aria-hidden="true" /> : <Copy aria-hidden="true" />} {copied === 'new' ? 'Copied' : 'Copy'}
                </Button>
              </div>
            </div>
          )}
        </div>
      </Card>

      <Card className="overflow-hidden">
        <CardHeader title="Active keys" />
        {!keys ? <SkeletonRegion label="Loading API keys"><RowsSkeleton rows={2} /></SkeletonRegion> : keys.length === 0 ? (
          <EmptyState icon={KeyRound} title="No API keys yet" description="Keys you create appear here." className="py-8" />
        ) : (
          <ul className="divide-y divide-line">
            {keys.map((k) => (
              <li key={k.id} className="flex items-center gap-3 px-5 py-3">
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium text-ink">{k.name}</p>
                  <p className="text-xs text-ink-3">
                    <code className="font-mono">{k.prefix}…</code> · created by {k.created_by} · <RelativeDate value={k.created_at} /> ·{' '}
                    {k.last_used_at ? <>last used <RelativeDate value={k.last_used_at} /></> : 'never used'}
                  </p>
                </div>
                {canManage && <Button size="sm" variant="ghost" onClick={() => setRevoking(k)}>Revoke</Button>}
              </li>
            ))}
          </ul>
        )}
      </Card>

      <ConfirmDialog open={!!revoking} onOpenChange={(o) => !o && setRevoking(null)}
        title={`Revoke “${revoking?.name}”?`} description="Anything using this key stops working immediately. This can't be undone."
        confirmLabel="Revoke key"
        onConfirm={async () => {
          try { await revokeApiKey(revoking.id); if (newKey?.id === revoking.id) setNewKey(null); toast({ title: 'Key revoked' }); await load(); } catch (err) { toast({ title: 'Could not revoke', description: err.message, variant: 'destructive' }); }
        }} />
    </div>
  );
};

/* ── Provider status (shared by AI and Integrations) ───────────────── */

const STATUS = {
  ok: { dot: 'bg-success', text: 'Connected' },
  limited: { dot: 'bg-warning', text: 'No key — public limits' },
  error: { dot: 'bg-danger', text: 'Error' },
  not_configured: { dot: 'bg-ink-3', text: 'Not configured' },
};

const SOURCE_TEXT = {
  workspace: 'Using your workspace key',
  server: 'Using server key',
  none: 'Not configured',
};

const fmt = (n, unit) => (n == null ? '—' : unit === 'USD' ? `$${Number(n).toFixed(2)}` : Number(n).toLocaleString());
const timeOf = (iso) => (iso ? new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '');

const Meter = ({ pct }) => (
  <div className="mt-1.5 h-1 overflow-hidden rounded-full bg-line" aria-hidden="true">
    <div className={cn('h-full rounded-full', pct >= 90 ? 'bg-danger' : pct >= 70 ? 'bg-warning' : 'bg-success')} style={{ width: `${pct}%` }} />
  </div>
);

const MetricRow = ({ m }) => {
  const pct = m.limit ? Math.min(100, Math.round(((m.used || 0) / m.limit) * 100)) : null;
  return (
    <div>
      <div className="flex items-baseline justify-between gap-3 text-sm">
        <span className="text-ink-2">{m.label}</span>
        <span className="tabular-nums text-ink">
          {m.used != null && m.limit != null ? <>{fmt(m.used, m.unit)} <span className="text-ink-3">of {fmt(m.limit, m.unit)}</span></>
            : m.used != null ? fmt(m.used, m.unit) : fmt(m.limit, m.unit)}
        </span>
      </div>
      {pct != null && <Meter pct={pct} />}
      <p className="mt-1 text-xs text-ink-3">
        {[m.unit !== 'USD' && m.unit, m.resetsAt && `resets ${new Date(m.resetsAt).toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' })}`].filter(Boolean).join(' · ')}
      </p>
    </div>
  );
};

const StatusLine = ({ p }) => {
  const st = STATUS[p.status] || STATUS.error;
  return (
    <p className="flex items-center gap-1.5 text-xs text-ink-2">
      <span className={cn('h-2 w-2 shrink-0 rounded-full', st.dot)} aria-hidden="true" />
      {st.text}{p.checkedAt && <span className="text-ink-3">· checked {timeOf(p.checkedAt)}</span>}
    </p>
  );
};

const ProviderDetails = ({ p }) => (
  <div className="space-y-3">
    {p.error && <p className="text-sm text-danger">{p.error}</p>}
    {p.metrics.map((m) => <MetricRow key={m.label} m={m} />)}
    {p.note && <p className="text-xs text-ink-3">{p.note}</p>}
  </div>
);

/* ── AI ────────────────────────────────────────────────────────────── */

const FEATURES = [
  { id: 'interviewQuestions', label: 'Interview questions' },
  { id: 'factChecker', label: 'Fact checker' },
  { id: 'coverLetters', label: 'Cover letters', hint: 'attach and re-analyse' },
  { id: 'projectReviews', label: 'Project reviews', hint: 'one call per project' },
  { id: 'jdGeneration', label: 'Job descriptions', hint: 'written with AI' },
  { id: 'resumeParsing', label: 'Resume parsing', hint: 'counted as resume uploads' },
];

const SERIES = [
  { id: 'aiCalls', label: 'AI calls', summary: 'AI calls' },
  { id: 'uploads', label: 'Resume uploads', summary: 'resume uploads' },
];

const dayLabel = (iso, opts = { month: 'short', day: 'numeric' }) => new Date(`${iso}T00:00:00`).toLocaleDateString([], opts);

const HistoryChart = ({ history }) => {
  const [series, setSeries] = useState('aiCalls');
  const { summary } = SERIES.find((s) => s.id === series);
  const max = Math.max(1, ...history.map((d) => d[series]));
  const total = history.reduce((n, d) => n + d[series], 0);
  const activeDays = history.filter((d) => d.aiCalls || d.uploads).length;
  return (
    <Card className="overflow-hidden">
      <CardHeader className="flex-wrap" title="Last 30 days" subtitle={`${total.toLocaleString()} ${summary} in total`}
        action={<Segmented items={SERIES} value={series} onChange={setSeries} label="Chart series" />} />
      <div className="p-5">
        <div className="flex h-32 items-end gap-[2px] sm:gap-1" aria-hidden="true">
          {history.map((d) => (
            <div key={d.date} title={`${dayLabel(d.date)}: ${d[series]}`} className="flex h-full flex-1 items-end">
              <div className={cn('w-full rounded-t-sm', d[series] ? 'bg-primary' : 'bg-line')}
                style={{ height: d[series] ? `${Math.max(4, (d[series] / max) * 100)}%` : '2px' }} />
            </div>
          ))}
        </div>
        <div className="mt-2 flex justify-between text-xs text-ink-3" aria-hidden="true">
          <span>{dayLabel(history[0].date)}</span><span>Today</span>
        </div>
        {activeDays < 3 && (
          <p className="mt-3 text-xs text-ink-3">Daily history started recording when this page was added, so earlier days show no usage yet.</p>
        )}
        <details className="mt-3 text-sm">
          <summary className="cursor-pointer text-ink-3 hover:text-ink">Show as table</summary>
          <div className="mt-2 max-h-64 overflow-y-auto">
            <table className="w-full text-left text-sm">
              <caption className="sr-only">AI calls and resume uploads per day, last 30 days</caption>
              <thead className="text-xs text-ink-3">
                <tr><th scope="col" className="py-1 font-medium">Date</th><th scope="col" className="py-1 text-right font-medium">AI calls</th><th scope="col" className="py-1 text-right font-medium">Uploads</th></tr>
              </thead>
              <tbody className="divide-y divide-line tabular-nums">
                {[...history].reverse().map((d) => (
                  <tr key={d.date}>
                    <th scope="row" className="py-1 font-normal text-ink-2">{dayLabel(d.date, { weekday: 'short', month: 'short', day: 'numeric' })}</th>
                    <td className="py-1 text-right text-ink">{d.aiCalls}</td>
                    <td className="py-1 text-right text-ink">{d.uploads}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
      </div>
    </Card>
  );
};

export const AiSettings = () => {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async (refresh = false) => {
    setError(null);
    setRefreshing(true);
    try {
      setData(await getAiUsage(refresh));
    } catch (err) {
      setError(err.message);
    } finally {
      setRefreshing(false);
    }
  }, []);
  useEffect(() => { load(); }, [load]);

  if (error) return <ErrorCard error={error} onRetry={() => load(true)} />;
  if (!data) {
    return (
      <SkeletonRegion label="Loading AI usage" className="space-y-6">
        <div className="rounded-lg border border-line bg-surface" aria-hidden="true">
          <div className="border-b border-line px-5 py-4"><Skeleton className="h-4 w-32" /></div>
          <div className="grid grid-cols-1 gap-5 p-5 sm:grid-cols-2">
            {[1, 2].map((i) => <div key={i} className="space-y-2"><Skeleton className="h-3.5 w-28" /><Skeleton className="h-2 rounded-full" /></div>)}
          </div>
        </div>
        <PanelSkeleton rows={4} />
      </SkeletonRegion>
    );
  }

  const resets = new Date(data.resetsAt);
  const featureMax = Math.max(1, ...FEATURES.map((f) => data.features[f.id] || 0));
  return (
    <div className="space-y-6">
      <Card>
        <CardHeader title="Today's usage" subtitle={`Daily limits for this workspace. They reset at 00:00 UTC (${resets.toLocaleString([], { weekday: 'short', hour: '2-digit', minute: '2-digit' })} your time).`} />
        <div className="grid grid-cols-1 gap-5 p-5 sm:grid-cols-2">
          {['aiCall', 'resumeUpload'].map((kind) => {
            const q = data.today[kind];
            return <MetricRow key={kind} m={{ label: q.label[0].toUpperCase() + q.label.slice(1), used: q.used, limit: q.limit, unit: 'today' }} />;
          })}
        </div>
        <p className="border-t border-line px-5 py-3 text-xs text-ink-3">The limits apply even when this workspace uses its own provider keys.</p>
      </Card>

      <Card>
        <CardHeader title="By feature" subtitle="AI calls today, per feature." />
        <ul className="divide-y divide-line">
          {FEATURES.map((f) => {
            const n = data.features[f.id] || 0;
            return (
              <li key={f.id} className="px-5 py-3">
                <div className="flex items-baseline justify-between gap-3 text-sm">
                  <span className="text-ink-2">{f.label}{f.hint && <span className="text-xs text-ink-3"> · {f.hint}</span>}</span>
                  <span className="tabular-nums text-ink">{n.toLocaleString()}</span>
                </div>
                <div className="mt-1.5 h-1 overflow-hidden rounded-full bg-line" aria-hidden="true">
                  <div className="h-full rounded-full bg-primary" style={{ width: `${(n / featureMax) * 100}%` }} />
                </div>
              </li>
            );
          })}
        </ul>
      </Card>

      <Card className="overflow-hidden">
        <CardHeader title="AI providers" subtitle="Key and model checks. Change keys on the Integrations tab."
          action={<Button size="sm" variant="secondary" onClick={() => load(true)} disabled={refreshing}>
            <RefreshCw className={cn(refreshing && 'animate-spin')} aria-hidden="true" /> Refresh
          </Button>} />
        <ul className="divide-y divide-line">
          {data.providers.map((p) => (
            <li key={p.id} className="grid grid-cols-1 gap-3 px-5 py-4 md:grid-cols-[14rem_minmax(0,1fr)]">
              <div className="space-y-1">
                <p className="text-sm font-medium text-ink">{p.name}</p>
                <p className="text-xs text-ink-3">{p.purpose}</p>
                <p className="text-xs text-ink-3">{SOURCE_TEXT[p.source]}</p>
                <StatusLine p={p} />
              </div>
              <ProviderDetails p={p} />
            </li>
          ))}
        </ul>
      </Card>

      <HistoryChart history={data.history} />
    </div>
  );
};

/* ── Integrations ──────────────────────────────────────────────────── */

const KeyForm = ({ provider, onSaved, onCancel }) => {
  const { toast } = useToast();
  const [key, setKey] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const id = `key-${provider.id}`;

  const submit = async (e) => {
    e.preventDefault();
    setSaving(true);
    setError(null);
    try {
      await saveProviderKey(provider.id, key.trim());
      toast({ title: `${provider.name} key saved`, description: 'This workspace now uses its own key.' });
      onSaved();
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <form onSubmit={submit} className="space-y-3 rounded-md border border-line bg-subtle/50 p-3">
      <Field label={`${provider.name} key`} htmlFor={id} error={error}
        hint="Tested with the provider before it's saved. It's stored encrypted and never shown again.">
        <Input id={id} type="password" autoComplete="off" spellCheck={false} required minLength={8} maxLength={512}
          value={key} onChange={(e) => setKey(e.target.value)} aria-invalid={!!error} />
      </Field>
      <div className="flex flex-wrap gap-2">
        <Button type="submit" size="sm" disabled={saving || key.trim().length < 8}>
          {saving ? <><Loader2 className="animate-spin" aria-hidden="true" /> Testing…</> : 'Test and save'}
        </Button>
        <Button type="button" size="sm" variant="ghost" onClick={onCancel} disabled={saving}>Cancel</Button>
      </div>
    </form>
  );
};

export const IntegrationsSettings = () => {
  const { toast } = useToast();
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [editing, setEditing] = useState(null);
  const [removing, setRemoving] = useState(null);
  const [testing, setTesting] = useState(null);
  const [announce, setAnnounce] = useState('');

  const load = useCallback(async (refresh = false) => {
    setError(null);
    try {
      setData(await getIntegrations(refresh));
    } catch (err) {
      setError(err.message);
    }
  }, []);
  useEffect(() => { load(); }, [load]);

  const test = async (p) => {
    setTesting(p.id);
    setAnnounce(`Testing ${p.name}…`);
    try {
      const row = await testIntegration(p.id);
      setData((d) => ({ ...d, providers: d.providers.map((x) => (x.id === p.id ? { ...x, ...row } : x)) }));
      setAnnounce(`${p.name}: ${(STATUS[row.status] || STATUS.error).text}${row.error ? `. ${row.error}` : ''}`);
    } catch (err) {
      setAnnounce(`${p.name}: test failed. ${err.message}`);
    } finally {
      setTesting(null);
    }
  };

  if (error) return <ErrorCard error={error} onRetry={() => load(true)} />;
  if (!data) {
    return (
      <SkeletonRegion label="Loading integrations" className="space-y-4">
        <Skeleton className="h-4 w-full max-w-xl" />
        {[1, 2, 3].map((i) => (
          <div key={i} className="grid grid-cols-1 gap-4 rounded-lg border border-line bg-surface p-5 md:grid-cols-[14rem_minmax(0,1fr)]" aria-hidden="true">
            <div className="space-y-2"><Skeleton className="h-4 w-24" /><Skeleton className="h-3 w-32" /></div>
            <div className="space-y-2"><Skeleton className="h-3.5 w-3/4" /><Skeleton className="h-8 w-40" /></div>
          </div>
        ))}
      </SkeletonRegion>
    );
  }

  const { canManage, keysEnabled } = data;
  return (
    <div className="space-y-4">
      <p className="text-sm text-ink-3">
        ResumeAI runs on the server's keys. A workspace can use its own key for any provider instead; it applies to this
        workspace only, and the daily AI limits still apply.
      </p>
      {!canManage && <p className="text-sm text-ink-3">Only owners and admins can add or remove keys.</p>}
      {canManage && !keysEnabled && (
        <p className="flex items-start gap-2 rounded-md border border-warning/30 bg-warning-soft p-3 text-sm text-warning">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
          <span>Set <code className="font-mono text-xs">PROVIDER_KEYS_SECRET</code> on the server to allow workspace keys.</span>
        </p>
      )}
      <p className="sr-only" aria-live="polite" role="status">{announce}</p>

      {data.providers.map((p) => {
        const ws = p.workspaceKey;
        return (
          <Card key={p.id} className="overflow-hidden">
            <div className="grid grid-cols-1 gap-4 p-5 md:grid-cols-[14rem_minmax(0,1fr)]">
              <div className="space-y-1">
                <h3 className="text-sm font-medium text-ink">{p.name}</h3>
                <p className="text-xs text-ink-3">{p.purpose}</p>
                <p className="text-xs text-ink-2">
                  {SOURCE_TEXT[p.source]}{p.source === 'workspace' && ws && <> <code className="font-mono">···{ws.last4}</code></>}
                </p>
                {ws && keysEnabled && p.source !== 'workspace' && (
                  <p className="text-xs text-warning">A saved workspace key ···{ws.last4} can't be read (the server secret changed). Replace it.</p>
                )}
                <StatusLine p={p} />
              </div>
              <div className="space-y-3">
                <ProviderDetails p={p} />
                {p.id === 'composio' && (
                  <p className="text-xs text-ink-3">The Gmail account that sends invites (COMPOSIO_USER_ID, COMPOSIO_GMAIL_ACCOUNT_ID) stays a server setting.</p>
                )}
                {ws && <p className="text-xs text-ink-3">Workspace key added by {ws.addedBy} · <RelativeDate value={ws.addedAt} /></p>}
                {editing === p.id && (
                  <KeyForm provider={p} onCancel={() => setEditing(null)} onSaved={() => { setEditing(null); load(); }} />
                )}
              </div>
            </div>
            <div className="flex flex-wrap items-center gap-2 border-t border-line bg-subtle/50 px-5 py-3">
              <Button size="sm" variant="secondary" onClick={() => test(p)} disabled={testing === p.id}
                aria-label={`Test ${p.name}`}>
                {testing === p.id ? <Loader2 className="animate-spin" aria-hidden="true" /> : <RefreshCw aria-hidden="true" />} Test
              </Button>
              {canManage && keysEnabled && editing !== p.id && (
                <Button size="sm" variant="ghost" onClick={() => setEditing(p.id)} aria-label={`${ws ? 'Replace' : 'Add'} key for ${p.name}`}>
                  <KeyRound aria-hidden="true" /> {ws ? 'Replace' : 'Add key'}
                </Button>
              )}
              {canManage && ws && (
                <Button size="sm" variant="ghost" onClick={() => setRemoving(p)} aria-label={`Remove key for ${p.name}`}>
                  <Trash2 aria-hidden="true" /> Remove
                </Button>
              )}
            </div>
          </Card>
        );
      })}

      <ConfirmDialog open={!!removing} onOpenChange={(o) => !o && setRemoving(null)}
        title={`Remove the ${removing?.name} key?`}
        description="This workspace goes back to the server's key, or to no key if the server has none."
        confirmLabel="Remove key"
        onConfirm={async () => {
          try { await removeProviderKey(removing.id); toast({ title: 'Key removed' }); await load(); } catch (err) { toast({ title: 'Could not remove', description: err.message, variant: 'destructive' }); }
        }} />
    </div>
  );
};

/* ── Plan & usage ──────────────────────────────────────────────────── */

export const UsageSettings = () => {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      setData(await getUsage());
    } catch (err) {
      setError(err.message);
    }
  }, []);
  useEffect(() => { load(); }, [load]);

  if (error) return <ErrorCard error={error} onRetry={load} />;
  if (!data) {
    return (
      <SkeletonRegion label="Loading plan and usage">
        <Skeleton className="h-3 w-24" />
        <Skeleton className="mt-2 h-8 w-32" />
        <Skeleton className="mt-2 h-4 w-full max-w-lg" />
        <Skeleton className="mt-4 h-24 rounded-lg" />
      </SkeletonRegion>
    );
  }

  const w = data.workspace;
  return (
    <div className="space-y-6">
      <div>
        <div className="mb-3">
          <p className="text-xs font-medium uppercase tracking-[0.08em] text-ink-3">Current plan</p>
          <p className="font-serif text-3xl text-ink">{data.plan}</p>
          <p className="text-sm text-ink-3">No seat caps from ResumeAI. Daily AI limits are on the AI tab; provider keys and their limits on Integrations.</p>
        </div>
        <StatStrip items={[
          { label: 'Candidates this month', value: w.candidates_this_month, sub: `${w.candidates_total} in total` },
          { label: 'Jobs', value: w.jobs, sub: `${w.active_jobs} active` },
          { label: 'Members', value: w.members },
          { label: 'API keys', value: w.api_keys },
        ]} />
      </div>
      <p className="flex items-center gap-1.5 text-xs text-ink-3">
        <ExternalLink className="h-3.5 w-3.5" aria-hidden="true" /> Billing for each service happens in that provider's own dashboard.
      </p>
    </div>
  );
};
