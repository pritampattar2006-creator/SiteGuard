import { useCallback, useEffect, useState } from 'react';
import { NavLink } from 'react-router-dom';
import { api, download, evidenceUrl } from './api.js';
import { CommandPalette, Toasts } from './palette.jsx';
import { useTheme } from './theme.js';

// ---- icons (simple outlined set) -------------------------------------------------------------
const PATHS = {
  dashboard: 'M3 3h7v9H3zM14 3h7v5h-7zM14 12h7v9h-7zM3 16h7v5H3z',
  inbox: 'M22 12h-6l-2 3h-4l-2-3H2M5.5 5h13l3.5 7v6a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2v-6z',
  folder: 'M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z',
  shield: 'M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6z',
  users: 'M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM22 21v-2a4 4 0 0 0-3-3.9M16 3.1a4 4 0 0 1 0 7.8',
  face: 'M4 8V6a2 2 0 0 1 2-2h2M16 4h2a2 2 0 0 1 2 2v2M20 16v2a2 2 0 0 1-2 2h-2M8 20H6a2 2 0 0 1-2-2v-2M9 10v1M15 10v1M9 15c1.5 1.3 4.5 1.3 6 0',
  bell: 'M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9M10.3 21a1.94 1.94 0 0 0 3.4 0',
  wallet: 'M3 7a2 2 0 0 1 2-2h13v4M3 7v10a2 2 0 0 0 2 2h14a1 1 0 0 0 1-1v-9a1 1 0 0 0-1-1H5a2 2 0 0 1-2-2zM16 14h.01',
  logout: 'M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9',
  alert: 'M12 9v4M12 17h.01M10.3 3.9L1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z',
  check: 'M20 6L9 17l-5-5',
  clock: 'M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18zM12 7v5l3 2',
  chart: 'M3 3v18h18M7 15l4-4 3 3 5-6',
  camera: 'M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2zM12 17a4 4 0 1 0 0-8 4 4 0 0 0 0 8z',
  hardhat: 'M4 18h16M5 18v-2a7 7 0 0 1 14 0v2M12 6v4M9 8v2M15 8v2',
};
export const Icon = ({ name }) => (
  <svg viewBox="0 0 24 24" aria-hidden="true"><path d={PATHS[name] || PATHS.alert} /></svg>
);

// ---- small pieces ----------------------------------------------------------------------------
const HUES = ['#2563c9', '#138a52', '#b86e00', '#8a3ffc', '#d23b3b', '#0f8b9d', '#c2410c', '#475569'];
export function Avatar({ name = '?', size = 36, photo = '' }) {
  if (photo) return <img className="avatar" src={photo} alt={name} style={{ width: size, height: size, objectFit: 'cover' }} />;
  const initials = name.split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0].toUpperCase()).join('');
  const hue = HUES[[...name].reduce((s, c) => s + c.charCodeAt(0), 0) % HUES.length];
  return <span className="avatar" style={{ width: size, height: size, background: hue, fontSize: size * 0.38 }}>{initials}</span>;
}

const TONES = {
  'pending review': 'warn', proposed: 'warn', confirmed: 'bad', issued: 'bad', acknowledged: 'ok', paid: 'ok', resolved: 'ok', disputed: 'info', dismissed: '', waived: '',
};
export function Chip({ tone, children }) {
  return <span className={`chip ${tone ? `c-${tone}` : ''}`}>{children}</span>;
}
export const Stamp = ({ status }) => <Chip tone={TONES[String(status).toLowerCase()]}>{status}</Chip>;

export const Kpi = ({ icon, label, value, tone = '' }) => (
  <div className={`kpi ${tone}`}><span className="ic"><Icon name={icon} /></span><div><b>{value}</b><span>{label}</span></div></div>
);
export const PageHead = ({ title, sub, children }) => (
  <div className="head"><div><h1>{title}</h1>{sub && <p>{sub}</p>}</div>{children && <div className="actions" style={{ margin: 0 }}>{children}</div>}</div>
);

