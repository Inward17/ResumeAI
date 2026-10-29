/**
 * Per-browser preferences (stored in localStorage).
 * Scoring thresholds decide which candidates are highlighted as strong
 * matches and which are flagged for manual verification review.
 */
const KEY = 'resumeai.preferences';

export const DEFAULT_PREFERENCES = {
  matchThreshold: 75,         // Role match % considered a strong match
  verificationThreshold: 60,  // Below this, a candidate is flagged for review
};

export const loadPreferences = () => {
  try {
    return { ...DEFAULT_PREFERENCES, ...JSON.parse(localStorage.getItem(KEY) || '{}') };
  } catch {
    return { ...DEFAULT_PREFERENCES };
  }
};

export const savePreferences = (prefs) => {
  try {
    localStorage.setItem(KEY, JSON.stringify(prefs));
    return true;
  } catch {
    return false;
  }
};
