/**
 * Candidate application statuses — the same list the backend accepts.
 * Every screen (pipeline, dossier, interviews) uses this one list.
 */
export const CANDIDATE_STATUSES = ['Under Review', 'Shortlisted', 'Interview', 'Offer', 'Hired', 'Rejected'];

/** Statuses shown on the Interviews page */
export const INTERVIEW_STATUSES = ['Shortlisted', 'Interview'];

export const STATUS_STYLES = {
  'Under Review': 'bg-amber-50 text-amber-800 ring-amber-200',
  Shortlisted: 'bg-indigo-50 text-indigo-800 ring-indigo-200',
  Interview: 'bg-emerald-50 text-emerald-800 ring-emerald-200',
  Offer: 'bg-sky-50 text-sky-800 ring-sky-200',
  Hired: 'bg-green-50 text-green-800 ring-green-200',
  Rejected: 'bg-red-50 text-red-700 ring-red-200',
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
  Active: 'bg-cyan-50 text-cyan-800 ring-cyan-200',
  Draft: 'bg-amber-50 text-amber-800 ring-amber-200',
  Closed: 'bg-slate-100 text-slate-600 ring-slate-200',
};
