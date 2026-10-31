import { useState } from 'react';

// Light or dark theme. A choice made with the toggle is remembered in this browser; otherwise the computer's own setting is followed.
const KEY = 'siteguard.theme';
const stored = () => { try { return localStorage.getItem(KEY); } catch { return null; } };
const inBrowser = typeof document !== 'undefined';
const asked = () => (typeof location === 'undefined' ? null : new URLSearchParams(location.search).get('theme')); // ?theme=dark for a link or a demo
const preferred = () => (['light', 'dark'].includes(asked()) ? asked() : null) || stored() || (inBrowser && window.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
export const applyTheme = (theme) => { if (inBrowser) document.documentElement.dataset.theme = theme; };
applyTheme(preferred()); // runs once when the page loads, before anything is drawn

export function useTheme() {
  const [theme, setTheme] = useState(() => (inBrowser && document.documentElement.dataset.theme) || 'light');
  const toggle = () => {
    const next = theme === 'dark' ? 'light' : 'dark';
    applyTheme(next);
    try { localStorage.setItem(KEY, next); } catch { /* the choice just is not remembered */ }
    setTheme(next);
  };
  return [theme, toggle];
}

// A small message at the bottom of the screen. Any code can call toast('Saved.'); <Toasts /> (in the shell) shows it.
export const toast = (message) => inBrowser && window.dispatchEvent(new CustomEvent('siteguard:toast', { detail: String(message) }));
