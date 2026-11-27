/**
 * Calendar, email and Slack connections and interview scheduling
 * (backend: app/routes/integration_routes.py, app/routes/scheduling_routes.py). Responses are camelCase.
 */
import { call, camelize, send } from './orgService';

const get = async (path) => camelize(await call(path));
const post = async (path, body, method = 'POST') => camelize(await call(path, send(method, body)));

export const getConnections = () => get('/api/integrations/me');
export const getTeamCalendars = () => get('/api/integrations/team');
export const startConnect = async (provider) => (await call(`/api/integrations/${provider}/connect`)).url;
export const disconnect = (provider) => call(`/api/integrations/${provider}`, send('DELETE'));
export const getSlackChannels = () => get('/api/integrations/slack/channels');
export const saveSlack = (settings) => post('/api/integrations/slack', settings, 'PUT');
export const removeSlack = () => call('/api/integrations/slack', send('DELETE'));

const base = (jobId, candidateId) => `/api/jobs/${jobId}/candidates/${candidateId}/interviews`;

/** body: { interviewer_uids, duration_minutes, timezone, start_date, end_date, work_start, work_end, include_weekends } */
export const findAvailability = (jobId, candidateId, body) => post(`${base(jobId, candidateId)}/availability`, body);
/** body: { interviewer_uids, duration_minutes, timezone, start, location_type, location_text } */
export const bookInterview = (jobId, candidateId, body) => post(base(jobId, candidateId), body);
/** body: same as booking, with slots: [iso] instead of start */
export const createSchedulingLink = (jobId, candidateId, body) => post(`${base(jobId, candidateId)}/link`, body);

export const listInterviews = ({ jobId, mine } = {}) => {
  const q = new URLSearchParams();
  if (jobId) q.set('job_id', jobId);
  if (mine) q.set('mine', 'true');
  return get(`/api/interviews${q.toString() ? `?${q}` : ''}`);
};
export const rescheduleInterview = (id, start, durationMinutes) =>
  post(`/api/interviews/${id}`, { start, duration_minutes: durationMinutes || undefined }, 'PATCH');
export const cancelInterview = (id) => post(`/api/interviews/${id}/cancel`);

// Candidate's public page (no sign-in)
export const getPublicSchedule = (token) => get(`/api/public/schedule/${encodeURIComponent(token)}`);
export const pickPublicSlot = (token, start, timezone) =>
  post(`/api/public/schedule/${encodeURIComponent(token)}`, { start, timezone });
