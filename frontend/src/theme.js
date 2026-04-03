/**
 * RESUMEAI — Shared Design Tokens (JS)
 *
 * These values are read at runtime from the CSS custom properties defined in theme.css.
 * To change colors across the whole app, edit theme.css — this file just bridges CSS → JS.
 *
 * Usage in components:
 *   import { C } from '../theme';
 *   style={{ color: C.primary }}
 */

/* Helper: reads a CSS variable from :root at runtime */
const css = (varName) => {
  if (typeof window !== 'undefined') {
    return getComputedStyle(document.documentElement)
      .getPropertyValue(varName)
      .trim();
  }
  return '';
};

/**
 * Main color token map — matches the CSS variables in theme.css.
 * Used as `style={{ background: C.primary }}` in JSX inline styles.
 */
export const C = {
  /* Brand */
  primary:           'var(--color-primary)',
  primaryDark:       'var(--color-primary-dark)',
  primaryContainer:  'var(--color-primary-container)',
  primaryLight:      'var(--color-primary-light)',
  accent:            'var(--color-accent)',
  accentLight:       'var(--color-accent-light)',
  cyan:              'var(--color-cyan)',
  cyanDim:           'var(--color-cyan-dim)',
  cyanBg:            'var(--color-cyan-bg)',
  cyanText:          'var(--color-cyan-text)',

  /* Surfaces */
  surface:           'var(--color-surface)',
  surfaceLow:        'var(--color-surface-low)',
  surfaceContainer:  'var(--color-surface-container)',
  surfaceHigh:       'var(--color-surface-high)',
  surfaceHighest:    'var(--color-surface-highest)',
  white:             'var(--color-surface-white)',
  sidebarBg:         'var(--color-sidebar-bg)',
  pageGray:          'var(--color-surface-low)',  /* alias used in many components */

  /* Text */
  textPrimary:       'var(--color-text-primary)',
  textSecondary:     'var(--color-text-secondary)',
  textMuted:         'var(--color-text-muted)',
  textFaint:         'var(--color-text-faint)',
  textOnPrimary:     'var(--color-text-on-primary)',

  /* Status */
  success:           'var(--color-success)',
  successBg:         'var(--color-success-bg)',
  warning:           'var(--color-warning)',
  warningBg:         'var(--color-warning-bg)',
  error:             'var(--color-error)',
  errorBg:           'var(--color-error-bg)',
  info:              'var(--color-info)',
  infoBg:            'var(--color-info-bg)',

  /* Borders */
  border:            'var(--color-border)',
  borderFaint:       'var(--color-border-faint)',

  /* Gradients */
  gradientPrimary:   'var(--gradient-primary)',
  gradientAccent:    'var(--gradient-accent)',
};

/**
 * Font family tokens
 */
export const FONTS = {
  display: 'var(--font-display)',
  body:    'var(--font-body)',
  label:   'var(--font-label)',
};

/**
 * Shadow tokens
 */
export const SHADOWS = {
  sm: 'var(--shadow-sm)',
  md: 'var(--shadow-md)',
  lg: 'var(--shadow-lg)',
  xl: 'var(--shadow-xl)',
};

export default C;
