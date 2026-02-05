/**
 * Job Service - API calls for job management
 */

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

/**
 * Fetch all jobs
 */
export const getJobs = async () => {
    const response = await fetch(`${API_BASE_URL}/api/jobs`);
    if (!response.ok) {
        throw new Error('Failed to fetch jobs');
    }
    return response.json();
};

/**
 * Fetch a single job by ID
 */
export const getJob = async (jobId) => {
    const response = await fetch(`${API_BASE_URL}/api/jobs/${jobId}`);
    if (!response.ok) {
        throw new Error('Failed to fetch job');
    }
    return response.json();
};

/**
 * Create a new job
 */
export const createJob = async (jobData) => {
    const response = await fetch(`${API_BASE_URL}/api/jobs`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(jobData),
    });
    if (!response.ok) {
        throw new Error('Failed to create job');
    }
    return response.json();
};

/**
 * Update an existing job
 */
export const updateJob = async (jobId, jobData) => {
    const response = await fetch(`${API_BASE_URL}/api/jobs/${jobId}`, {
        method: 'PUT',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(jobData),
    });
    if (!response.ok) {
        throw new Error('Failed to update job');
    }
    return response.json();
};

/**
 * Delete a job
 */
export const deleteJob = async (jobId) => {
    const response = await fetch(`${API_BASE_URL}/api/jobs/${jobId}`, {
        method: 'DELETE',
    });
    if (!response.ok) {
        throw new Error('Failed to delete job');
    }
    return response.json();
};

/**
 * Transform API job to frontend format
 */
export const transformJobFromAPI = (job) => ({
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

/**
 * Transform frontend job to API format
 */
export const transformJobToAPI = (job) => ({
    job_title: job.title,
    job_description: job.description,
    required_skills: job.requirements || [],
    preferred_skills: job.preferredSkills || [],
    experience_level: job.experienceLevel,
    employment_type: job.employmentType,
    location: job.location,
    is_active: job.status === 'Active',
});
