// Tiny client for the SiteGuard API. Each website runs on its own port, so each keeps its own sign-in in its own browser storage.
export const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:4000';
const KEY = 'siteguard.session';

export const session = {
  get() { try { return JSON.parse(localStorage.getItem(KEY)); } catch { return null; } },
  set(value) { try { localStorage.setItem(KEY, JSON.stringify(value)); } catch { /* storage blocked: the sign-in just will not be remembered */ } },
  clear() { try { localStorage.removeItem(KEY); } catch { /* ignore */ } },
};

export async function api(path, { method = 'GET', body } = {}) {
  const current = session.get();
  const res = await fetch(API_BASE + path, {
    method,
    headers: { 'content-type': 'application/json', ...(current?.token ? { authorization: `Bearer ${current.token}` } : {}) },
    body: body ? JSON.stringify(body) : undefined,
  });
  const data = await res.json().catch(() => ({}));
  if (res.status === 401 && current) {
    session.clear();
    window.dispatchEvent(new Event('siteguard:signout'));
  }
  if (!res.ok) throw new Error(data.error || `Request failed (${res.status})`);
  return data;
}

// Downloads a file the API protects with the sign-in (a PDF, for example) and saves it under the given name.
export async function download(path, filename) {
  const current = session.get();
  const res = await fetch(API_BASE + path, { headers: current?.token ? { authorization: `Bearer ${current.token}` } : {} });
  if (!res.ok) { const data = await res.json().catch(() => ({})); throw new Error(data.error || `Download failed (${res.status})`); }
  const url = URL.createObjectURL(await res.blob());
  const a = document.createElement('a'); a.href = url; a.download = filename; document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 5000);
}

export const evidenceUrl = (p) => (p ? (p.startsWith('http') ? p : API_BASE + p) : '');
