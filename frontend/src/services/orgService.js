/** Organization, team invites, workspace API keys and usage (backend: app/routes/org_routes.py) */
import { apiFetch } from './api';

const call = async (path, options = {}) => {
    const response = await apiFetch(path, {
        ...options,
        headers: options.body ? { 'Content-Type': 'application/json' } : undefined,
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
        const detail = Array.isArray(data.detail) ? data.detail.map((d) => d.msg).join(', ') : data.detail;
        throw new Error(detail || `Request failed (${response.status})`);
    }
    return data;
};

const send = (method, body) => ({ method, body: body ? JSON.stringify(body) : undefined });

export const getOrg = () => call('/api/org');
export const renameOrg = (name) => call('/api/org', send('PATCH', { name }));
export const changeMemberRole = (uid, role) => call(`/api/org/members/${uid}`, send('PATCH', { role }));
export const removeMember = (uid) => call(`/api/org/members/${uid}`, send('DELETE'));

export const inviteMember = (email, role) => call('/api/org/invites', send('POST', { email, role }));
export const revokeInvite = (id) => call(`/api/org/invites/${id}`, send('DELETE'));
export const previewInvite = (token) => call(`/api/invites/${token}`);
export const acceptInvite = (token) => call(`/api/invites/${token}/accept`, send('POST'));

export const listApiKeys = () => call('/api/org/api-keys');
export const createApiKey = (name) => call('/api/org/api-keys', send('POST', { name }));
export const revokeApiKey = (id) => call(`/api/org/api-keys/${id}`, send('DELETE'));

export const getUsage = (refresh = false) => call(`/api/org/usage${refresh ? '?refresh=true' : ''}`);
