/**
 * Job Service - API calls for job management
 * 
 * The backend uses snake_case field names (job_title, is_active, etc.)
 * The frontend uses camelCase (title, status, etc.)
 * Transform functions bridge the gap at the service boundary.
 */

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

/* ─────────────────────────────────────────────────────────────
 *  Transform: Backend (snake_case) ➜ Frontend (camelCase)
 * ───────────────────────────────────────────────────────────── */
const transformJobFromAPI = (job) => ({
    id:              job.id,
    title:           job.job_title,
    description:     job.job_description,
    requirements:    job.required_skills    || [],
    preferredSkills: job.preferred_skills   || [],
    experienceLevel: job.experience_level,
    employmentType:  job.employment_type,
    location:        job.location,
    status:          job.is_active ? 'Active' : 'Closed',
    totalCandidates: job.total_candidates   || 0,
    screened:        job.screened           || 0,
    shortlisted:     job.shortlisted       || 0,
    postedAt:        job.posted_at,
});

/* ─────────────────────────────────────────────────────────────
 *  Transform: Frontend (camelCase) ➜ Backend (snake_case)
 * ───────────────────────────────────────────────────────────── */
const transformJobToAPI = (job) => ({
    job_title:        job.title,
    job_description:  job.description,
    required_skills:  job.requirements    || [],
    preferred_skills: job.preferredSkills || [],
    experience_level: job.experienceLevel,
    employment_type:  job.employmentType,
    location:         job.location,
    is_active:        job.status !== 'Closed',    // default to active
});

/* ─────────────────────────────────────────────────────────────
 *  API calls — transforms applied at the boundary
 * ───────────────────────────────────────────────────────────── */

/** Fetch all jobs (GET /api/jobs) */
export const getJobs = async () => {
    const response = await fetch(`${API_BASE_URL}/api/jobs`);
    if (!response.ok) throw new Error('Failed to fetch jobs');
    const rawJobs = await response.json();
    return rawJobs.map(transformJobFromAPI);
};

/** Fetch a single job by ID (GET /api/jobs/:id) */
export const getJob = async (jobId) => {
    const response = await fetch(`${API_BASE_URL}/api/jobs/${jobId}`);
    if (!response.ok) throw new Error('Failed to fetch job');
    const rawJob = await response.json();
    return transformJobFromAPI(rawJob);
};

/** Create a new job (POST /api/jobs) */
export const createJob = async (jobData) => {
    const response = await fetch(`${API_BASE_URL}/api/jobs`, {
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
    const response = await fetch(`${API_BASE_URL}/api/jobs/${jobId}`, {
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
    const response = await fetch(`${API_BASE_URL}/api/jobs/${jobId}`, {
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
    const response = await fetch(`${API_BASE_URL}/api/v1/jobs/${jobId}/candidates`);
    if (!response.ok) throw new Error('Failed to fetch candidates');
    const data = await response.json();
    // Backend returns { job_id, candidates: [...] }
    return (data.candidates || []).map(c => ({
        id:                 c.candidate_id,
        name:               c.name || 'Unknown',
        email:              c.email || '',
        phone:              c.phone || '',
        status:             c.status || 'Under Review',
        applicationDate:    c.application_date,
        jdMatchScore:       c.jd_match_score       || 0,
        verificationScore:  c.verification_score   || 0,
        scoreDetails:       c.score_details        || {},
        filename:           c.filename,
        verificationStatus: c.verification_status,
        skillMatches:       c.skill_matches        || [],
    }));
};

/** Upload resumes (POST /api/v1/jobs/:id/upload) */
export const uploadResumes = async (jobId, files) => {
    const formData = new FormData();
    Array.from(files).forEach(f => formData.append('files', f));
    const response = await fetch(`${API_BASE_URL}/api/v1/jobs/${jobId}/upload`, {
        method: 'POST',
        body: formData,
    });
    if (!response.ok) throw new Error('Upload failed');
    return response.json();
};

/** Update candidate status (PUT /api/v1/jobs/:jobId/candidates/:candidateId/status) */
export const updateCandidateStatus = async (jobId, candidateId, status) => {
    const response = await fetch(
        `${API_BASE_URL}/api/v1/jobs/${jobId}/candidates/${candidateId}/status`,
        {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ status }),
        }
    );
    if (!response.ok) throw new Error('Failed to update status');
    return response.json();
};
