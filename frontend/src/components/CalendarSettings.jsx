/**
 * Settings > Integrations > Calendar & email: the signed-in person's Google / Microsoft
 * connection (used to book interviews and email candidates) and the workspace's Slack.
 */
import React, { useCallback, useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { AlertTriangle, CalendarDays, Link2, Loader2, Trash2 } from 'lucide-react';
import { useToast } from '../hooks/use-toast';
import {
  getConnections, startConnect, disconnect, getSlackChannels, saveSlack, removeSlack,
} from '../services/schedulingService';
import { ConfirmDialog } from './Modal';
import { Card, CardHeader, Button, Field, Input, Select, Skeleton, RelativeDate } from './common';

const CALLBACK_ERRORS = {
  expired: 'The sign-in took too long or was already used. Try again.',
  denied: 'Access was not granted.',
  forbidden: 'You are no longer allowed to connect this for the workspace.',
  exchange: "The provider didn't accept the sign-in. Try again.",
};
const NAMES = { google: 'Google', microsoft: 'Microsoft', slack: 'Slack' };

const NotConfigured = () => <p className="text-xs text-ink-3">Not configured on this server.</p>;

const SlackCard = ({ slack, onChange }) => {
  const { toast } = useToast();
  const [channels, setChannels] = useState(null);
  const [webhook, setWebhook] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [removing, setRemoving] = useState(false);

  useEffect(() => {
    if (slack.canManage && slack.connected) getSlackChannels().then((d) => setChannels(d.channels)).catch((e) => setError(e.message));
  }, [slack.canManage, slack.connected]);

  const run = async (fn) => {
    setBusy(true);
    setError(null);
    try { await fn(); } catch (e) { setError(e.message); } finally { setBusy(false); }
  };
  const connect = () => run(async () => { window.location.assign(await startConnect('slack')); });
  const pickChannel = (id) => run(async () => {
    const ch = channels.find((c) => c.id === id);
    onChange(await saveSlack({ channel_id: id, channel_name: ch?.name }));
    toast({ title: `Slack notifications go to #${ch?.name}` });
  });
  const saveWebhook = (e) => {
    e.preventDefault();
    run(async () => { onChange(await saveSlack({ webhook_url: webhook.trim() })); setWebhook(''); toast({ title: 'Slack webhook saved' }); });
  };

  const status = slack.connected ? `Connected to ${slack.team || 'Slack'}` : slack.webhook ? 'Posting through an incoming webhook' : 'Not set up';
  return (
    <Card className="overflow-hidden">
      <div className="space-y-3 p-5">
        <div>
          <h3 className="text-sm font-medium text-ink">Slack</h3>
          <p className="text-xs text-ink-3">Posts booked, moved and cancelled interviews to a channel and messages the interviewers.</p>
          <p className="mt-1 text-xs text-ink-2">{status}{slack.channel && <> · #{slack.channel.name}</>}</p>
        </div>
        {!slack.canManage && <p className="text-xs text-ink-3">Only owners and admins can set up Slack.</p>}
        {slack.canManage && slack.connected && (
          <Field label="Channel" htmlFor="slack-channel" hint="Invite the app to the channel in Slack (/invite) so it can post.">
            {channels ? (
              <Select id="slack-channel" value={slack.channel?.id || ''} disabled={busy} onChange={(e) => pickChannel(e.target.value)}>
                <option value="" disabled>Pick a channel</option>
                {channels.map((c) => <option key={c.id} value={c.id}>#{c.name}</option>)}
              </Select>
            ) : <Skeleton className="h-9" />}
          </Field>
        )}
        {slack.canManage && !slack.connected && !slack.oauthConfigured && slack.webhookAllowed && (
          <form onSubmit={saveWebhook} className="space-y-2">
            <Field label="Incoming webhook URL" htmlFor="slack-webhook"
              hint={slack.webhook ? 'A webhook is saved. Paste a new one to replace it.' : 'From a Slack app with Incoming Webhooks. Channel posts only, no direct messages.'}>
              <Input id="slack-webhook" type="url" autoComplete="off" spellCheck={false} placeholder="https://hooks.slack.com/services/…"
                value={webhook} onChange={(e) => setWebhook(e.target.value)} />
            </Field>
            <Button type="submit" size="sm" disabled={busy || !webhook.trim()}>Save webhook</Button>
          </form>
        )}
        {slack.canManage && !slack.connected && !slack.oauthConfigured && !slack.webhookAllowed && <NotConfigured />}
        {error && <p className="text-xs text-danger" role="alert">{error}</p>}
      </div>
      {slack.canManage && (slack.oauthConfigured || slack.connected || slack.webhook) && (
        <div className="flex flex-wrap gap-2 border-t border-line bg-subtle/50 px-5 py-3">
          {slack.oauthConfigured && !slack.connected && (
            <Button size="sm" variant="secondary" onClick={connect} disabled={busy}><Link2 aria-hidden="true" /> Connect Slack</Button>
          )}
          {(slack.connected || slack.webhook) && (
            <Button size="sm" variant="ghost" onClick={() => setRemoving(true)} aria-label="Remove Slack"><Trash2 aria-hidden="true" /> Remove</Button>
          )}
        </div>
      )}
      <ConfirmDialog open={removing} onOpenChange={setRemoving} title="Remove Slack?"
        description="Interview notifications stop for the whole workspace." confirmLabel="Remove Slack"
        onConfirm={async () => {
          try { await removeSlack(); onChange(null); toast({ title: 'Slack removed' }); } catch (e) { toast({ title: 'Could not remove', description: e.message, variant: 'destructive' }); }
        }} />
    </Card>
  );
};

const CalendarSettings = () => {
  const { toast } = useToast();
  const [params, setParams] = useSearchParams();
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(null);
  const [removing, setRemoving] = useState(null);

  const load = useCallback(() => getConnections().then(setData).catch((e) => setError(e.message)), []);
  useEffect(() => { load(); }, [load]);

  // Coming back from the provider's sign-in page
  useEffect(() => {
    const connected = params.get('connected');
    const err = params.get('error');
    if (!connected && !err) return;
    if (connected) toast({ title: `${NAMES[connected] || 'Account'} connected` });
    else toast({ title: `Couldn't connect ${NAMES[params.get('provider')] || 'the account'}`, description: CALLBACK_ERRORS[err] || 'Try again.', variant: 'destructive' });
    setParams({ tab: 'integrations' }, { replace: true });
  }, [params, setParams, toast]);

  const connect = async (p) => {
    setBusy(p.id);
    try {
      window.location.assign(await startConnect(p.id));
    } catch (e) {
      toast({ title: `Couldn't connect ${p.name}`, description: e.message, variant: 'destructive' });
      setBusy(null);
    }
  };

  if (error) {
    return (
      <Card className="p-5 text-sm text-ink-3">
        <p className="flex items-center gap-2"><AlertTriangle className="h-4 w-4 text-warning" aria-hidden="true" /> Couldn't load calendar connections: {error}</p>
      </Card>
    );
  }
  if (!data) return <Skeleton className="h-48 rounded-lg" />;

  return (
    <section aria-labelledby="calendar-heading" className="space-y-4">
      <Card>
        <CardHeader title={<span id="calendar-heading">Calendar & email</span>}
          subtitle="Your own account: interviews you book go on its calendar with a video link, and candidates get the email from it. Only you can use it." />
        <div className="divide-y divide-line">
          {data.calendar.map((p) => {
            const c = p.connection;
            const expired = c?.status === 'expired';
            return (
              <div key={p.id} className="flex flex-col gap-3 p-5 sm:flex-row sm:items-center sm:justify-between">
                <div className="flex min-w-0 items-start gap-3">
                  <CalendarDays className="mt-0.5 h-4 w-4 shrink-0 text-ink-3" aria-hidden="true" />
                  <div className="min-w-0">
                    <h3 className="text-sm font-medium text-ink">{p.name} {p.id === 'google' ? 'Calendar & Gmail' : 'Outlook & Teams'}</h3>
                    {c ? (
                      <p className="truncate text-xs text-ink-2">
                        {c.email || 'Connected'} · <RelativeDate value={c.connectedAt} />
                        {expired && <span className="ml-1 text-warning">· Access expired, reconnect</span>}
                      </p>
                    ) : p.configured ? <p className="text-xs text-ink-3">Not connected</p> : <NotConfigured />}
                  </div>
                </div>
                <div className="flex shrink-0 gap-2">
                  {p.configured && (!c || expired) && (
                    <Button size="sm" variant="secondary" onClick={() => connect(p)} disabled={busy === p.id} aria-label={`${expired ? 'Reconnect' : 'Connect'} ${p.name}`}>
                      {busy === p.id ? <Loader2 className="animate-spin" aria-hidden="true" /> : <Link2 aria-hidden="true" />} {expired ? 'Reconnect' : 'Connect'}
                    </Button>
                  )}
                  {c && (
                    <Button size="sm" variant="ghost" onClick={() => setRemoving(p)} aria-label={`Disconnect ${p.name}`}>
                      <Trash2 aria-hidden="true" /> Disconnect
                    </Button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </Card>

      <SlackCard slack={data.slack} onChange={(slack) => (slack ? setData((d) => ({ ...d, slack })) : load())} />

      <ConfirmDialog open={!!removing} onOpenChange={(o) => !o && setRemoving(null)}
        title={`Disconnect ${removing?.name}?`}
        description="Interviews already booked stay on the calendar, but you can't book or move interviews from ResumeAI until you connect again."
        confirmLabel="Disconnect"
        onConfirm={async () => {
          try { await disconnect(removing.id); toast({ title: `${removing.name} disconnected` }); await load(); } catch (e) { toast({ title: 'Could not disconnect', description: e.message, variant: 'destructive' }); }
        }} />
    </section>
  );
};

export default CalendarSettings;
