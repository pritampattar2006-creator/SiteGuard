import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { api, evidenceUrl } from '../../shared/api.js';
import { useAuth } from '../../shared/auth.jsx';
import { toast } from '../../shared/theme.js';
import { Chip, Err, PageHead, Stamp, Thumb, fmtDay, money, useLoad } from '../../shared/ui.jsx';

// ---- accident alarm ---------------------------------------------------------------------------
// A worker-down alert from the detector becomes an accident report. While one is open, a siren sounds in this panel and a red banner
// shows the report. The alarm stops when a supervisor acknowledges it. It says a worker is down, not why (a fall, a hit, or a medical event).
function useSiren(on) {
  const ctx = useRef(null);
  useEffect(() => {
    if (!on) return undefined;
    const Audio = window.AudioContext || window.webkitAudioContext;
    if (!Audio) return undefined;
    try { ctx.current = ctx.current || new Audio(); } catch { return undefined; }
    const ac = ctx.current;
    const resume = () => ac.state === 'suspended' && ac.resume().catch(() => {});
    resume();
    window.addEventListener('click', resume);
    const osc = ac.createOscillator(); const gain = ac.createGain();
    osc.type = 'square'; gain.gain.value = 0.06; osc.connect(gain); gain.connect(ac.destination); osc.start();
    let high = false;
    const t = setInterval(() => { high = !high; osc.frequency.setValueAtTime(high ? 900 : 620, ac.currentTime); }, 420);
    osc.frequency.value = 620;
    return () => { clearInterval(t); window.removeEventListener('click', resume); try { osc.stop(); osc.disconnect(); gain.disconnect(); } catch { /* already stopped */ } };
  }, [on]);
}

const what = (a) => (a.kind === 'OBJECT HIT WORKER' ? 'an object has hit a worker' : a.kind === 'OBJECT NEAR WORKER' ? 'an object is falling close to a worker' : `${a.employeeName ? `${a.employeeName} (${a.employeeCode})` : 'a worker (not identified)'} is down`);
export const accidentText = (a) => `ACCIDENT DETECTED at ${a.venue || 'the site'}: ${what(a)}. ${new Date(a.occurredAt).toLocaleString()}. ${a.detail || ''}`.trim();

export function AccidentWatcher({ onChanged }) {
  const open = useLoad(() => api('/api/accidents?status=Open'), [], 4000);
  const [muted, setMuted] = useState(false);
  const [busy, setBusy] = useState(false);
  const list = open.data || [];
  useSiren(list.length > 0 && !muted);
  useEffect(() => { if (list.length) setMuted(false); }, [list.length]);
  if (!list.length) return null;
  const act = async (a, status) => { setBusy(true); try { await api(`/api/accidents/${a._id}/status`, { method: 'POST', body: { status } }); await open.reload(); onChanged?.(); } finally { setBusy(false); } };
  return (
    <div role="alert" className="alertbar" style={{ flexDirection: 'column', alignItems: 'stretch', gap: '.7rem' }}>
      <div style={{ display: 'flex', gap: '.8rem', alignItems: 'center' }}><span className="alertbar-dot" /><b style={{ fontSize: '1.15rem' }}>ACCIDENT ALERT · {list.length} open</b><span style={{ flex: 1 }} />
        <button className="alt sm" onClick={() => setMuted(!muted)}>{muted ? 'Sound the alarm again' : 'Silence the alarm'}</button></div>
      {list.map((a) => (
        <div key={a._id} style={{ display: 'flex', gap: '1rem', alignItems: 'center', background: 'rgba(255,255,255,.12)', borderRadius: 8, padding: '.6rem' }}>
          {a.evidencePath && <img src={evidenceUrl(a.evidencePath)} alt="Accident scene" style={{ width: 120, height: 80, objectFit: 'cover', borderRadius: 6 }} />}
          <div style={{ flex: 1 }}><b>Report {String(a.number).padStart(4, '0')} · {a.venue}</b><br />{what(a).charAt(0).toUpperCase() + what(a).slice(1)} · {new Date(a.occurredAt).toLocaleString()}<br /><span className="small">{a.detail}</span></div>
          <div className="actions" style={{ marginTop: 0 }}>
            <button className="alt sm" disabled={busy} onClick={() => act(a, 'Acknowledged')}>I am going there</button>
            <button className="alt sm" disabled={busy} onClick={() => act(a, 'False alarm')}>False alarm</button>
          </div>
        </div>
      ))}
    </div>
  );
}

