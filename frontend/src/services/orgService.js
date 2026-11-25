/** Organization, team invites, workspace API keys, AI usage, integrations and usage (backend: app/routes/org_routes.py) */
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

// AI usage and integrations return camelCase (feature names too: interviewQuestions, factChecker, ...)
const camelize = (v) => {
    if (Array.isArray(v)) return v.map(camelize);
    if (!v || typeof v !== 'object') return v;
    return Object.fromEntries(Object.entries(v).map(([k, x]) => [k.replace(/_([a-z0-9])/g, (_, c) => c.toUpperCase()), camelize(x)]));
};

export const getAiUsage = async (refresh = false) => camelize(await call(`/api/org/ai-usage${refresh ? '?refresh=true' : ''}`));
export const getIntegrations = async (refresh = false) => camelize(await call(`/api/org/integrations${refresh ? '?refresh=true' : ''}`));
export const testIntegration = async (id) => camelize(await call(`/api/org/integrations/${id}/test`, send('POST')));
export const saveProviderKey = async (id, key) => camelize(await call(`/api/org/integrations/${id}`, send('PUT', { key })));
export const removeProviderKey = (id) => call(`/api/org/integrations/${id}`, send('DELETE'));
