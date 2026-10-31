import { createContext, useContext, useEffect, useState } from 'react';
import { api, session } from './api.js';
import './theme.js';

const Ctx = createContext(null);
export const useAuth = () => useContext(Ctx);

const OTHER_SITE = {
  employee: 'This is the employee portal. Supervisors sign in at http://localhost:3002.',
  supervisor: 'This is the supervisor panel. Employees sign in at http://localhost:3001.',
};

// Normal sign-in. For a quick demo without typing, set VITE_AUTO_LOGIN=1 and each site signs itself in as a dummy account.

export function AuthProvider({ role, auto, children }) {
  const [user, setUser] = useState(() => {
    const saved = session.get()?.user;
    return saved && saved.role === role ? saved : null;
  });
  const autoOn = import.meta.env.VITE_AUTO_LOGIN === '1' && Array.isArray(auto);
  const [starting, setStarting] = useState(autoOn && !user);
  const login = async (employeeId, password) => {
    const result = await api('/api/auth/login', { method: 'POST', body: { employeeId, password } });
    if (result.user.role !== role) throw new Error(OTHER_SITE[role]);
    session.set(result);
    setUser(result.user);
  };
  const logout = () => { session.clear(); setUser(null); };
  useEffect(() => {
    const out = () => { setUser(null); if (autoOn) login(auto[0], auto[1]).catch(() => {}); };
    window.addEventListener('siteguard:signout', out);
    if (starting) login(auto[0], auto[1]).catch(() => {}).finally(() => setStarting(false));
    return () => window.removeEventListener('siteguard:signout', out);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  if (starting) return <p className="muted" style={{ padding: '2rem' }}>Starting…</p>;
  return <Ctx.Provider value={{ user, login, logout, role, autoOn }}>{children}</Ctx.Provider>;
}

// A new supervisor creates their own account, with the requirements of their own site, and is signed straight in. They start with an empty
// site of their own: they add their employees (with faces) after signing in, and see only that.
const GEAR = [['helmet', 'Helmet'], ['vest', 'Vest'], ['gloves', 'Gloves'], ['boots', 'Boots'], ['goggles', 'Goggles']];
function SignupForm({ onBack }) {
  const { login } = useAuth();
  const [f, setF] = useState({ name: '', siteName: '', conditionClass: '', fields: '', requiredItems: ['helmet', 'vest'], password: '', again: '' });
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const toggle = (k) => setF((x) => ({ ...x, requiredItems: x.requiredItems.includes(k) ? x.requiredItems.filter((y) => y !== k) : [...x.requiredItems, k] }));
  const submit = async (e) => {
    e.preventDefault(); setError('');
    if (f.password !== f.again) { setError('The two passwords are not the same.'); return; }
    setBusy(true);
    try {
      const made = await api('/api/auth/signup', { method: 'POST', body: { name: f.name, siteName: f.siteName, conditionClass: f.conditionClass, fields: f.fields, requiredItems: f.requiredItems, password: f.password } });
      try { window.sessionStorage.setItem('siteguard.welcome', JSON.stringify(made)); } catch { /* the welcome note is optional */ }
      await login(made.employeeId, f.password);
    } catch (err) { setError(err.message); setBusy(false); }
  };
  return (
    <form onSubmit={submit}>
      <h2 style={{ fontSize: '1.4rem' }}>Create a supervisor account</h2>
      <p className="muted">You get a site of your own. Tell us what your workers must wear, then add your employees and their faces after you sign in.</p>
      <div className="field"><label htmlFor="sn">Your name</label><input id="sn" value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} autoFocus style={{ width: '100%' }} /></div>
      <div className="field"><label htmlFor="ss">Your site or kind of work</label><input id="ss" value={f.siteName} onChange={(e) => setF({ ...f, siteName: e.target.value })} placeholder="e.g. Bridge construction, Wireman" style={{ width: '100%' }} /></div>
      <div className="field"><label>Gear every worker must wear (the requirements)</label>
        <div className="actions" style={{ marginTop: 0 }}>{GEAR.map(([k, label]) => <label key={k} className="inline"><input type="checkbox" checked={f.requiredItems.includes(k)} onChange={() => toggle(k)} />{label}</label>)}</div>
        <p className="small muted" style={{ margin: '.2rem 0 0' }}>Goggles, gloves and boots use a second model whose accuracy has not been measured.</p></div>
      <div className="field"><label htmlFor="sc">Conditions class (optional)</label><input id="sc" value={f.conditionClass} onChange={(e) => setF({ ...f, conditionClass: e.target.value })} placeholder="e.g. Class A: work at height" style={{ width: '100%' }} /></div>
      <div className="field"><label htmlFor="sf">Fields of your site, separated by commas (optional)</label><input id="sf" value={f.fields} onChange={(e) => setF({ ...f, fields: e.target.value })} placeholder="e.g. Block A, Block B, Foundation" style={{ width: '100%' }} /></div>
      <div className="field"><label htmlFor="sp">Password (6 or more characters)</label><input id="sp" type="password" value={f.password} onChange={(e) => setF({ ...f, password: e.target.value })} autoComplete="new-password" style={{ width: '100%' }} /></div>
      <div className="field"><label htmlFor="sp2">Password again</label><input id="sp2" type="password" value={f.again} onChange={(e) => setF({ ...f, again: e.target.value })} autoComplete="new-password" style={{ width: '100%' }} /></div>
      {error && <div className="err">{error}</div>}
      <button className="go" disabled={busy || !f.name || !f.siteName || !f.password || !f.requiredItems.length} style={{ width: '100%', padding: '.7rem' }}>{busy ? 'Creating…' : 'Create account and sign in'}</button>
      <p className="small" style={{ marginTop: '1rem' }}>Already have one? <button type="button" className="link" onClick={onBack}>Sign in</button></p>
    </form>
  );
}

export function Login({ title, subtitle, points, demo, demoNote = 'Dummy accounts: the code is the user name and the password is the code followed by @123, for example', signup = false }) {
  const { login } = useAuth();
  const [mode, setMode] = useState('in');
  const [id, setId] = useState('');
  const [pw, setPw] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const submit = async (e) => {
    e.preventDefault();
    setBusy(true); setError('');
    try { await login(id, pw); } catch (err) { setError(err.message); } finally { setBusy(false); }
  };
  return (
    <div className="auth">
      <div className="auth-art">
        <div className="brand"><span className="brand-mark"><svg viewBox="0 0 24 24"><path d="M4 17h16v2H4zM5 16a7 7 0 0 1 14 0zM11 5h2v4h-2z" /></svg></span><span>SiteGuard<small>{subtitle}</small></span></div>
        <div><h1>{title}</h1><p>Every catch is recorded with its picture, time and place, and checked by a person before it counts.</p></div>
        <ul>{points.map((p) => <li key={p}>{p}</li>)}</ul>
      </div>
      <div className="auth-form">
        {mode === 'up' ? <SignupForm onBack={() => setMode('in')} /> : (
        <form onSubmit={submit}>
          <h2 style={{ fontSize: '1.4rem' }}>Sign in</h2>
          <p className="muted">Enter your employee code and password.</p>
          <div className="field"><label htmlFor="id">Employee code</label><input id="id" value={id} onChange={(e) => setId(e.target.value)} autoFocus autoComplete="username" style={{ width: '100%' }} /></div>
          <div className="field"><label htmlFor="pw">Password</label><input id="pw" type="password" value={pw} onChange={(e) => setPw(e.target.value)} autoComplete="current-password" style={{ width: '100%' }} /></div>
          {error && <div className="err">{error}</div>}
          <button className="go" disabled={busy || !id || !pw} style={{ width: '100%', padding: '.7rem' }}>{busy ? 'Signing in…' : 'Sign in'}</button>
          <p className="small muted" style={{ marginTop: '1rem' }}><a href="/about">About accuracy and privacy</a></p>
          {signup && <p className="small" style={{ marginTop: '1rem' }}>New here? <button type="button" className="link" onClick={() => setMode('up')}>Create account</button></p>}
          {demo && <p className="small muted" style={{ marginTop: '1rem' }}>{demoNote} <span className="mono">{demo[0]}</span> and <span className="mono">{demo[1]}</span>. <button type="button" className="link" onClick={() => { setId(demo[0]); setPw(demo[1]); }}>Fill it in</button></p>}
        </form>
        )}
      </div>
    </div>
  );
}
