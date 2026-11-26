/**
 * Job Service - API calls for job management
 * 
 * The backend uses snake_case field names (job_title, is_active, etc.)
 * The frontend uses camelCase (title, status, etc.)
 * Transform functions bridge the gap at the service boundary.
 */

import { apiFetch } from './api';
import { normalizeStatus } from '../lib/statuses';

/* ─────────────────────────────────────────────────────────────
 *  Transform: Backend (snake_case) ➜ Frontend (camelCase)
 * ───────────────────────────────────────────────────────────── */
const transformJobFromAPI = (job) => ({
    id: job.id,
    title: job.job_title,
    description: job.job_description,
    requirements: job.required_skills || [],
    preferredSkills: job.preferred_skills || [],
    experienceLevel: job.experience_level,
    employmentType: job.employment_type,
    location: job.location,
    department: job.department || '',
    salaryMin: job.salary_min ?? null,
    salaryMax: job.salary_max ?? null,
    // Older backends only send is_active
    status: job.status || (job.is_active ? 'Active' : 'Closed'),
    totalCandidates: job.total_candidates || 0,
    screened: job.screened || 0,
    shortlisted: job.shortlisted || 0,
    postedAt: job.posted_at,
});

/* ─────────────────────────────────────────────────────────────
 *  Transform: Frontend (camelCase) ➜ Backend (snake_case)
 * ───────────────────────────────────────────────────────────── */
const toNumberOrNull = (v) => (v === '' || v === null || v === undefined || Number.isNaN(Number(v)) ? null : Number(v));

const transformJobToAPI = (job) => ({
    job_title: job.title,
    job_description: job.description,
    required_skills: job.requirements || [],
    preferred_skills: job.preferredSkills || [],
    experience_level: job.experienceLevel || null,
    employment_type: job.employmentType || null,
    location: job.location || null,
    department: job.department || null,
    salary_min: toNumberOrNull(job.salaryMin),
    salary_max: toNumberOrNull(job.salaryMax),
    status: job.status || 'Active',
    is_active: (job.status || 'Active') === 'Active',
});

/* ─────────────────────────────────────────────────────────────
 *  API calls — transforms applied at the boundary
 * ───────────────────────────────────────────────────────────── */

/** Fetch all jobs (GET /api/jobs) — candidate counts are computed by the backend */
export const getJobs = async () => {
    const response = await apiFetch('/api/jobs');
    if (!response.ok) throw new Error('Failed to fetch jobs');
    const rawJobs = await response.json();
    return rawJobs.map(transformJobFromAPI);
};

/** Fetch a single job by ID (GET /api/jobs/:id) */
export const getJob = async (jobId) => {
    const response = await apiFetch(`/api/jobs/${jobId}`);
    if (!response.ok) throw new Error('Failed to fetch job');
    return transformJobFromAPI(await response.json());
};

/** Create a new job (POST /api/jobs) */
export const createJob = async (jobData) => {
    const response = await apiFetch('/api/jobs', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(transformJobToAPI(jobData)),
    });
    if (!response.ok) {
        const err = await response.json().catch(() => ({}));
        throw new Error(err.detail || 'Failed to create job');
    }
    const rawJob = await response.json();
    return transformJobFromAPI(rawJob);
};

