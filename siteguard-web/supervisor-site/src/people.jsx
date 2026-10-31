import { Fragment, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { useAuth } from '../../shared/auth.jsx';
import { api, download, session } from '../../shared/api.js';
import { toast } from '../../shared/theme.js';
import { Avatar, Chip, Err, Kpi, PageHead, Stamp, Thumb, fmtDate, fmtDay, money, monthName, ticketNo, useLoad } from '../../shared/ui.jsx';

// ---- detector service (faces) -----------------------------------------------------------------
const DETECTOR = import.meta.env.VITE_DETECTOR_URL || 'http://localhost:5000';
export async function faceCall(path, options = {}) {
  const res = await fetch(DETECTOR + path, { ...options, headers: { 'content-type': 'application/json', authorization: `Bearer ${session.get()?.token || ''}` } });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || `The detector service said no (${res.status}).`);
  return data;
}
const readFile = (file) => new Promise((resolve, reject) => { const r = new FileReader(); r.onload = () => resolve(r.result); r.onerror = reject; r.readAsDataURL(file); });
const useFaces = () => useLoad(() => faceCall('/faces').catch(() => null), [], 20000);
// Everyone the detector has seen (enrolled employees and demo identities) with their sightings.
export const usePeopleSeen = () => useLoad(() => faceCall('/people').catch(() => null), [], 15000);
const ago = (iso) => {
  const m = Math.round((Date.now() - new Date(iso)) / 60000);
  return m < 1 ? 'just now' : m < 60 ? `${m} min ago` : m < 1440 ? `${Math.round(m / 60)} h ago` : `${Math.round(m / 1440)} d ago`;
};
// Shrink a chosen photo to a small square-ish JPEG before it is stored with the employee.
const shrink = (file, max = 200) => new Promise((resolve, reject) => {
  const img = new Image();
  img.onload = () => {
    const scale = Math.min(1, max / Math.max(img.width, img.height));
    const c = document.createElement('canvas'); c.width = Math.round(img.width * scale); c.height = Math.round(img.height * scale);
    c.getContext('2d').drawImage(img, 0, 0, c.width, c.height);
    resolve(c.toDataURL('image/jpeg', 0.82));
  };
  img.onerror = reject;
  img.src = URL.createObjectURL(file);
});

