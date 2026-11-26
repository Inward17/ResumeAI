/**
 * Interview scorecards (backend: app/routes/scorecard_routes.py).
 * Interviewer notes and AI text are plain text: render them as text only.
 */
import { apiFetch } from './api';

const call = async (path, options = {}, fallback = 'Request failed') => {
    const response = await apiFetch(path, {
        ...options,
        headers: options.body ? { 'Content-Type': 'application/json' } : undefined,
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
        const detail = Array.isArray(data.detail) ? data.detail.map((d) => d.msg).join(', ') : data.detail;
        const err = new Error(detail || fallback);
        err.status = response.status;
        throw err;
    }
    return data;
};
const send = (method, body) => ({ method, body: body ? JSON.stringify(body) : undefined });

const camel = (v) => {
    if (Array.isArray(v)) return v.map(camel);
    if (!v || typeof v !== 'object') return v;
    return Object.fromEntries(Object.entries(v).map(([k, x]) => [k.replace(/_([a-z0-9])/g, (_, c) => c.toUpperCase()), camel(x)]));
};
const snake = (v) => {
    if (Array.isArray(v)) return v.map(snake);
    if (!v || typeof v !== 'object') return v;
    return Object.fromEntries(Object.entries(v).map(([k, x]) => [k.replace(/[A-Z]/g, (c) => `_${c.toLowerCase()}`), snake(x)]));
};

const cardUrl = (jobId, candidateId) => `/api/jobs/${jobId}/candidates/${candidateId}/scorecards`;

export const RECOMMENDATIONS = [
    { id: 'strong_no', label: 'Strong no' },
    { id: 'no', label: 'No' },
    { id: 'yes', label: 'Yes' },
    { id: 'strong_yes', label: 'Strong yes' },
];
export const MIN_EVIDENCE = 20;

export const getScorecardTemplate = async (jobId) =>
    camel((await call(`/api/jobs/${jobId}/scorecard`, {}, 'Could not load the scorecard')).scorecard);

export const saveScorecardTemplate = async (jobId, competencies) =>
    camel((await call(`/api/jobs/${jobId}/scorecard`, send('PUT', { competencies: snake(competencies) }), 'Could not save the scorecard')).scorecard);

export const suggestScorecardTemplate = async (jobId) =>
    camel((await call(`/api/jobs/${jobId}/scorecard/suggest`, send('POST'), 'Could not suggest a scorecard')).competencies);

/** { [candidateId]: { submitted, total } } */
export const getScorecardCounts = async (jobId) =>
    (await call(`/api/jobs/${jobId}/scorecard-counts`, {}, 'Could not load scorecard counts')).counts || {};

/** { template, mine, locked, others, interviewers } */
export const getScorecards = async (jobId, candidateId) =>
    camel(await call(cardUrl(jobId, candidateId), {}, 'Could not load scorecards'));

/** Save a draft (submit=false) or submit */
export const saveMyScorecard = async (jobId, candidateId, card) =>
    camel((await call(`${cardUrl(jobId, candidateId)}/mine`, send('PUT', snake(card)), 'Could not save the scorecard')).mine);

export const requestScorecard = (jobId, candidateId, uid) =>
    call(`${cardUrl(jobId, candidateId)}/requests`, send('POST', { uid }), 'Could not request a scorecard');

export const cancelScorecardRequest = (jobId, candidateId, uid) =>
    call(`${cardUrl(jobId, candidateId)}/requests/${encodeURIComponent(uid)}`, send('DELETE'), 'Could not withdraw the request');

/** Rejects with err.status 403 while the caller still owes their own scorecard */
export const getEvidenceSummary = async (jobId, candidateId) =>
    camel((await call(`${cardUrl(jobId, candidateId)}/summary`, {}, 'Could not load the evidence summary')).summary);

export const getEvidenceBrief = async (jobId, candidateId) =>
    camel((await call(`${cardUrl(jobId, candidateId)}/brief`, send('POST'), 'Could not write the evidence brief')).brief);
