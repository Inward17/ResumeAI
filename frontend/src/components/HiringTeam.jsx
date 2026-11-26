/** The job's hiring team: who among the hiring managers and interviewers can see this job. */
import React, { useEffect, useState } from 'react';
import { Loader2 } from 'lucide-react';
import { useToast } from '../hooks/use-toast';
import { setJobTeam } from '../services/jobService';
import { ROLE_LABEL, RESTRICTED_ROLES, loadOrg, usePermissions } from '../lib/permissions';
import Modal from './Modal';
import { Card, CardHeader, Button, Initials } from './common';

const HiringTeam = ({ job, onChange }) => {
  const { toast } = useToast();
  const { can } = usePermissions();
  const [members, setMembers] = useState([]);
  const [editing, setEditing] = useState(false);
  const [picked, setPicked] = useState([]);
  const [saving, setSaving] = useState(false);

  useEffect(() => { loadOrg().then((o) => setMembers(o.members || [])).catch(() => {}); }, []);

  const team = members.filter((m) => job.teamUids.includes(m.uid));
  const canEdit = can('job.assign_team');

  const open = () => { setPicked(job.teamUids); setEditing(true); };
  const toggle = (uid) => setPicked((p) => (p.includes(uid) ? p.filter((u) => u !== uid) : [...p, uid]));
  const save = async () => {
    setSaving(true);
    try {
      onChange(await setJobTeam(job.id, picked));
      setEditing(false);
      toast({ title: 'Hiring team updated' });
    } catch (err) {
      toast({ title: 'Could not update the hiring team', description: err.message, variant: 'destructive' });
    } finally {
      setSaving(false);
    }
  };

  return (
    <Card>
      <CardHeader title="Hiring team"
        action={canEdit && <Button size="sm" variant="ghost" onClick={open} aria-label="Edit hiring team">Edit</Button>} />
      <div className="p-4">
        {team.length ? (
          <ul className="space-y-2">
            {team.map((m) => (
              <li key={m.uid} className="flex min-w-0 items-center gap-2 text-sm">
                <Initials name={m.name || m.email} className="h-7 w-7 text-xs" />
                <span className="min-w-0 flex-1 truncate text-ink">{m.name || m.email}</span>
                <span className="shrink-0 text-xs text-ink-3">{ROLE_LABEL[m.role]}</span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-ink-3">
            No one assigned. Hiring managers and interviewers only see jobs they are on the hiring team of.
          </p>
        )}
      </div>

      <Modal open={editing} onOpenChange={(o) => !o && setEditing(false)} title="Hiring team"
        description="Hiring managers and interviewers see only the jobs they are on. Owners, admins and recruiters see every job."
        footer={(
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={() => setEditing(false)}>Cancel</Button>
            <Button onClick={save} disabled={saving}>
              {saving && <Loader2 className="animate-spin" aria-hidden="true" />} Save team
            </Button>
          </div>
        )}>
        <fieldset className="px-5 py-4">
          <legend className="sr-only">Workspace members on this job's hiring team</legend>
          <ul className="divide-y divide-line">
            {members.map((m) => (
              <li key={m.uid}>
                <label className="flex cursor-pointer items-center gap-3 py-2.5 text-sm">
                  <input type="checkbox" className="h-4 w-4 accent-primary" checked={picked.includes(m.uid)}
                    onChange={() => toggle(m.uid)} />
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-ink">{m.name || m.email}</span>
                    <span className="block truncate text-xs text-ink-3">{m.email}</span>
                  </span>
                  <span className={RESTRICTED_ROLES.includes(m.role) ? 'text-xs font-medium text-ink-2' : 'text-xs text-ink-3'}>
                    {ROLE_LABEL[m.role]}
                  </span>
                </label>
              </li>
            ))}
          </ul>
        </fieldset>
      </Modal>
    </Card>
  );
};

export default HiringTeam;