// Photos can be added per employee (several at once), or in bulk when each file name starts with the employee ID (E001.jpg, E001_2.jpg).
export function FacePanel({ team, faces, compact = false }) {
  const [consent, setConsent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [results, setResults] = useState([]);
  const [error, setError] = useState('');
  const counts = Object.fromEntries((faces.data || []).map((f) => [f.employeeId, f.samples]));
  const known = new Set(team.map((m) => m.employeeId));
  const offline = faces.data === null && !faces.loading;

  const send = async (employeeId, file) => {
    try {
      const r = await faceCall('/faces/enroll', { method: 'POST', body: JSON.stringify({ employeeId, consent, image: await readFile(file) }) });
      return { file: file.name, employeeId, ok: true, text: `added (${r.samples} on file)` };
    } catch (err) { return { file: file.name, employeeId, ok: false, text: err.message }; }
  };
  const run = async (jobs, skipped = []) => {
    setBusy(true); setError(''); setResults(skipped);
    const out = [];
    for (const [employeeId, file] of jobs) { out.push(await send(employeeId, file)); setResults([...skipped, ...out]); }
    faces.reload(); setBusy(false);
  };
  const forEmployee = (employeeId) => (e) => {
    const files = [...e.target.files]; e.target.value = '';
    if (files.length) run(files.map((f) => [employeeId, f]));
  };
  const bulk = (e) => {
    const files = [...e.target.files]; e.target.value = '';
    const jobs = []; const skipped = [];
    for (const f of files) {
      const id = f.name.split(/[_.\- ]/)[0].toUpperCase();
      if (known.has(id)) jobs.push([id, f]);
      else skipped.push({ file: f.name, employeeId: '', ok: false, text: 'The file name must start with an employee ID, like E001_1.jpg' });
    }
    run(jobs, skipped);
  };
  const remove = async (id) => { setError(''); try { await faceCall(`/faces/${id}`, { method: 'DELETE' }); faces.reload(); } catch (err) { setError(err.message); } };
  const off = busy || !consent || offline;
  return (
    <section className={compact ? '' : 'card'}>
      {!compact && <h3>Face matching (optional)</h3>}
      <p className="small muted">Add photos of your employees and the detector can suggest a worker's name on a flagged case. It is only a suggestion: you still confirm the person. Only a numeric template is stored, never the photo, and you can remove a person at any time. Accuracy on real site footage has not been measured; helmets, distance and poor light make it less reliable.</p>
      {offline && <div className="err">The detector service is not running, so photos cannot be added. Start it with <span className="mono">npm run detector</span>.</div>}
      <label style={{ display: 'flex', gap: '.5rem', alignItems: 'center' }}><input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} />Every employee whose photo I add has been told how their face template is used and agrees.</label>
      <p className="small muted" style={{ marginTop: '.4rem' }}>Best photos: one person, facing the camera, no helmet or cap, good light. Two or three per person, taken on different days, work better than one.</p>
      <div className="scroll"><table>
        <thead><tr><th>Employee</th><th>Photos on file</th><th>Add photos</th><th /></tr></thead>
        <tbody>{team.map((m) => (
          <tr key={m.id}><td><div className="who-cell"><Avatar name={m.name} size={30} /><div><b>{m.name}</b><small>{m.employeeId}{m.jobRole ? ` · ${m.jobRole}` : ''}</small></div></div></td>
            <td>{counts[m.employeeId] ? <Chip tone="ok">{counts[m.employeeId]} on file</Chip> : <span className="muted">none</span>}</td>
            <td><input type="file" accept="image/*" multiple onChange={forEmployee(m.employeeId)} disabled={off} aria-label={`Add photos for ${m.name}`} /></td>
            <td className="right">{counts[m.employeeId] ? <button className="alt sm" onClick={() => remove(m.employeeId)}>Remove</button> : null}</td></tr>
        ))}</tbody>
      </table></div>
      {!compact && (
        <div className="field" style={{ marginTop: '1rem' }}>
          <label htmlFor="fbulk">Or add many at once: photos named with the employee ID (E001.jpg, E001_2.jpg, E002.jpg…)</label>
          <input id="fbulk" type="file" accept="image/*" multiple onChange={bulk} disabled={off} />
        </div>
      )}
      {busy && <p className="muted">Adding photos…</p>}
      <Err text={error} />
      {results.length > 0 && <div className="scroll" style={{ marginTop: '.8rem' }}><table><thead><tr><th>File</th><th>Employee</th><th>Result</th></tr></thead>
        <tbody>{results.map((r, i) => <tr key={i}><td>{r.file}</td><td className="mono">{r.employeeId}</td><td style={{ color: r.ok ? 'var(--ok)' : 'var(--bad)' }}>{r.text}</td></tr>)}</tbody></table></div>}
    </section>
  );
}

export function FacesPage() {
  const team = useLoad(() => api('/api/employees'), []);
  const faces = useFaces();
  const seen = usePeopleSeen();
  const [open, setOpen] = useState('');
  const [msg, setMsg] = useState('');
  const { user: me } = useAuth();
  const mine = new Set((team.data || []).map((m) => m.employeeId));
  const seenList = (seen.data || []).filter((p) => me.isAdmin || mine.has(p.employeeId));
  const clear = async () => { try { const r = await faceCall('/people/dummy', { method: 'DELETE' }); setMsg(`Cleared ${r.cleared} demo identities.`); seen.reload(); } catch (e) { setMsg(e.message); } };
  return (
    <>
      <PageHead title="Face matching" sub="Photos of your employees, and everyone the detector has recognised on camera." />
      <Err text={team.error} />
      <div className="card">
        <h3>People seen on camera {me.isAdmin && seen.data?.some((p) => p.dummy) && <button className="alt sm" onClick={clear}>Clear demo identities</button>}</h3>
        <p className="small muted">The same face always gets the same person here, across photos, videos and cameras. Demo identities (marked demo) have made-up names and belong to nobody; they expire after 7 days or when cleared.</p>
        {msg && <p className="small" style={{ color: 'var(--ok)' }}>{msg}</p>}
        {seen.data === null && !seen.loading ? <div className="note">The detector service is not running, so sightings are not available.</div>
          : !seenList.length ? <div className="empty">Nobody seen yet. Upload a photo, video or live camera on the demo desk (port 3003).</div> : (
            <div className="scroll"><table>
              <thead><tr><th>Person</th><th>Work role</th><th className="right">Times seen</th><th>Last seen</th><th /></tr></thead>
              <tbody>{seenList.map((p) => (
                <Fragment key={p.employeeId}>
                  <tr className="click" onClick={() => setOpen(open === p.employeeId ? '' : p.employeeId)}>
                    <td><div className="who-cell"><Avatar name={p.name} size={32} /><div><b>{p.name}</b> {p.dummy && <Chip tone="info">demo</Chip>}<small>{p.employeeId}</small></div></div></td>
                    <td>{p.jobRole}</td><td className="right">{p.sightingCount}</td><td className="small">{ago(p.lastSeen)}</td><td className="right"><button className="link">{open === p.employeeId ? 'Hide' : 'Sightings'}</button></td></tr>
                  {open === p.employeeId && p.sightings.slice().reverse().map((x, i) => <tr key={i}><td colSpan="5" className="small" style={{ background: 'var(--soft)' }}>{fmtDate(x.at)} · {x.source}{x.location ? ` · ${x.location}` : ''}</td></tr>)}
                </Fragment>
              ))}</tbody>
            </table></div>
          )}
      </div>
      {team.data && <FacePanel team={team.data} faces={faces} />}
    </>
  );
}

