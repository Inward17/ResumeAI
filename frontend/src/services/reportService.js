/** Hiring reports (backend: app/routes/reports.py). Responses come back camelCase. */
import { apiFetch } from './api';

const camelize = (v) => {
    if (Array.isArray(v)) return v.map(camelize);
    if (!v || typeof v !== 'object') return v;
    return Object.fromEntries(Object.entries(v).map(([k, x]) => [k.replace(/_([a-z0-9])/g, (_, c) => c.toUpperCase()), camelize(x)]));
};

// filters: { jobId, from, to, stuckDays }
const query = ({ jobId, from, to, stuckDays } = {}) => {
    const q = new URLSearchParams();
    if (jobId) q.set('job_id', jobId);
    if (from) q.set('from', from);
    if (to) q.set('to', to);
    if (stuckDays) q.set('stuck_days', stuckDays);
    return q;
};

const failure = async (response) => {
    const data = await response.json().catch(() => ({}));
    const detail = Array.isArray(data.detail) ? data.detail.map((d) => d.msg).join(', ') : data.detail;
    return new Error(detail || `Request failed (${response.status})`);
};

export const getReport = async (filters) => {
    const response = await apiFetch(`/api/reports/overview?${query(filters)}`);
    if (!response.ok) throw await failure(response);
    const data = await response.json();
    // Keys that are data (statuses like not_found, quota kinds) stay as sent
    return { ...camelize(data), aiUsage: data.ai_usage,
        screening: { ...camelize(data.screening), verificationSources: data.screening.verification_sources } };
};

/** Downloads one report section ('stuck' | 'jobs' | 'funnel') as a CSV file */
export const downloadReportCsv = async (report, filters) => {
    const q = query(filters);
    q.set('report', report);
    const response = await apiFetch(`/api/reports/export.csv?${q}`);
    if (!response.ok) throw await failure(response);
    const url = URL.createObjectURL(await response.blob());
    const a = document.createElement('a');
    a.href = url;
    a.download = `resumeai-${report}.csv`;
    a.click();
    URL.revokeObjectURL(url);
};
