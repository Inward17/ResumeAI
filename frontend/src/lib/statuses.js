/**
 * Candidate application statuses — the same list the backend accepts.
 * Every screen (pipeline, dossier, interviews) uses this one list.
 */
export const CANDIDATE_STATUSES = ['Under Review', 'Shortlisted', 'Interview', 'Offer', 'Hired', 'Rejected'];

/** Statuses shown on the Interviews page */
export const INTERVIEW_STATUSES = ['Shortlisted', 'Interview'];

/** Dot colour per status (statuses render as a dot + label, not a filled pill) */
export const STATUS_STYLES = {
  'Under Review': 'bg-ink-3',
  Shortlisted: 'bg-primary',
  Interview: 'bg-info',
  Offer: 'bg-warning',
  Hired: 'bg-success',
  Rejected: 'bg-danger',
};

// Values written by older versions of the app
const LEGACY = {
  new: 'Under Review',
  reviewing: 'Under Review',
  'pending review': 'Under Review',
  'under review': 'Under Review',
  shortlisted: 'Shortlisted',
  interview: 'Interview',
  offer: 'Offer',
  hired: 'Hired',
  rejected: 'Rejected',
};

export const normalizeStatus = (status) =>
  LEGACY[String(status || '').trim().toLowerCase()] || 'Under Review';

export const JOB_STATUSES = ['Active', 'Draft', 'Closed'];

export const JOB_STATUS_STYLES = {
  Active: 'bg-success',
  Draft: 'bg-warning',
  Closed: 'bg-ink-3',
};
