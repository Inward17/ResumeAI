/**
 * Settings sections backed by the organization API: team & invites,
 * workspace API keys, and plan & usage (live limits of the backend's API keys).
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
} from '../services/orgService';
import { ConfirmDialog } from './Modal';
import {
  Card, CardHeader, Button, IconButton, Field, Input, Select, Initials, EmptyState, Skeleton, Menu, StatStrip, RelativeDate, formatDate,
} from './common';

const ROLE_LABEL = { owner: 'Owner', admin: 'Admin', member: 'Member' };

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
  if (!org) return <div className="space-y-4"><Skeleton className="h-40 rounded-lg" /><Skeleton className="h-64 rounded-lg" /></div>;

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
          <form onSubmit={sendInvite} className="grid grid-cols-1 gap-3 p-5 sm:grid-cols-[minmax(0,1fr)_9rem_auto] sm:items-end">
            <Field label="Email" htmlFor="invite-email">
              <Input id="invite-email" type="email" required placeholder="colleague@company.com" autoComplete="off"
                value={email} onChange={(e) => setEmail(e.target.value)} />
            </Field>
            <Field label="Role" htmlFor="invite-role">
              <Select id="invite-role" value={role} onChange={(e) => setRole(e.target.value)}>
                <option value="member">Member</option>
                <option value="admin">Admin</option>
              </Select>
            </Field>
            <Button type="submit" disabled={sending || !email.trim()}>
              {sending ? <Loader2 className="animate-spin" aria-hidden="true" /> : <Mail aria-hidden="true" />}
              {sending ? 'Sending…' : 'Send invite'}
            </Button>
          </form>
          <p className="-mt-2 px-5 pb-4 text-xs text-ink-3">Admins can invite people and manage API keys. Members can work on every job.</p>
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

      <Card className="overflow-hidden">
        <CardHeader title="Members" subtitle={`${org.members.length} ${org.members.length === 1 ? 'person' : 'people'}`} />
        <ul className="divide-y divide-line">
          {org.members.map((m) => {
            const self = m.uid === org.me;
            const actions = [];
            if (self && m.role !== 'owner') {
              actions.push({ label: 'Leave workspace', Icon: LogOut, danger: true,
                onSelect: () => setConfirm({ title: 'Leave this workspace?', description: 'You’ll lose access to its jobs and candidates until someone invites you again.', label: 'Leave', run: () => removeMember(m.uid).then(() => window.location.assign('/dashboard')) }) });
            } else if (manager && !self && m.role !== 'owner') {
              actions.push({ label: m.role === 'admin' ? 'Make member' : 'Make admin', onSelect: run(() => changeMemberRole(m.uid, m.role === 'admin' ? 'member' : 'admin'), 'Role updated') });
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
{`curl ${window.location.protocol}//${window.location.hostname}:8000/api/jobs \\
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
        {!keys ? <div className="p-5"><Skeleton className="h-10" /></div> : keys.length === 0 ? (
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
          try { await revokeApiKey(revoking.id); toast({ title: 'Key revoked' }); await load(); } catch (err) { toast({ title: 'Could not revoke', description: err.message, variant: 'destructive' }); }
        }} />
    </div>
  );
};

/* ── Plan & usage ──────────────────────────────────────────────────── */

const STATUS = {
  ok: { dot: 'bg-success', text: 'Connected' },
  limited: { dot: 'bg-warning', text: 'No key — public limits' },
  error: { dot: 'bg-danger', text: 'Error' },
  not_configured: { dot: 'bg-ink-3', text: 'Not configured' },
};

const fmt = (n, unit) => (n == null ? '—' : unit === 'USD' ? `$${Number(n).toFixed(2)}` : Number(n).toLocaleString());

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
      {pct != null && (
        <div className="mt-1.5 h-1 overflow-hidden rounded-full bg-line">
          <div className={cn('h-full rounded-full', pct >= 90 ? 'bg-danger' : pct >= 70 ? 'bg-warning' : 'bg-success')} style={{ width: `${pct}%` }} />
        </div>
      )}
      <p className="mt-1 text-xs text-ink-3">
        {[m.unit !== 'USD' && m.unit, m.resets_at && `resets ${new Date(m.resets_at).toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' })}`].filter(Boolean).join(' · ')}
      </p>
    </div>
  );
};

export const UsageSettings = () => {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async (refresh = false) => {
    setError(null);
    setRefreshing(true);
    try {
      setData(await getUsage(refresh));
    } catch (err) {
      setError(err.message);
    } finally {
      setRefreshing(false);
    }
  }, []);
  useEffect(() => { load(); }, [load]);

  if (error) return <ErrorCard error={error} onRetry={() => load(true)} />;
  if (!data) return <div className="space-y-4"><Skeleton className="h-28 rounded-lg" /><Skeleton className="h-72 rounded-lg" /></div>;

  const w = data.workspace;
  return (
    <div className="space-y-6">
      <div>
        <div className="mb-3 flex items-end justify-between gap-3">
          <div>
            <p className="text-xs font-medium uppercase tracking-[0.08em] text-ink-3">Current plan</p>
            <p className="font-serif text-3xl text-ink">{data.plan}</p>
            <p className="text-sm text-ink-3">No seat or usage caps from ResumeAI — your limits are the API keys below.</p>
          </div>
        </div>
        <StatStrip items={[
          { label: 'Candidates this month', value: w.candidates_this_month, sub: `${w.candidates_total} in total` },
          { label: 'Jobs', value: w.jobs, sub: `${w.active_jobs} active` },
          { label: 'Members', value: w.members },
          { label: 'API keys', value: w.api_keys },
        ]} />
      </div>

      <Card className="overflow-hidden">
        <CardHeader title="Service limits" subtitle={`Live from each provider · checked ${new Date(data.checked_at).toLocaleTimeString()}`}
          action={<Button size="sm" variant="secondary" onClick={() => load(true)} disabled={refreshing}>
            <RefreshCw className={cn(refreshing && 'animate-spin')} aria-hidden="true" /> Refresh
          </Button>} />
        <ul className="divide-y divide-line">
          {data.providers.map((p) => {
            const st = STATUS[p.status] || STATUS.error;
            return (
              <li key={p.id} className="grid grid-cols-1 gap-3 px-5 py-4 md:grid-cols-[14rem_minmax(0,1fr)]">
                <div>
                  <p className="text-sm font-medium text-ink">{p.name}</p>
                  <p className="text-xs text-ink-3">{p.purpose}</p>
                  <p className="mt-1.5 flex items-center gap-1.5 text-xs text-ink-2">
                    <span className={cn('h-2 w-2 rounded-full', st.dot)} aria-hidden="true" />{st.text}
                  </p>
                </div>
                <div className="space-y-3">
                  {p.status === 'not_configured' && (
                    <p className="text-sm text-ink-3">Set <code className="rounded bg-subtle px-1 font-mono text-xs">{p.env}</code> in backend/.env to enable.</p>
                  )}
                  {p.error && <p className="text-sm text-danger">{p.error}</p>}
                  {p.metrics.map((m) => <MetricRow key={m.label} m={m} />)}
                  {p.note && <p className="text-xs text-ink-3">{p.note}</p>}
                </div>
              </li>
            );
          })}
        </ul>
      </Card>
      <p className="flex items-center gap-1.5 text-xs text-ink-3">
        <ExternalLink className="h-3.5 w-3.5" aria-hidden="true" /> Billing for each service happens in that provider's own dashboard.
      </p>
    </div>
  );
};