export function Accidents() {
  const list = useLoad(() => api('/api/accidents'), [], 8000);
  const [msg, setMsg] = useState('');
  const act = async (a, status) => { await api(`/api/accidents/${a._id}/status`, { method: 'POST', body: { status } }); list.reload(); };
  const copy = async (a) => { try { await navigator.clipboard.writeText(accidentText(a)); toast('Report copied.'); } catch { setMsg(accidentText(a)); } };
  return (
    <>
      <PageHead title="Accident reports" sub="A worker who falls or stops moving raises an alert here, with a siren in this panel. The system can say a worker is down, not why." />
      <div className="note">A hit by a falling object or a heart attack looks the same to a camera as any other fall: a person on the ground. Always send someone to check.</div>
      <Err text={list.error} />
      {msg && <p className="small">{msg}</p>}
      {!list.data?.length ? <div className="empty">No accident alerts.</div> : (
        <div className="scroll"><table>
          <thead><tr><th>No.</th><th>Scene</th><th>Where</th><th>Who</th><th>When</th><th>Status</th><th /></tr></thead>
          <tbody>{list.data.map((a) => (
            <tr key={a._id}><td className="mono">{String(a.number).padStart(4, '0')}</td><td><Thumb path={a.evidencePath} /></td><td>{a.venue}<div className="small muted">{a.detail}</div></td>
              <td>{a.employeeName ? <>{a.employeeName}<div className="mono small muted">{a.employeeCode}</div></> : <span className="muted">not identified</span>}</td>
              <td className="small nowrap">{new Date(a.occurredAt).toLocaleString()}</td><td><Stamp status={a.status} /></td>
              <td className="right"><div className="actions" style={{ marginTop: 0 }}>{a.status !== 'Resolved' && <button className="go sm" onClick={() => act(a, 'Resolved')}>Resolved</button>}<button className="alt sm" onClick={() => copy(a)}>Copy report</button><button className="alt sm" onClick={() => printAccident(a)}>Print</button></div></td></tr>
          ))}</tbody>
        </table></div>
      )}
    </>
  );
}

