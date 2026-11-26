/**
 * Workspace roles and what the signed-in user may do (backend: PERMISSIONS in app/org.py).
 * Only hides actions in the UI; the API is the real guard.
 */
import { useEffect, useState } from 'react';
import { getOrg } from '../services/orgService';

export const ROLE_LABEL = {
  owner: 'Owner', admin: 'Admin', member: 'Recruiter', hiring_manager: 'Hiring manager', interviewer: 'Interviewer',
};

// Roles an owner or admin can give (there is one owner)
export const ASSIGNABLE_ROLES = [
  { id: 'admin', description: 'Everything a recruiter can do, plus members, invites, API keys and integrations.' },
  { id: 'member', description: 'Creates jobs, uploads resumes and works on every job.' },
  { id: 'hiring_manager', description: 'Sees assigned jobs only; can move candidates and run AI checks.' },
  { id: 'interviewer', description: 'Sees assigned jobs only; can interview and submit evaluations.' },
];

export const RESTRICTED_ROLES = ['hiring_manager', 'interviewer'];

let cached = null; // one /api/org request shared by every component, refreshed when the workspace changes
export const loadOrg = () => {
  cached ??= getOrg().catch((err) => { cached = null; throw err; });
  return cached;
};
export const forgetOrg = () => { cached = null; };
if (typeof window !== 'undefined') window.addEventListener('resumeai:org', forgetOrg);

/** { role, can(action), restricted, loaded }. Until loaded, can() is true so recruiters see no flicker. */
export const usePermissions = () => {
  const [org, setOrg] = useState(null);
  useEffect(() => {
    let live = true;
    const refresh = () => loadOrg().then((o) => live && setOrg(o)).catch(() => {});
    refresh();
    window.addEventListener('resumeai:org', refresh);
    return () => { live = false; window.removeEventListener('resumeai:org', refresh); };
  }, []);
  const permissions = org?.permissions;
  return {
    role: org?.role,
    loaded: !!org,
    restricted: RESTRICTED_ROLES.includes(org?.role),
    can: (action) => !permissions || permissions.includes(action),
  };
};