/** Update an existing job (PUT /api/jobs/:id) */
export const updateJob = async (jobId, jobData) => {
    const response = await apiFetch(`/api/jobs/${jobId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(transformJobToAPI(jobData)),
    });
    if (!response.ok) {
        const err = await response.json().catch(() => ({}));
        throw new Error(err.detail || 'Failed to update job');
    }
    const rawJob = await response.json();
    return transformJobFromAPI(rawJob);
};

/** Delete a job (DELETE /api/jobs/:id) */
export const deleteJob = async (jobId) => {
    const response = await apiFetch(`/api/jobs/${jobId}`, {
        method: 'DELETE',
    });
    if (!response.ok) throw new Error('Failed to delete job');
    return response.json();
};

/* ─────────────────────────────────────────────────────────────
 *  Candidate API calls
 *  These live under /api/v1/jobs (different prefix from jobs CRUD)
 * ───────────────────────────────────────────────────────────── */

/** Fetch candidates for a job (GET /api/v1/jobs/:id/candidates) */
export const getJobCandidates = async (jobId) => {
    const response = await apiFetch(`/api/v1/jobs/${jobId}/candidates`);
    if (!response.ok) throw new Error('Failed to fetch candidates');
    const data = await response.json();
    // Backend returns { job_id, candidates: [...] }
    return (data.candidates || []).map(transformCandidateFromAPI);
};

const pct = (v) => Math.max(0, Math.min(100, Math.round(Number(v) || 0)));
const strings = (v) => (Array.isArray(v) ? v.filter(Boolean).map(String) : []);

const transformCandidateFromAPI = (c) => ({
    id: c.candidate_id,
    name: c.name || 'Unknown candidate',
    email: c.email || '',
    phone: c.phone || '',
    status: normalizeStatus(c.status),
    applicationDate: c.application_date,
    // All scores are 0–100
    jdMatchScore: c.jd_match_score == null ? null : pct(c.jd_match_score),
    githubScore: c.github_score == null ? null : pct(c.github_score),
    // null = no source could be checked (shown as "—", not 0%)
    verificationScore: c.verification_score == null ? null : pct(c.verification_score),
    interviewScore: c.interview_score == null ? null : pct(c.interview_score),
    interviewedAt: c.interviewed_at || null,
    scoreDetails: c.score_details || {},
    filename: c.filename,
    verificationStatus: c.verification_status
        ? { ...c.verification_status, discrepancies: (c.verification_status.discrepancies || []).map(transformDiscrepancy).filter(Boolean) }
        : null,
    skillMatches: c.skill_matches || [],
    skills: strings(c.skills),
    education: strings(c.education),
    experience: strings(c.experience),
    githubUrl: c.github_url || null,
    linkedinUrl: c.linkedin_url || null,
    hasCoverLetter: !!c.has_cover_letter,
    codingProfiles: Array.isArray(c.coding_profiles) ? c.coding_profiles.map(transformCodingProfile) : [],
    portfolios: Array.isArray(c.portfolios) ? c.portfolios.map(transformPortfolio) : [],
    portfolioSkillEvidence: Array.isArray(c.portfolio_skill_evidence)
        ? c.portfolio_skill_evidence.filter((e) => e && e.skill).map((e) => ({ skill: String(e.skill), sources: strings(e.sources) }))
        : [],
});

// Fields are already camelCase (verification model); LinkedIn's actual value is linkedinValue
const transformDiscrepancy = (d) => {
    if (!d || typeof d !== 'object') return null;
    const description = d.description || d.field;
    if (!description) return null;
    return {
        field: d.field || null,
        source: d.source || null,
        severity: d.severity || 'minor',
        description: String(description),
        resumeValue: d.resumeValue ?? null,
        actualValue: d.actualValue ?? d.linkedinValue ?? null,
    };
};

const numOrNull = (v) => (v == null || Number.isNaN(Number(v)) ? null : Number(v));

const transformCodingProfile = (p) => ({
    platform: p.platform,
    handle: p.handle,
    // Built by the backend from a validated handle; https only
    profileUrl: typeof p.profile_url === 'string' && p.profile_url.startsWith('https://') ? p.profile_url : null,
    status: p.status || 'pending',
    name: p.name || null,
    rating: numOrNull(p.rating),
    maxRating: numOrNull(p.max_rating),
    title: p.title || null,
    maxTitle: p.max_title || null,
    stars: numOrNull(p.stars),
    problemsSolved: numOrNull(p.problems_solved),
    contests: numOrNull(p.contests),
    issues: strings(p.issues),
});

const httpsOrNull = (url) => (typeof url === 'string' && url.startsWith('https://') ? url : null);
const counts = (o) => (o && typeof o === 'object'
    ? Object.fromEntries(Object.entries(o).filter(([, v]) => numOrNull(v) != null).map(([k, v]) => [k, numOrNull(v)]))
    : {});

// Behance, Dribbble, personal website, Kaggle, Stack Overflow. All text is candidate-controlled: render as plain text.
const transformPortfolio = (p) => ({
    platform: p.platform,
    handle: p.handle,
    // Built by the backend from a validated handle or URL; https only
    profileUrl: httpsOrNull(p.profile_url),
    status: p.status || 'pending',
    name: p.name || null,
    headline: p.headline || null,
    followers: numOrNull(p.followers),
    appreciations: numOrNull(p.appreciations),
    reputation: numOrNull(p.reputation),
    badges: counts(p.badges),
    topTags: strings(p.top_tags),
    tiers: p.tiers && typeof p.tiers === 'object'
        ? Object.fromEntries(Object.entries(p.tiers).filter(([, v]) => typeof v === 'string'))
        : {},
    medals: counts(p.medals),
    competitions: numOrNull(p.competitions),
    projects: (Array.isArray(p.projects) ? p.projects : [])
        .filter((pr) => pr && pr.title)
        .map((pr) => ({ title: String(pr.title), tools: strings(pr.tools), dates: pr.dates || null, url: httpsOrNull(pr.url) })),
    skills: strings(p.skills),
    issues: strings(p.issues),
    note: p.note || null,
});

/** One candidate of a job (the list endpoint is the only candidate source) */
export const getJobCandidate = async (jobId, candidateId) => {
    const candidates = await getJobCandidates(jobId);
    const candidate = candidates.find(c => c.id === candidateId);
    if (!candidate) throw new Error('Candidate not found for this job');
    return candidate;
};

const UPLOAD_BATCH_SIZE = 10;

/**
 * Upload resumes (POST /api/v1/jobs/:id/upload).
 * Sent in small batches so large selections (50-100+ files) stay under
 * request-size limits of proxies/hosts; onProgress(uploaded, total) after each batch.
 */
export const uploadResumes = async (jobId, files, onProgress) => {
    const list = Array.from(files);
    const saved = [];
    for (let i = 0; i < list.length; i += UPLOAD_BATCH_SIZE) {
        const formData = new FormData();
        list.slice(i, i + UPLOAD_BATCH_SIZE).forEach(f => formData.append('files', f));
        const response = await apiFetch(`/api/v1/jobs/${jobId}/upload`, {
            method: 'POST',
            body: formData,
        });
        if (!response.ok) {
            const err = await response.json().catch(() => ({}));
            throw new Error(err.detail || `Upload failed after ${saved.length} of ${list.length} files`);
        }
        const data = await response.json();
        saved.push(...(data.saved || []));
        if (onProgress) onProgress(saved.length, list.length);
    }
    return { status: 'accepted', saved };
};

/** Resume processing progress (GET /api/v1/jobs/:id/tasks) */
export const getJobTasks = async (jobId) => {
    const response = await apiFetch(`/api/v1/jobs/${jobId}/tasks`);
    if (!response.ok) throw new Error('Failed to fetch processing status');
    return response.json();
};

/** Update candidate status (PUT /api/v1/jobs/:jobId/candidates/:candidateId/status) */
export const updateCandidateStatus = async (jobId, candidateId, status) => {
    const response = await apiFetch(
        `/api/v1/jobs/${jobId}/candidates/${candidateId}/status`,
        {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ status }),
        }
    );
    if (!response.ok) {
        const err = await response.json().catch(() => ({}));
        throw new Error(err.detail || 'Failed to update status');
    }
    return response.json();
};

/**
 * Fetch AI-generated interview questions (GET /api/jobs/:jobId/candidates/:candidateId/interview-questions).
 * The result's `stale` is true when the cover letter changed after the questions were made;
 * regenerate=true makes new ones (one AI call).
 */
export const getInterviewQuestions = async (jobId, candidateId, regenerate = false) => {
    const response = await apiFetch(
        `/api/jobs/${jobId}/candidates/${candidateId}/interview-questions${regenerate ? '?regenerate=true' : ''}`
    );
    if (!response.ok) {
        const err = await response.json().catch(() => ({}));
        throw new Error(err.detail || 'Failed to fetch interview questions');
    }
    return response.json();
};

/** Submit interview evaluation (POST /api/jobs/:jobId/candidates/:candidateId/evaluation) */
export const submitEvaluation = async (jobId, candidateId, evaluationData) => {
    const response = await apiFetch(
        `/api/jobs/${jobId}/candidates/${candidateId}/evaluation`,
        {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(evaluationData),
        }
    );
    if (!response.ok) throw new Error('Failed to submit evaluation');
    return response.json();
};

/** The last submitted evaluation, or null (GET /api/jobs/:jobId/candidates/:candidateId/evaluation) */
export const getEvaluation = async (jobId, candidateId) => {
    const response = await apiFetch(`/api/jobs/${jobId}/candidates/${candidateId}/evaluation`);
    if (response.status === 404) return null;
    if (!response.ok) throw new Error('Failed to fetch evaluation');
    return (await response.json()).evaluation;
};

/** AI Fact Checker (POST /api/fact-checker/:candidateId) */
export const factCheck = async (candidateId, message, candidateName) => {
    const response = await apiFetch(
        `/api/fact-checker/${candidateId}`,
        {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message, candidate_name: candidateName }),
        }
    );
    if (!response.ok) {
        const err = await response.json().catch(() => ({}));
        throw new Error(err.detail || 'Something went wrong while checking that claim. Please try again.');
    }
    return response.json();
};

/** Write a job description with AI (POST /api/jobs/generate-description); nothing is saved */
export const generateJobDescription = async ({ title, seniority, location, employmentType, notes, mustHaveSkills, tone }) => {
    const response = await apiFetch('/api/jobs/generate-description', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            job_title: title,
            seniority: seniority || null,
            location: location || null,
            employment_type: employmentType || null,
            notes: notes || null,
            must_have_skills: mustHaveSkills || [],
            tone: tone || 'neutral',
        }),
    });
    if (!response.ok) {
        const err = await response.json().catch(() => ({}));
        // 422 detail is a list of field errors
        const detail = Array.isArray(err.detail) ? `Check the inputs: ${err.detail[0]?.msg || 'invalid value'}` : err.detail;
        throw new Error(detail || 'Could not write the job description. Please try again.');
    }
    const d = await response.json();
    return {
        description: d.job_description,
        requiredSkills: d.required_skills || [],
        preferredSkills: d.preferred_skills || [],
        inclusiveLanguageNotes: d.inclusive_language_notes || [],
    };
};

/* ─────────────────────────────────────────────────────────────
 *  Cover letter of one application (/api/v1/jobs/:jobId/candidates/:candidateId/cover-letter)
 * ───────────────────────────────────────────────────────────── */

const transformCoverLetter = (l) => (l ? {
    text: l.text || '',
    truncated: !!l.truncated,
    source: l.source,
    filename: l.filename || null,
    uploadedAt: l.uploaded_at,
    analysisStatus: l.analysis_status,
    analysisError: l.analysis_error || null,
    analysis: l.analysis ? {
        summary: l.analysis.summary || '',
        fit: {
            specificity: l.analysis.fit?.specificity || null,
            addressesRole: l.analysis.fit?.addresses_role ?? null,
            requirementsAddressed: strings(l.analysis.fit?.requirements_addressed),
            notes: l.analysis.fit?.notes || '',
        },
        contradictions: (l.analysis.contradictions || []).map((c) => ({
            topic: c.topic, letterClaim: c.letter_claim, resumeSays: c.resume_says, severity: c.severity,
        })),
        probePoints: strings(l.analysis.probe_points),
    } : null,
} : null);

const coverLetterUrl = (jobId, candidateId) => `/api/v1/jobs/${jobId}/candidates/${candidateId}/cover-letter`;

const coverLetterRequest = async (path, options, fallback) => {
    const response = await apiFetch(path, options);
    if (!response.ok) {
        const err = await response.json().catch(() => ({}));
        throw new Error(err.detail || fallback);
    }
    return transformCoverLetter((await response.json()).cover_letter);
};

export const getCoverLetter = (jobId, candidateId) =>
    coverLetterRequest(coverLetterUrl(jobId, candidateId), {}, 'Could not load the cover letter');

/** Attach a file (File) or pasted text (string); replaces any existing letter */
export const attachCoverLetter = (jobId, candidateId, fileOrText) => {
    let options;
    if (typeof fileOrText === 'string') {
        options = { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ text: fileOrText }) };
    } else {
        const formData = new FormData();
        formData.append('file', fileOrText);
        options = { method: 'POST', body: formData };
    }
    return coverLetterRequest(coverLetterUrl(jobId, candidateId), options, 'Could not attach the cover letter');
};

export const retryCoverLetterAnalysis = (jobId, candidateId) =>
    coverLetterRequest(`${coverLetterUrl(jobId, candidateId)}/analysis`, { method: 'POST' }, 'Could not analyse the cover letter');

export const deleteCoverLetter = async (jobId, candidateId) => {
    const response = await apiFetch(coverLetterUrl(jobId, candidateId), { method: 'DELETE' });
    if (!response.ok) throw new Error('Could not remove the cover letter');
};

/* ─────────────────────────────────────────────────────────────
 *  Project reviews (deployed projects visited and rated by AI on demand)
 *  All text is candidate- or model-controlled: render as plain text.
 * ───────────────────────────────────────────────────────────── */
// Project links were validated by the backend (public http/https only); nothing else is used as an href
const webUrlOrNull = (url) => (typeof url === 'string' && /^https?:\/\//i.test(url) ? url : null);
const verdict = (v, key) => (v && typeof v === 'object' ? { verdict: String(v.verdict || ''), text: String(v[key] || '') } : null);

const transformProjectReview = (r) => {
    if (!r || typeof r !== 'object') return null;
    const ratings = r.ratings && typeof r.ratings === 'object' ? r.ratings : {};
    return {
        whatItDoes: String(r.what_it_does || ''),
        live: verdict(r.live_and_working, 'reason'),
        matchesClaim: verdict(r.matches_claim, 'details'),
        ownership: verdict(r.ownership_evidence, 'details'),
        ratings: ['working', 'polish', 'technical_depth', 'originality']
            .filter((k) => ratings[k])
            .map((k) => ({ key: k, score: numOrNull(ratings[k].score), reason: String(ratings[k].reason || '') })),
        redFlags: strings(r.red_flags),
        interviewQuestions: strings(r.interview_questions),
        jobRelevance: r.job_relevance ? { score: numOrNull(r.job_relevance.score), reason: String(r.job_relevance.reason || '') } : null,
        overall: r.overall ? { score: numOrNull(r.overall.score), justification: String(r.overall.justification || '') } : null,
    };
};

const transformProject = (p) => ({
    id: String(p.id),
    url: webUrlOrNull(p.url),
    name: String(p.name || ''),
    sourceLabel: String(p.source_label || 'Resume'),
    mention: String(p.mention || ''),
    reviewable: Boolean(p.reviewable),
    note: p.note || null,
    selected: Boolean(p.selected),
    state: p.state || null,
    siteStatus: p.site_status || null,
    siteNote: p.site_note || null,
    pages: (Array.isArray(p.pages) ? p.pages : []).map((pg) => ({ url: webUrlOrNull(pg.url), title: pg.title || '', failed: Boolean(pg.failed) })),
    // Only our own stored JPEG thumbnail, as a data URL
    screenshot: typeof p.screenshot === 'string' && p.screenshot.startsWith('data:image/jpeg;base64,') ? p.screenshot : null,
    screenshotNote: p.screenshot_note || null,
    review: transformProjectReview(p.review),
    reviewStatus: p.review_status || null,
    reviewNote: p.review_note || null,
});

/** Discovered projects and the latest review (GET /api/v1/jobs/:jobId/candidates/:candidateId/project-reviews) */
export const getProjectReviews = async (jobId, candidateId) => {
    const response = await apiFetch(`/api/v1/jobs/${jobId}/candidates/${candidateId}/project-reviews`);
    if (!response.ok) throw new Error('Could not load project reviews');
    const d = await response.json();
    return {
        firecrawlConfigured: Boolean(d.firecrawl_configured),
        maxProjects: numOrNull(d.max_projects) ?? 3,
        maxPages: numOrNull(d.max_pages) ?? 3,
        projects: (Array.isArray(d.projects) ? d.projects : []).map(transformProject),
        review: d.review ? {
            status: d.review.status,
            error: d.review.error || null,
            requestedBy: d.review.requested_by || null,
            requestedAt: d.review.requested_at || null,
            reviewedAt: d.review.reviewed_at || null,
            otherJob: Boolean(d.review.other_job),
            projects: (Array.isArray(d.review.projects) ? d.review.projects : []).map(transformProject),
        } : null,
        discrepancies: (Array.isArray(d.discrepancies) ? d.discrepancies : []).map(transformDiscrepancy).filter(Boolean),
    };
};

/** Start a review, or with retry re-run only the AI step (POST .../project-reviews) */
export const startProjectReviews = async (jobId, candidateId, { retry = false } = {}) => {
    const response = await apiFetch(
        `/api/v1/jobs/${jobId}/candidates/${candidateId}/project-reviews${retry ? '?retry=true' : ''}`,
        { method: 'POST' },
    );
    if (!response.ok) {
        const err = await response.json().catch(() => ({}));
        throw new Error(err.detail || 'Could not start the project review');
    }
    return response.json();
};