// A one-page accident report in its own window, ready to print or save as PDF.
const esc = (v) => String(v ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
function printAccident(a) {
  const w = window.open('', '_blank', 'width=800,height=900');
  if (!w) { toast('Allow pop-ups to print the report.'); return; }
  const img = a.evidencePath ? `<img src="${esc(evidenceUrl(a.evidencePath))}" style="max-width:100%;max-height:340px;border:1px solid #999">` : '<p>No picture attached.</p>';
  w.document.write(`<!doctype html><meta charset="utf-8"><title>Accident report ${esc(String(a.number).padStart(4, '0'))}</title>
<style>body{font:14px/1.5 Segoe UI,Arial,sans-serif;margin:32px;color:#000}h1{font-size:22px;margin:0 0 4px}td{padding:5px 12px 5px 0;vertical-align:top}.sig{margin-top:48px;display:flex;gap:40px}.sig div{flex:1;border-top:1px solid #000;padding-top:4px}</style>
<h1>Accident report ${esc(String(a.number).padStart(4, '0'))}</h1><p>Raised automatically by the SiteGuard camera watch. It says what the camera saw, not why. A person must check.</p>
<table><tr><td><b>Type</b></td><td>${esc(a.kind)}</td></tr><tr><td><b>Where</b></td><td>${esc(a.venue)}</td></tr><tr><td><b>When</b></td><td>${esc(new Date(a.occurredAt).toLocaleString())}</td></tr>
<tr><td><b>Worker</b></td><td>${esc(a.employeeName ? `${a.employeeName} (${a.employeeCode})` : 'Not identified')}</td></tr><tr><td><b>Detail</b></td><td>${esc(a.detail)}</td></tr>
<tr><td><b>Status</b></td><td>${esc(a.status)}${a.closedBy ? ` by ${esc(a.closedBy)}` : ''}</td></tr></table>${img}
<div class="sig"><div>Checked by (name and signature)</div><div>Date and time</div></div><script>window.onload=function(){window.print()}<\/script>`);
  w.document.close();
}

// ---- the log ----------------------------------------------------------------------------------
const csvCell = (v) => `"${String(v ?? '').replace(/"/g, '""')}"`;

export function LogPage() {
  const log = useLoad(() => api('/api/log'), [], 15000);
  const [text, setText] = useState('');
  const [kind, setKind] = useState('');
  const [shift, setShift] = useState('');
  const inShift = (iso) => { const h = new Date(iso).getHours(); return !shift || (shift === 'day' ? h >= 6 && h < 18 : h < 6 || h >= 18); };
  const rows = (log.data || []).filter((r) => (!kind || r.kind === kind) && inShift(r.at) && `${r.userId} ${r.name} ${r.violation} ${r.location} ${r.sector}`.toLowerCase().includes(text.toLowerCase()));
  const day = (iso) => new Date(iso).toLocaleDateString([], { day: '2-digit', month: 'short', year: 'numeric' });
  const time = (iso) => new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  const download = () => {
    const head = ['Type', 'No.', 'Employee ID', 'Name', 'Violation', 'Date', 'Time', 'Status', 'Sector', 'Place', 'Times caught', 'Image'];
    const body = rows.map((r) => [r.kind, r.number, r.userId, r.name, r.violation, day(r.at), time(r.at), r.status, r.sector, r.location, r.catches, r.image ? evidenceUrl(r.image) : '']);
    const blob = new Blob(['﻿' + [head, ...body].map((l) => l.map(csvCell).join(',')).join('\r\n')], { type: 'text/csv;charset=utf-8' });
    const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = `siteguard-log-${new Date().toISOString().slice(0, 10)}.csv`; a.click();
  };
  return (
    <>
      <PageHead title="Log" sub="Every catch and every accident alert: who, what, the picture, and the date and time.">
        <input className="search" placeholder="Search ID, name, place" value={text} onChange={(e) => setText(e.target.value)} />
        <select value={kind} onChange={(e) => setKind(e.target.value)}><option value="">All</option><option>Violation</option><option>Accident</option></select>
        <select value={shift} onChange={(e) => setShift(e.target.value)} aria-label="Shift"><option value="">Day and night</option><option value="day">Day shift (6:00 to 18:00)</option><option value="night">Night shift</option></select>
        <button className="go" onClick={download} disabled={!rows.length}>Download CSV</button>
      </PageHead>
      <Err text={log.error} />
      {log.loading ? <p className="muted">Loading…</p> : !rows.length ? <div className="empty">Nothing in the log yet.</div> : (
        <div className="scroll"><table>
          <thead><tr><th>Type</th><th>Employee ID</th><th>Name</th><th>Violation</th><th>Image</th><th>Date</th><th>Time</th><th>Status</th><th>Place</th></tr></thead>
          <tbody>{rows.map((r) => (
            <tr key={r.key}><td>{r.kind === 'Accident' ? <Chip tone="bad">Accident</Chip> : 'Violation'}</td><td className="mono">{r.userId || '—'}</td><td>{r.name || '—'}{r.catches > 1 && <div className="small muted">caught {r.catches} times</div>}</td>
              <td><b>{r.violation}</b></td><td><Thumb path={r.image} /></td><td className="nowrap">{day(r.at)}</td><td className="nowrap mono">{time(r.at)}</td><td><Stamp status={r.status} /></td><td className="small">{[r.sector, r.location].filter(Boolean).join(' · ')}</td></tr>
          ))}</tbody>
        </table></div>
      )}
    </>
  );
}

// ---- rules and penalties ----------------------------------------------------------------------
const RULE = { helmet: 'A helmet must be worn at all times on site.', vest: 'A high-visibility vest must be worn at all times on site.', gloves: 'Gloves must be worn for hand work.', boots: 'Safety boots must be worn at all times.', goggles: 'Eye protection must be worn where required.' };

export function Rules() {
  const rules = useLoad(() => api('/api/rules'), []);
  const pens = useLoad(() => api('/api/penalties'), [], 20000);
  const p = rules.data?.policy;
  return (
    <>
      <PageHead title="Rules and penalties" sub="What each kind of work requires, how violations are counted, and when a penalty is proposed." />
      <Err text={rules.error} />
      {p && (
        <section className="card">
          <h3>Penalty policy</h3>
          <p>A violation is recorded only after a supervisor confirms it. <b>{p.proposeAt} confirmed violations within {p.windowDays} days</b> propose a penalty of <b>{money(p.amount, p.currency)}</b>. A supervisor approves or waives it, and the employee can dispute it. One violation is counted per person per day.</p>
          <p className="small muted">These are example values for the demo; the real amounts are set by the company's own policy.</p>
          <Link to="/penalties">Open the penalties</Link>
        </section>
      )}
      {(rules.data?.sectors || []).map((s) => (
        <section className="card" key={s.id}>
          <h3>{s.name} <span className="small muted">{s.conditionClass}</span></h3>
          <ul style={{ margin: '.3rem 0 .6rem 1.2rem' }}>{s.requiredItems.map((i) => <li key={i}>{RULE[i] || `${i} must be worn.`} <span className="small muted">Missing it records: NO {i.toUpperCase()}</span></li>)}</ul>
          <p className="small muted" style={{ margin: 0 }}>Fields: {s.fields.join(', ') || 'none yet'} · Classes: {s.classes.join(', ') || 'none yet'} · Violations confirmed so far: <b>{s.violated}</b></p>
        </section>
      ))}
      <h3>Penalties</h3>
      {!pens.data?.length ? <div className="empty">No penalties yet.</div> : (
        <div className="scroll"><table><thead><tr><th>Employee</th><th>Rule broken</th><th className="right">Amount</th><th>Date</th><th>Status</th></tr></thead>
          <tbody>{pens.data.map((x) => <tr key={x._id}><td><b>{x.employeeName}</b></td><td className="small" style={{ maxWidth: 380 }}>{x.reason}</td><td className="right money">{money(x.amount, x.currency)}</td><td className="nowrap">{fmtDay(x.createdAt)}</td><td><Stamp status={x.status} /></td></tr>)}</tbody></table></div>
      )}
    </>
  );
}

// Shown to a supervisor who has no employees yet (a new account): the three steps to get going.
export function SetupGuide() {
  const { user } = useAuth();
  const team = useLoad(() => (user.isAdmin ? Promise.resolve([1]) : api('/api/employees')), [user.id], 20000);
  if (user.isAdmin || !team.data || team.data.length) return null;
  const Step = ({ n, to, title, text }) => <div style={{ flex: 1, minWidth: 220 }}><b>{n}. <Link to={to}>{title}</Link></b><p className="small muted" style={{ margin: '.2rem 0 0' }}>{text}</p></div>;
  return (
    <section className="card" style={{ borderLeft: '4px solid var(--info, #2563c9)' }}>
      <h3>Welcome, {user.name}. Set up your site</h3>
      <div className="actions" style={{ alignItems: 'flex-start', marginTop: 0 }}>
        <Step n="1" to="/sectors" title="Check your requirements" text="The gear your workers must wear, your fields and your classes. You can change them any time." />
        <Step n="2" to="/employees" title="Add your employees" text={`Name, photo and field. IDs are made for you and start with ${user.code || 'your code'}. The photo also teaches the camera their face.`} />
        <Step n="3" to="/" title="Upload a video or photo" text="On the demo desk (port 3003), choose your sector. Anyone caught without the gear reaches you here." />
      </div>
    </section>
  );
}

// ---- monthly safety report (print or save as PDF) -------------------------------------------------
function Bars({ rows, tone }) {
  const top = Math.max(1, ...rows.map((r) => r[1]));
  return <div className="bars">{rows.map(([label, n]) => <div className="bar-row" key={label}><span>{label}</span><div className="track"><div className={`fill ${tone || ''}`} style={{ width: `${(n / top) * 100}%` }} /></div><b>{n}</b></div>)}{!rows.length && <p className="muted small">Nothing recorded.</p>}</div>;
}
const tally = (items) => Object.entries(items.reduce((m, k) => { if (k) m[k] = (m[k] || 0) + 1; return m; }, {})).sort((a, b) => b[1] - a[1]);
const monthOf = (iso) => { const d = new Date(iso); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`; };
const COUNTED_STATUS = ['Confirmed', 'Acknowledged', 'Disputed'];

export function Report() {
  const { user } = useAuth();
  const log = useLoad(() => api('/api/log'), []);
  const pens = useLoad(() => api('/api/penalties'), []);
  const [month, setMonth] = useState(monthOf(new Date().toISOString()));
  const all = log.data || [];
  const months = [...new Set([monthOf(new Date().toISOString()), ...all.map((r) => monthOf(r.at))])].sort().reverse();
  const rows = all.filter((r) => monthOf(r.at) === month);
  const found = rows.filter((r) => r.kind === 'Violation' && r.status !== 'Dismissed');
  const confirmed = found.filter((r) => COUNTED_STATUS.includes(r.status));
  const accidents = rows.filter((r) => r.kind === 'Accident');
  const penalties = (pens.data || []).filter((p) => monthOf(p.createdAt) === month);
  const day = found.filter((r) => { const h = new Date(r.at).getHours(); return h >= 6 && h < 18; }).length;
  const label = new Date(`${month}-01T00:00:00`).toLocaleDateString([], { month: 'long', year: 'numeric' });
  return (
    <>
      <PageHead title="Monthly safety report" sub={`${user.isAdmin ? 'All sectors' : user.sectorName || 'Your site'}. Print it or save it as a PDF.`}>
        <select value={month} onChange={(e) => setMonth(e.target.value)} aria-label="Month" className="no-print">{months.map((m) => <option key={m} value={m}>{new Date(`${m}-01T00:00:00`).toLocaleDateString([], { month: 'long', year: 'numeric' })}</option>)}</select>
        <button className="go" onClick={() => window.print()}>Print or save as PDF</button>
      </PageHead>
      <Err text={log.error} />
      <h2>{user.isAdmin ? 'All sectors' : user.sectorName} · {label}</h2>
      <div className="grid g4" style={{ marginBottom: '1rem' }}>
        {[['Caught without gear', found.length], ['Confirmed by a supervisor', confirmed.length], ['Accident alerts', accidents.length], ['Penalties proposed or issued', penalties.length]].map(([k, v]) => <div className="kpi" key={k}><div><b>{v}</b><span>{k}</span></div></div>)}
      </div>
      <div className="grid g2">
        <section className="card"><h3>What was missing</h3><Bars rows={tally(found.flatMap((r) => r.violation.split(/\s*[,+]\s*/)))} /></section>
        <section className="card"><h3>Where it happened</h3><Bars rows={tally(found.map((r) => r.location || 'Place not recorded'))} tone="warn" /></section>
        <section className="card"><h3>Shift</h3><Bars rows={[['Day shift (6:00 to 18:00)', day], ['Night shift', found.length - day]]} /></section>
        <section className="card"><h3>Accident alerts</h3>
          {!accidents.length ? <p className="muted small">None this month.</p> : <div className="scroll"><table><thead><tr><th>When</th><th>Type</th><th>Where</th><th>Status</th></tr></thead><tbody>{accidents.map((a) => <tr key={a.key}><td className="small nowrap">{new Date(a.at).toLocaleString()}</td><td>{a.violation.split(':')[0]}</td><td className="small">{a.location}</td><td><Stamp status={a.status} /></td></tr>)}</tbody></table></div>}</section>
      </div>
      <section className="card"><h3>Penalties</h3>
        {!penalties.length ? <p className="muted small">None this month.</p> : <div className="scroll"><table><thead><tr><th>Employee</th><th className="right">Amount</th><th>Status</th></tr></thead><tbody>{penalties.map((p) => <tr key={p._id}><td>{p.employeeName}</td><td className="right">{money(p.amount, p.currency)}</td><td><Stamp status={p.status} /></td></tr>)}</tbody></table></div>}</section>
      <p className="small muted">Counts come from what the camera watch caught and what supervisors confirmed. Accuracy limits are on the About page. Made {new Date().toLocaleString()}.</p>
    </>
  );
}