export const fmtDate = (iso) => (iso ? new Date(iso).toLocaleString([], { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' }) : '');
export const fmtDay = (iso) => (iso ? new Date(iso).toLocaleDateString([], { day: '2-digit', month: 'short', year: 'numeric' }) : '');
export const ticketNo = (n) => String(n || 0).padStart(5, '0');
export const money = (n, cur = 'INR') => `${cur === 'INR' ? '₹' : `${cur} `}${Number(n || 0).toLocaleString('en-IN')}`;
export const monthName = (key) => new Date(`${key}-01T00:00:00Z`).toLocaleDateString([], { month: 'long', year: 'numeric', timeZone: 'UTC' });
export const Err = ({ text }) => (text ? <div className="err">{text}</div> : null);

// Re-runs `fn` whenever `deps` change, and every `every` ms if given.
export function useLoad(fn, deps = [], every = 0) {
  const [state, setState] = useState({ data: null, error: '', loading: true });
  const run = useCallback(async () => {
    try { setState({ data: await fn(), error: '', loading: false }); }
    catch (e) { setState((s) => ({ ...s, error: e.message, loading: false })); }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  useEffect(() => {
    run();
    if (!every) return undefined;
    const t = setInterval(run, every);
    return () => clearInterval(t);
  }, [run, every]);
  return { ...state, reload: run };
}

export function Shell({ site, tag, nav, user, onLogout, topExtra, children }) {
  const [theme, toggleTheme] = useTheme();
  const today = new Date().toLocaleDateString([], { weekday: 'long', day: 'numeric', month: 'long' });
  return (
    <div className="app">
      <aside className="side">
        <div className="brand"><span className="brand-mark"><svg viewBox="0 0 24 24"><path d="M4 17h16v2H4zM5 16a7 7 0 0 1 14 0zM11 5h2v4h-2z" /></svg></span><span>{site}<small>{tag}</small></span></div>
        <nav className="nav">
          {nav.map((n) => (
            <NavLink key={n.to} to={n.to} end={n.to === '/'}><Icon name={n.icon} />{n.label}{n.count > 0 && <span className="badge-n">{n.count}</span>}</NavLink>
          ))}
        </nav>
        {user && (
          <div className="me"><Avatar name={user.name} size={34} /><div><b>{user.name}</b><small>{user.jobRole || user.employeeId}</small></div>
            {onLogout && <button onClick={onLogout} title="Sign out" aria-label="Sign out"><Icon name="logout" /></button>}</div>
        )}
      </aside>
      <div className="main">
        <div className="topbar"><b>{tag}</b><span className="sp" />{topExtra}<button className="alt sm no-print" onClick={() => window.dispatchEvent(new Event('siteguard:palette'))} title="Search pages and people (Ctrl+K)">Search <kbd>Ctrl K</kbd></button><button className="alt sm no-print" onClick={toggleTheme} aria-label={theme === 'dark' ? 'Switch to the light theme' : 'Switch to the dark theme'}>{theme === 'dark' ? 'Light' : 'Dark'}</button><span>{today}</span></div>
        <main className="page">{children}</main>
      </div>
      <CommandPalette nav={nav} user={user} theme={theme} onTheme={toggleTheme} onLogout={onLogout} />
      <Toasts />
    </div>
  );
}

const FAULT_WORDS = {
  HELMET: 'No safety helmet on the head', VEST: 'No high-visibility vest on the body', BOOTS: 'No safety boots on the feet',
  GLOVES: 'No safety gloves on the hands', GOGGLES: 'No safety goggles on the eyes', UNCLEAR: 'Could not be judged clearly: a supervisor must look at the picture',
};

// The exact fault in plain words, one line for each missing item.
export function FaultBox({ missing }) {
  const items = String(missing || '').split(/\s*[,+]\s*/).filter(Boolean).map((s) => s.trim().toUpperCase().replace(/^NO\s+/, ''));
  if (!items.length) return null;
  return (
    <div className="fault" role="note" style={{ border: '1px solid var(--bad, #b42318)', borderLeft: '5px solid var(--bad, #b42318)', background: 'rgba(180,35,24,.07)', borderRadius: 8, padding: '8px 12px', margin: '8px 0' }}>
      <div className="small" style={{ fontWeight: 700, letterSpacing: '.04em', color: 'var(--bad, #b42318)' }}>THE EXACT FAULT</div>
      <ul style={{ margin: '4px 0 0 18px', padding: 0 }}>{items.map((i) => <li key={i}><b>{FAULT_WORDS[i] || i}</b></li>)}</ul>
    </div>
  );
}

// Downloads the one-page violation notice (the fault and its pictures) as a PDF.
export function NoticeButton({ path, number, label = 'Download notice (PDF)' }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const go = async () => {
    setBusy(true); setError('');
    try { await download(path, `violation-notice-${String(number).padStart(5, '0')}.pdf`); } catch (e) { setError(e.message); }
    setBusy(false);
  };
  return <><button className="alt sm" disabled={busy} onClick={go}>{busy ? 'Preparing…' : label}</button>{error && <span className="small" style={{ color: 'var(--bad, #b42318)', marginLeft: 8 }}>{error}</span>}</>;
}

export function Evidence({ path, contextPath }) {
  const [open, setOpen] = useState('');
  const src = evidenceUrl(path);
  const whole = evidenceUrl(contextPath);
  if (!src) return <div className="case-img"><div className="none">No picture attached</div></div>;
  return (
    <>
      <div className="case-img" style={{ position: 'relative' }}>
        <img src={src} alt="The worker" onClick={() => setOpen(src)} />
        {whole && <button className="alt sm" style={{ position: 'absolute', left: 8, bottom: 8 }} onClick={() => setOpen(whole)}>Whole picture</button>}
      </div>
      {open && <div className="lightbox" onClick={() => setOpen('')}><img src={open} alt="Evidence, enlarged" /></div>}
    </>
  );
}

export function Thumb({ path }) {
  const [open, setOpen] = useState(false);
  const src = evidenceUrl(path);
  if (!src) return <span className="muted small">no picture</span>;
  return (
    <>
      <img className="thumb" src={src} alt="Evidence" onClick={() => setOpen(true)} />
      {open && <div className="lightbox" onClick={() => setOpen(false)}><img src={src} alt="Evidence, enlarged" /></div>}
    </>
  );
}

export const HazardBar = () => <div className="hazard" />;

export function Notifications() {
  const { data, error, loading } = useLoad(() => api('/api/notifications'), [], 15000);
  return (
    <>
      <PageHead title="Notifications" sub="Everything that needs your attention, newest first." />
      <Err text={error} />
      {loading ? <p className="muted">Loading…</p> : !data?.length ? <div className="empty">Nothing yet.</div> : (
        <div className="card">{data.map((n) => <p key={n._id} style={{ borderBottom: '1px solid var(--line)', paddingBottom: '.6rem' }}>{n.message}<br /><span className="small muted">{fmtDate(n.at)}</span></p>)}</div>
      )}
    </>
  );
}