// ---- Employees ------------------------------------------------------------------------------
const EMPTY = { name: '', jobRole: '', monthlySalary: '', number: '', field: '', className: '', sectorId: '', password: '' };

export function Employees() {
  const team = useLoad(() => api('/api/employees'), []);
  const cases = useLoad(() => api('/api/violations'), [], 20000);
  const pens = useLoad(() => api('/api/penalties'), [], 20000);
  const faces = useFaces();
  const seen = usePeopleSeen();
  const queue = useLoad(() => api('/api/review/queue'), [], 15000);
  const nav = useNavigate();
  const [text, setText] = useState('');
  const [adding, setAdding] = useState(false);
  const [form, setForm] = useState(EMPTY);
  const [error, setError] = useState('');
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });
  const { user } = useAuth();
  const sectors = useLoad(() => api('/api/sectors'), []);
  const [photoFile, setPhotoFile] = useState(null);
  const [consent, setConsent] = useState(false);
  const [made, setMade] = useState(null);
  const sector = (sectors.data || []).find((s) => s.id === (user.isAdmin ? form.sectorId || user.sectorId : user.sectorId));
  const add = async (e) => {
    e.preventDefault(); setError(''); setMade(null);
    try {
      const body = { ...form, sectorId: sector?.id || '', monthlySalary: Number(form.monthlySalary) || 0, photo: photoFile ? await shrink(photoFile) : '' };
      const created = await api('/api/employees', { method: 'POST', body });
      // The same photo teaches the camera to recognise this person (only a numeric template is kept, and only with the consent box ticked).
      let face = photoFile ? 'No face template made.' : 'No photo added, so the camera cannot recognise this person yet.';
      if (photoFile && consent) {
        try { const r = await faceCall('/faces/enroll', { method: 'POST', body: JSON.stringify({ employeeId: created.employeeId, consent: true, image: await readFile(photoFile) }) }); face = `Face enrolled (${r.samples} on file).`; faces.reload(); } catch (err) { face = `Employee added, but the face was not enrolled: ${err.message}`; }
      } else if (photoFile) face = 'Photo saved on the profile. Tick the consent box to also let the camera recognise this person.';
      setMade({ ...created, face }); setForm({ ...EMPTY, field: form.field, className: form.className }); setPhotoFile(null); setConsent(false); team.reload();
    } catch (err) { setError(err.message); }
  };
  const mine = (id) => (cases.data || []).filter((v) => v.employeeId === id && v.status !== 'Dismissed');
  const waitingFor = (empId) => (queue.data || []).filter((v) => v.suggested?.employeeId === empId).length;
  const issued = (id) => (pens.data || []).filter((p) => p.employeeId === id && ['Issued', 'Paid'].includes(p.status)).length;
  const enrolled = new Set((faces.data || []).map((f) => f.employeeId));
  const seenBy = Object.fromEntries((seen.data || []).map((p) => [p.employeeId, p]));
  const todayCaught = (id) => (cases.data || []).filter((v) => v.employeeId === id && v.dayKey === new Date(Date.now() + 330 * 60000).toISOString().slice(0, 10)).reduce((n, v) => n + (v.catches || 1), 0);
  const rows = (team.data || []).filter((m) => `${m.name} ${m.employeeId} ${m.jobRole} ${m.department}`.toLowerCase().includes(text.toLowerCase()))
    .sort((a, b) => mine(b.id).length - mine(a.id).length || (seenBy[b.employeeId]?.sightingCount || 0) - (seenBy[a.employeeId]?.sightingCount || 0) || a.name.localeCompare(b.name));
  return (
    <>
      <PageHead title="Employees" sub="Your team: who they are, their violations and their pay.">
        <input className="search" placeholder="Search name, ID or role" value={text} onChange={(e) => setText(e.target.value)} />
        <button className="go" onClick={() => setAdding(!adding)}>{adding ? 'Close' : 'Add employee'}</button>
      </PageHead>
      {adding && (
        <form className="card" onSubmit={add}>
          <h3>New employee{sector ? ` · ${sector.name}` : ''}</h3>
          <p className="small muted">The ID is made for you: your 3-letter code and a number (for example <span className="mono">{(user.code || 'BCE')}101</span>). The starting password is <span className="mono">123456789</span> for every new employee (a demo value; change it before real use).</p>
          <div className="actions" style={{ alignItems: 'flex-end' }}>
            {user.isAdmin && <div><label htmlFor="a0">Sector</label><select id="a0" value={sector?.id || ''} onChange={(e) => setForm({ ...form, sectorId: e.target.value, field: '', className: '' })}>{(sectors.data || []).map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}</select></div>}
            <div><label htmlFor="a2">Name</label><input id="a2" value={form.name} onChange={set('name')} /></div>
            <div><label htmlFor="a5">Work role</label><input id="a5" value={form.jobRole} onChange={set('jobRole')} placeholder="e.g. Electrician" /></div>
            <div><label htmlFor="a7">Field</label><select id="a7" value={form.field} onChange={set('field')}><option value="">Choose…</option>{(sector?.fields || []).map((f) => <option key={f}>{f}</option>)}</select></div>
            <div><label htmlFor="a8">Class</label><select id="a8" value={form.className} onChange={set('className')}><option value="">Choose…</option>{(sector?.classes || []).map((f) => <option key={f}>{f}</option>)}</select></div>
            <div><label htmlFor="a9">ID number (optional)</label><input id="a9" value={form.number} onChange={set('number')} placeholder="next free" style={{ width: 110 }} /></div>
            <div><label htmlFor="a6">Monthly salary (₹)</label><input id="a6" type="number" min="0" value={form.monthlySalary} onChange={set('monthlySalary')} /></div>
          </div>
          <div className="actions" style={{ alignItems: 'center' }}>
            <div><label htmlFor="a10">Photo of the employee (face, no helmet)</label><input id="a10" type="file" accept="image/*" onChange={(e) => setPhotoFile(e.target.files?.[0] || null)} /></div>
            <label className="inline"><input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} /> The employee has been told how their face template is used and agrees.</label>
            <button className="go">Add employee</button>
          </div>
          <Err text={error} />
          {made && <div className="note info"><b>{made.name}</b> added. Sign-in ID <span className="mono"><b>{made.employeeId}</b></span>, password <span className="mono"><b>{made.password}</b></span>{made.passwordIsDefault ? ' (the default)' : ''}. {made.face}</div>}
        </form>
      )}
      <Err text={team.error} />
      {team.loading ? <p className="muted">Loading…</p> : (
        <div className="scroll"><table>
          <thead><tr><th>Employee</th><th>Work role</th><th className="right">Salary / month</th><th className="right">Violations</th><th className="right">Caught today</th><th className="right">Seen on site</th><th>Last seen</th></tr></thead>
          <tbody>{rows.map((m) => {
            const n = mine(m.id).length;
            return (
              <tr key={m.id} className="click" onClick={() => nav(`/employees/${m.id}`)}>
                <td><div className="who-cell"><Avatar name={m.name} photo={m.photo} /><div><b>{m.name}</b><small className="mono">{m.employeeId}{enrolled.has(m.employeeId) ? ' · face enrolled' : ''}</small></div></div></td>
                <td>{m.jobRole}<br /><span className="small muted">{m.department}</span></td>
                <td className="right money">{money(m.monthlySalary)}</td>
                <td className="right">{n ? <Chip tone={n >= 3 ? 'bad' : 'warn'}>{n}</Chip> : <Chip tone="ok">0</Chip>}{issued(m.id) ? <span className="small muted"> · {issued(m.id)} penalty</span> : null}{waitingFor(m.employeeId) ? <span className="small muted"> · {waitingFor(m.employeeId)} awaiting review</span> : null}</td>
                <td className="right">{todayCaught(m.id) || '—'}</td>
                <td className="right">{seenBy[m.employeeId]?.sightingCount || '—'}</td><td className="small">{seenBy[m.employeeId] ? ago(seenBy[m.employeeId].lastSeen) : <span className="muted">not seen yet</span>}</td>
              </tr>
            );
          })}</tbody>
        </table></div>
      )}
    </>
  );
}

