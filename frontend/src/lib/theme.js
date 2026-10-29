/**
 * Light / dark / system theme, stored per browser.
 * index.html applies the saved choice before first paint; this keeps it in sync afterwards.
 */
import { useEffect, useState } from 'react';

const KEY = 'resumeai.theme';
export const THEMES = ['system', 'light', 'dark'];

const media = () => window.matchMedia('(prefers-color-scheme: dark)');

const read = () => {
  try {
    return localStorage.getItem(KEY) || 'system';
  } catch {
    return 'system';
  }
};

const apply = (theme) => {
  const dark = theme === 'dark' || (theme === 'system' && media().matches);
  document.documentElement.classList.toggle('dark', dark);
};

export const useTheme = () => {
  const [theme, setThemeState] = useState(read);

  useEffect(() => {
    apply(theme);
    if (theme !== 'system') return undefined;
    const mq = media();
    const onChange = () => apply('system');
    mq.addEventListener('change', onChange);
    return () => mq.removeEventListener('change', onChange);
  }, [theme]);

  // Other mounted toggles (sidebar, settings) follow changes made elsewhere
  useEffect(() => {
    const onSync = (e) => setThemeState(e.detail);
    window.addEventListener('resumeai:theme', onSync);
    return () => window.removeEventListener('resumeai:theme', onSync);
  }, []);

  const setTheme = (next) => {
    try { localStorage.setItem(KEY, next); } catch { /* private mode: still applies for this session */ }
    window.dispatchEvent(new CustomEvent('resumeai:theme', { detail: next }));
  };

  return { theme, setTheme };
};
