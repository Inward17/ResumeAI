/**
 * Job Service - API calls for job management
 * 
 * The backend uses snake_case field names (job_title, is_active, etc.)
 * The frontend uses camelCase (title, status, etc.)
 * Transform functions bridge the gap at the service boundary.
 */

import { apiFetch } from './api';

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
    status: job.is_active ? 'Active' : 'Closed',
    totalCandidates: job.total_candidates || 0,
    screened: job.screened || 0,
    shortlisted: job.shortlisted || 0,
    postedAt: job.posted_at,
});

/* ─────────────────────────────────────────────────────────────
 *  Transform: Frontend (camelCase) ➜ Backend (snake_case)
 * ───────────────────────────────────────────────────────────── */
const transformJobToAPI = (job) => ({
    job_title: job.title,
    job_description: job.description,
    required_skills: job.requirements || [],
    preferred_skills: job.preferredSkills || [],
    experience_level: job.experienceLevel,
    employment_type: job.employmentType,
    location: job.location,
    is_active: job.status !== 'Closed',    // default to active
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
    return (data.candidates || []).map(c => ({
        id: c.candidate_id,
        name: c.name || 'Unknown',
        email: c.email || '',
        phone: c.phone || '',
        status: c.status || 'Under Review',
        applicationDate: c.application_date,
        jdMatchScore: c.jd_match_score || 0,
        verificationScore: c.verification_score || 0,
        scoreDetails: c.score_details || {},
        filename: c.filename,
        verificationStatus: c.verification_status,
        skillMatches: c.skill_matches || [],
    }));
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
    if (!response.ok) throw new Error('Failed to update status');
    return response.json();
};

/** Fetch AI-generated interview questions (GET /api/jobs/:jobId/candidates/:candidateId/interview-questions) */
export const getInterviewQuestions = async (jobId, candidateId) => {
    const response = await apiFetch(
        `/api/jobs/${jobId}/candidates/${candidateId}/interview-questions`
    );
    if (!response.ok) throw new Error('Failed to fetch interview questions');
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
    if (!response.ok) throw new Error('Fact check request failed');
    return response.json();
};