// ---- One employee ---------------------------------------------------------------------------
export function EmployeeDetail() {
  const { id } = useParams();
  const prof = useLoad(() => api(`/api/employees/${id}/profile`), [id], 20000);
  const faces = useFaces();
  const seen = usePeopleSeen();
  const [tab, setTab] = useState('violations');
  const [salary, setSalary] = useState('');
  const [msg, setMsg] = useState('');
  const [error, setError] = useState('');
  if (prof.loading) return <p className="muted">Loading…</p>;
  if (!prof.data) return <><Err text={prof.error} /><Link to="/employees">Back to employees</Link></>;
  const { employee: e, violations, penalties, payslips, currency } = prof.data;
  const counted = violations.filter((v) => !['Pending review', 'Dismissed'].includes(v.status));
  const waiting = violations.filter((v) => v.status === 'Pending review');
  const recent = counted.filter((v) => Date.now() - new Date(v.occurredAt) <= 30 * 86400000);
  const slip = payslips[0];
  const saveSalary = async () => {
    setError(''); setMsg('');
    try { await api(`/api/employees/${e.id}/salary`, { method: 'POST', body: { monthlySalary: Number(salary) } }); setMsg('Salary saved.'); setSalary(''); prof.reload(); } catch (err) { setError(err.message); }
  };
  return (
    <>
      <p className="small"><Link to="/employees">← Employees</Link></p>
      <div className="hero">
        <Avatar name={e.name} size={72} photo={e.photo} />
        <div><h1>{e.name}</h1><p>{e.jobRole || 'Employee'}{e.department ? ` · ${e.department}` : ''} · <span className="mono">{e.employeeId}</span></p></div>
        <span className="sp" />
        <button className="go" onClick={async () => { setError(''); try { await download(`/api/employees/${e.id}/report.pdf`, `complaint-report-${e.employeeId}.pdf`); toast('Complaint report downloaded.'); } catch (err) { setError(err.message); } }}>Complaint report (PDF)</button>
        {recent.length >= 3 ? <Chip tone="bad">Repeat violations</Chip> : recent.length ? <Chip tone="warn">{recent.length} in the last 30 days</Chip> : <Chip tone="ok">Clean record</Chip>}
      </div>
      <div className="grid g4" style={{ marginBottom: '1rem' }}>
        <Kpi icon="alert" tone={counted.length ? 'hot' : 'ok'} label="Violations on record" value={counted.length} />
        <Kpi icon="inbox" tone={waiting.length ? 'hot' : 'ok'} label="Caught, awaiting your review" value={waiting.length} />
        <Kpi icon="clock" tone={recent.length ? 'hot' : 'ok'} label="Confirmed in the last 30 days" value={recent.length} />
        <Kpi icon="wallet" tone="info" label={`Net pay, ${monthName(slip.month)}`} value={money(slip.net, currency)} />
      </div>
      <div className="tabs">{[['violations', 'Violations'], ['sightings', 'Seen on site'], ['penalties', 'Penalties'], ['salary', 'Salary'], ['face', 'Face and photo']].map(([k, label]) => <button key={k} className={tab === k ? 'on' : ''} onClick={() => setTab(k)}>{label}</button>)}</div>

      {tab === 'violations' && (!violations.length ? <div className="empty">No violations.</div> : (
        <div className="scroll"><table>
          <thead><tr><th>No.</th><th>Picture</th><th>Missing</th><th>Where</th><th>When</th><th>Status</th><th>Reviewed by</th></tr></thead>
          <tbody>{violations.map((v) => (
            <Fragment key={v._id}>
              <tr><td className="mono">{ticketNo(v.number)}</td><td><Thumb path={v.evidencePath} /></td><td><b>{v.missing}</b>{v.remarks && <div className="small muted" style={{ maxWidth: 380 }}>{v.remarks}</div>}</td><td>{v.location}</td><td className="small nowrap">{fmtDate(v.occurredAt)}{v.catches > 1 && <><br /><span className="small muted">caught {v.catches} times</span></>}</td><td><Stamp status={v.status} /></td><td>{v.reviewedBy}</td></tr>
              {v.status === 'Disputed' && <tr><td colSpan="7" className="small" style={{ background: 'var(--info-soft)' }}>Employee says: {(v.log || []).filter((l) => l.action === 'Disputed').map((l) => l.note).join(' / ')}</td></tr>}
            </Fragment>
          ))}</tbody>
        </table></div>
      ))}

      {tab === 'penalties' && (!penalties.length ? <div className="empty">No penalties.</div> : penalties.map((p) => (
        <div className="card" key={p._id}><div className="case-top"><span className="no">{fmtDay(p.createdAt)}</span><Stamp status={p.status} /></div>
          <div className="what" style={{ color: 'var(--ink)' }}>{money(p.amount, p.currency)}</div><p className="small muted">{p.reason}</p>
          {p.note && <p className="small">Note: {p.note}</p>}<Link to="/penalties" className="small">Decide on the Penalties page</Link></div>
      )))}

      {tab === 'salary' && (
        <>
          <div className="card">
            <h3>Monthly salary</h3>
            <p className="muted small">Current: <b className="money">{money(e.monthlySalary, currency)}</b>. Demo figures; set the real amount here.</p>
            <div className="actions" style={{ marginTop: 0 }}><input type="number" min="0" placeholder="New amount (₹)" value={salary} onChange={(ev) => setSalary(ev.target.value)} /><button className="go" disabled={!salary} onClick={saveSalary}>Save</button></div>
            {msg && <p className="small" style={{ color: 'var(--ok)' }}>{msg}</p>}<Err text={error} />
          </div>
          <div className="scroll"><table>
            <thead><tr><th>Month</th><th className="right">Salary</th><th className="right">Penalties issued</th><th className="right">Net pay</th></tr></thead>
            <tbody>{payslips.map((p) => <tr key={p.month}><td><b>{monthName(p.month)}</b></td><td className="right money">{money(p.base, currency)}</td><td className="right money">{p.deductions ? `− ${money(p.deductions, currency)}` : '—'}</td><td className="right money"><b>{money(p.net, currency)}</b></td></tr>)}</tbody>
          </table></div>
        </>
      )}

      {tab === 'sightings' && (() => {
        const mine = (seen.data || []).find((p) => p.employeeId === e.employeeId);
        return !mine ? <div className="empty">Not seen on camera yet.</div> : (
          <div className="card"><h3>Seen on site {mine.sightingCount} time{mine.sightingCount > 1 ? 's' : ''}</h3>
            <div className="scroll"><table><thead><tr><th>When</th><th>Where</th><th>Source</th></tr></thead>
              <tbody>{mine.sightings.slice().reverse().map((x, i) => <tr key={i}><td className="small nowrap">{fmtDate(x.at)}</td><td>{x.location || '—'}</td><td>{x.source}</td></tr>)}</tbody></table></div></div>
        );
      })()}

      {tab === 'face' && (
        <>
          <div className="card"><h3>Profile photo</h3>
            <div className="who-cell"><Avatar name={e.name} size={72} photo={e.photo} />
              <div><input type="file" accept="image/*" onChange={async (ev) => { const f = ev.target.files?.[0]; ev.target.value = ''; if (!f) return; setError(''); try { await api(`/api/employees/${e.id}/photo`, { method: 'POST', body: { photo: await shrink(f) } }); prof.reload(); } catch (err) { setError(err.message); } }} />
                {e.photo && <button className="alt sm" style={{ marginLeft: '.5rem' }} onClick={async () => { await api(`/api/employees/${e.id}/photo`, { method: 'POST', body: { photo: '' } }); prof.reload(); }}>Remove</button>}
                <p className="small muted" style={{ margin: '.3rem 0 0' }}>Shown on this page, the employee list and the employee's own site. It is shrunk to a small image.</p></div></div>
            <Err text={error} /></div>
          <div className="card"><h3>Face matching</h3><FacePanel team={[e]} faces={faces} compact /></div>
        </>
      )}
    </>
  );
}
