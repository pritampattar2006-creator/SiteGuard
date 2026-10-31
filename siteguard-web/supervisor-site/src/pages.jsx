import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { api } from '../../shared/api.js';
import { Avatar, Chip, Err, Evidence, FaultBox, Kpi, NoticeButton, PageHead, Stamp, Thumb, fmtDate, money, ticketNo, useLoad } from '../../shared/ui.jsx';
import { usePeopleSeen } from './people.jsx';

// ---- Dashboard ------------------------------------------------------------------------------
function DayChart({ days, series }) {
  const peak = Math.max(3, ...series);
  const W = 560, H = 170, pad = 24, bw = (W - pad) / series.length;
  return (
    <svg viewBox={`0 0 ${W} ${H + 22}`} role="img" aria-label="Confirmed violations per day, last 14 days" style={{ width: '100%' }}>
      {[0, 0.5, 1].map((f) => <g key={f}><line x1={pad} x2={W} y1={H - f * (H - 10)} y2={H - f * (H - 10)} stroke="var(--line)" /><text x={pad - 6} y={H - f * (H - 10) + 4} fontSize="10" textAnchor="end" fill="var(--muted)">{Math.round(f * peak)}</text></g>)}
      {series.map((n, i) => {
        const h = (n / peak) * (H - 10);
        return <g key={i}><rect x={pad + i * bw + 5} y={H - h} width={bw - 10} height={h} rx="4" fill="var(--brand)"><title>{`${days[i]}: ${n}`}</title></rect>
          {(i % 3 === 0 || i === series.length - 1) && <text x={pad + i * bw + bw / 2} y={H + 16} fontSize="10" textAnchor="middle" fill="var(--muted)">{days[i].slice(5)}</text>}</g>;
      })}
    </svg>
  );
}

export const Bars = ({ entries, empty }) => {
  const top = Math.max(1, ...entries.map((e) => e[1]));
  return !entries.length ? <p className="muted small">{empty}</p> : <div className="bars">{entries.map(([k, n]) => <div className="bar-row" key={k}><span>{k}</span><div className="bar-track"><div className="bar-fill" style={{ width: `${(n / top) * 100}%` }} /></div><b>{n}</b></div>)}</div>;
};

export function Dashboard() {
  const stats = useLoad(() => api('/api/stats'), [], 10000);
  const queue = useLoad(() => api('/api/review/queue'), [], 10000);
  const cases = useLoad(() => api('/api/violations'), [], 15000);
  const seen = usePeopleSeen();
  const onSite = (seen.data || []).filter((p) => Date.now() - new Date(p.lastSeen) < 10 * 60000);
  const s = stats.data;
  return (
    <>
      <PageHead title="Overview" sub="What needs you today, and how the site is doing." />
      <Err text={stats.error} />
      {s && (
        <div className="grid g4" style={{ marginBottom: '1rem' }}>
          <Kpi icon="inbox" tone={s.pending ? 'hot' : 'ok'} label="Waiting for review" value={s.pending} />
          <Kpi icon="alert" tone="bad" label="Confirmed violations" value={s.confirmed} />
          <Kpi icon="shield" tone={s.penaltiesWaiting ? 'hot' : 'ok'} label="Penalties awaiting decision" value={s.penaltiesWaiting} />
          <Kpi icon="wallet" tone="info" label="Penalties issued or paid" value={money(s.penaltyTotal)} />
          <Kpi icon="users" tone="info" label="On site now (seen in the last 10 min)" value={onSite.length} />
          <Kpi icon="clock" tone={s.caughtToday ? 'hot' : 'ok'} label={`Catches today, ${s.peopleToday} ${s.peopleToday === 1 ? 'person' : 'people'}`} value={s.caughtToday} />
        </div>
      )}
      {onSite.length > 0 && <div className="card"><h3>On site now</h3><div className="actions" style={{ marginTop: 0 }}>{onSite.map((p) => <span key={p.employeeId} className="who-cell" style={{ background: 'var(--soft)', padding: '.3rem .7rem .3rem .3rem', borderRadius: 99 }}><Avatar name={p.name} size={28} /><span>{p.name} <span className="small muted">{p.jobRole}</span></span></span>)}</div></div>}
      {s && (
        <div className="split" style={{ marginBottom: '1rem' }}>
          <div className="card"><h3>Confirmed violations, last 14 days</h3><DayChart days={s.days} series={s.series} /></div>
          <div className="card"><h3>What is missing most</h3><Bars entries={Object.entries(s.byItem).sort((a, b) => b[1] - a[1])} empty="No confirmed violations yet." /></div>
        </div>
      )}
      <div className="split">
        <div className="card">
          <h3>Waiting for review {s?.pending > 0 && <Link to="/queue" className="small">Open the queue</Link>}</h3>
          {!queue.data?.length ? <div className="empty">The queue is clear. New catches from the detector appear here by themselves.</div> : (
            <div className="scroll"><table>
              <thead><tr><th>Picture</th><th>Missing</th><th>Where</th><th>When</th><th>Face suggestion</th></tr></thead>
              <tbody>{queue.data.slice(0, 4).map((v) => <tr key={v._id}><td><Thumb path={v.evidencePath} /></td><td><b>{v.missing}</b></td><td>{v.location}</td><td className="small nowrap">{fmtDate(v.occurredAt)}</td><td>{v.suggested ? <Chip tone="info">{v.suggested.name}</Chip> : <span className="muted small">none</span>}</td></tr>)}</tbody>
            </table></div>
          )}
        </div>
        <div className="card">
          <h3>Most violations</h3><Bars entries={s?.byEmployee || []} empty="Nobody yet." />
          <h3 style={{ marginTop: '1.1rem' }}>By location</h3><Bars entries={Object.entries(s?.byLocation || {}).sort((a, b) => b[1] - a[1]).slice(0, 5)} empty="No locations recorded yet." />
        </div>
      </div>
      <div className="card" style={{ marginTop: '1rem' }}>
        <h3>Recent cases <Link to="/cases" className="small">All cases</Link></h3>
        {!cases.data?.length ? <p className="muted">No cases yet.</p> : (
          <div className="scroll"><table>
            <thead><tr><th>Employee</th><th>Missing</th><th>Where</th><th>When</th><th>Status</th></tr></thead>
            <tbody>{cases.data.slice(0, 6).map((v) => <tr key={v._id}><td>{v.employeeName ? <div className="who-cell"><Avatar name={v.employeeName} size={28} />{v.employeeName}</div> : <span className="muted">—</span>}</td><td>{v.missing}</td><td>{v.location}</td><td className="small nowrap">{fmtDate(v.occurredAt)}</td><td><Stamp status={v.status} /></td></tr>)}</tbody>
          </table></div>
        )}
      </div>
    </>
  );
}

// A short remark written from the facts of the case. The supervisor can reword it; an edited remark is never overwritten.
function RemarkBox({ v, onSaved }) {
  const [edit, setEdit] = useState(false);
  const [text, setText] = useState('');
  const [error, setError] = useState('');
  const save = async () => {
    setError('');
    try { await api(`/api/violations/${v._id}/remarks`, { method: 'POST', body: { remarks: text } }); setEdit(false); onSaved(); } catch (e) { setError(e.message); }
  };
  if (edit) {
    return (
      <div className="field"><label htmlFor={`r${v._id}`}>Remark</label><textarea id={`r${v._id}`} value={text} onChange={(e) => setText(e.target.value)} />
        <div className="actions"><button onClick={save}>Save remark</button><button className="alt" onClick={() => setEdit(false)}>Cancel</button></div><Err text={error} /></div>
    );
  }
  return (
    <div className="remark">{v.remarks || 'No remark yet.'}
      <small>{v.remarksEdited ? 'Edited by a supervisor' : 'Written automatically from the case details'} · <button className="link" onClick={() => { setText(v.remarks || ''); setEdit(true); }}>Edit</button></small></div>
  );
}

// ---- Review queue: where a caught violation arrives ------------------------------------------
function QueueCard({ v, employees, onDone }) {
  const [employeeId, setEmployeeId] = useState('');
  const [touched, setTouched] = useState(false);
  const [note, setNote] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const hint = v.suggested && employees.find((e) => e.employeeId === v.suggested.employeeId);
  useEffect(() => { if (hint && !touched) setEmployeeId(hint.id); }, [hint, touched]);
  const decide = async (decision) => {
    setBusy(true); setError('');
    try { await api(`/api/violations/${v._id}/decision`, { method: 'POST', body: { decision, employeeId, note } }); onDone(); }
    catch (e) { setError(e.message); } finally { setBusy(false); }
  };
  return (
    <article className="case">
      <Evidence path={v.evidencePath} contextPath={v.contextPath} />
      <div className="case-body">
        <div className="case-top"><span className="no">CASE {ticketNo(v.number)}</span><span>{v.catches > 1 && <Chip tone="bad">caught {v.catches} times today</Chip>} <Stamp status="Pending review" /></span></div>
        <div className="what">{v.missing}</div>
        <FaultBox missing={v.missing} />
        <div className="facts">
          <span>Detected <b>{v.workerRef}</b></span><span>When <b>{fmtDate(v.occurredAt)}</b></span>
          {v.location && <span>Where <b>{v.location}</b></span>}<span>Source <b>{v.source}</b></span>
        </div>
        <RemarkBox v={v} onSaved={onDone} />
        {v.suggested && <div className="note info">{v.suggested.dummy ? 'Made-up name for this person. The system does not know who they really are; the same footage always gets the same name' : 'Face match suggestion (not verified)'}: <b>{v.suggested.name}</b>{v.suggested.jobRole ? `, ${v.suggested.jobRole}` : ''}{v.suggested.dummy ? '' : ` (similarity ${v.suggested.score})`}. Check the picture before confirming. It can be wrong.</div>}
        <div className="actions" style={{ alignItems: 'flex-end' }}>
          <div><label htmlFor={`e${v._id}`}>Which employee is this?</label>
            <select id={`e${v._id}`} value={employeeId} onChange={(e) => { setTouched(true); setEmployeeId(e.target.value); }}>
              <option value="">Choose…</option>{employees.map((e) => <option key={e.id} value={e.id}>{e.name} ({e.employeeId}){e.jobRole ? ` · ${e.jobRole}` : ''}</option>)}
            </select></div>
          <div style={{ flex: 1, minWidth: 180 }}><label htmlFor={`n${v._id}`}>Note (optional)</label><input id={`n${v._id}`} value={note} onChange={(e) => setNote(e.target.value)} style={{ width: '100%' }} /></div>
        </div>
        <div className="actions">
          <button className="danger" disabled={busy || !employeeId} onClick={() => decide('confirm')}>Confirm violation</button>
          <button className="alt" disabled={busy} onClick={() => decide('dismiss')}>Dismiss: false alarm</button>
        </div>
        <Err text={error} />
      </div>
    </article>
  );
}

export function Queue({ onChanged }) {
  const queue = useLoad(() => api('/api/review/queue'), [], 8000);
  const team = useLoad(() => api('/api/employees'), []);
  const done = () => { queue.reload(); onChanged(); };
  return (
    <>
      <PageHead title="Review queue" sub="Cases the detector caught. Nothing is recorded against a person until you confirm it." />
      <div className="note">Look at the picture yourself. The detector can be wrong, and a dismissed case costs nobody anything.</div>
      <Err text={queue.error || team.error} />
      {queue.loading ? <p className="muted">Loading…</p> : !queue.data?.length ? <div className="empty">The queue is clear. New catches from the detector appear here by themselves.</div>
        : queue.data.map((v) => <QueueCard key={v._id} v={v} employees={team.data || []} onDone={done} />)}
    </>
  );
}

// ---- Penalties ------------------------------------------------------------------------------
function PenaltyRow({ p, onDone }) {
  const [note, setNote] = useState('');
  const [error, setError] = useState('');
  const nav = useNavigate();
  const act = async (decision) => {
    setError('');
    try { await api(`/api/penalties/${p._id}/decide`, { method: 'POST', body: { decision, note } }); onDone(); } catch (e) { setError(e.message); }
  };
  const choices = { Proposed: [['Issued', 'Issue penalty', 'danger'], ['Waived', 'Waive', 'alt']], Disputed: [['Issued', 'Uphold and issue', 'danger'], ['Waived', 'Waive', 'alt']], Issued: [['Paid', 'Mark as paid', 'ok'], ['Waived', 'Waive', 'alt']] }[p.status] || [];
  return (
    <article className="card">
      <div className="case-top"><div className="who-cell"><Avatar name={p.employeeName} /><div><b>{p.employeeName}</b><small>{fmtDate(p.createdAt)}</small></div></div><Stamp status={p.status} /></div>
      <div className="what" style={{ color: 'var(--ink)' }}>{money(p.amount, p.currency)}</div>
      <p className="small muted">{p.reason}</p>
      {p.status === 'Disputed' && p.note && <div className="note info">Employee says: {p.note}</div>}
      {choices.length > 0 && (
        <div className="actions" style={{ alignItems: 'flex-end' }}>
          <div style={{ flex: 1, minWidth: 200 }}><label htmlFor={`pn${p._id}`}>Your note</label><input id={`pn${p._id}`} value={note} onChange={(e) => setNote(e.target.value)} style={{ width: '100%' }} /></div>
          {choices.map(([d, label, cls]) => <button key={d} className={cls} onClick={() => act(d)}>{label}</button>)}
          <button className="alt" onClick={() => nav(`/employees/${p.employeeId}`)}>Open employee</button>
        </div>
      )}
      <Err text={error} />
    </article>
  );
}

const COUNTED_STATUSES = ['Confirmed', 'Acknowledged', 'Disputed', 'Resolved'];

// Put a penalty on an employee by ID. Only an employee with confirmed violations that no penalty covers yet can be given one.
function PutPenalty({ onDone }) {
  const [code, setCode] = useState('');
  const [found, setFound] = useState(null);
  const [picked, setPicked] = useState([]);
  const [amount, setAmount] = useState('');
  const [reason, setReason] = useState('');
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);
  const find = async (e) => {
    e?.preventDefault();
    setError(''); setMessage(''); setFound(null);
    try {
      const all = await api('/api/employees');
      const emp = all.find((x) => String(x.employeeId).toUpperCase() === code.trim().toUpperCase());
      if (!emp) throw new Error('No employee with that ID in your sector.');
      const prof = await api(`/api/employees/${emp.id}/profile`);
      const open = prof.violations.filter((v) => v.employeeId === emp.id && COUNTED_STATUSES.includes(v.status) && !v.penaltyId);
      setFound({ emp, open, currency: prof.currency });
      setPicked(open.map((v) => v._id));
      setAmount(''); setReason('');
    } catch (err) { setError(err.message); }
  };
  const issue = async () => {
    setError(''); setBusy(true);
    try {
      const body = { employeeId: found.emp.employeeId, violationIds: picked };
      if (amount !== '') body.amount = Number(amount);
      if (reason.trim()) body.reason = reason.trim();
      const p = await api('/api/penalties', { method: 'POST', body });
      setMessage(`Penalty of ${money(p.amount, p.currency)} issued to ${p.employeeName}. They have been notified and can dispute it.`);
      setFound(null); setCode('');
      onDone();
    } catch (err) { setError(err.message); }
    setBusy(false);
  };
  const toggle = (id) => setPicked((p) => (p.includes(id) ? p.filter((x) => x !== id) : [...p, id]));
  return (
    <article className="card">
      <h3>Put a penalty on an employee</h3>
      <p className="small muted">Enter the employee ID. A penalty can only be put on someone who has confirmed violations that no penalty covers yet. It is issued at once, the employee is told, and they can dispute it.</p>
      <form className="actions" style={{ alignItems: 'flex-end' }} onSubmit={find}>
        <div style={{ flex: 1, minWidth: 200 }}><label htmlFor="pp-id">Employee ID</label><input id="pp-id" value={code} onChange={(e) => setCode(e.target.value)} placeholder="for example E001" style={{ width: '100%' }} /></div>
        <button className="go" type="submit" disabled={!code.trim()}>Find employee</button>
      </form>
      {message && <div className="note info">{message}</div>}
      {found && (
        <>
          <div className="who-cell" style={{ margin: '12px 0' }}><Avatar name={found.emp.name} /><div><b>{found.emp.name}</b><small>{found.emp.employeeId} · {found.emp.jobRole || found.emp.department}</small></div></div>
          {!found.open.length ? <div className="empty">{found.emp.name} has no confirmed violation without a penalty, so there is nothing to base a penalty on.</div> : (
            <>
              <p className="small muted">Violations this penalty covers ({picked.length} of {found.open.length} chosen):</p>
              {found.open.map((v) => (
                <label key={v._id} style={{ display: 'flex', gap: 8, alignItems: 'center', margin: '4px 0' }}>
                  <input type="checkbox" checked={picked.includes(v._id)} onChange={() => toggle(v._id)} />
                  <span>#{v.number} · {v.missing} · {fmtDate(v.occurredAt)}{v.location ? ` · ${v.location}` : ''}</span>
                </label>
              ))}
              <div className="actions" style={{ alignItems: 'flex-end', marginTop: 10 }}>
                <div><label htmlFor="pp-amt">Amount ({found.currency})</label><input id="pp-amt" type="number" min="1" max="100000" value={amount} onChange={(e) => setAmount(e.target.value)} placeholder="policy default" /></div>
                <div style={{ flex: 1, minWidth: 220 }}><label htmlFor="pp-why">Reason (optional)</label><input id="pp-why" value={reason} onChange={(e) => setReason(e.target.value)} placeholder="written from the violations if left empty" style={{ width: '100%' }} /></div>
                <button className="danger" onClick={issue} disabled={busy || !picked.length}>Issue penalty</button>
              </div>
            </>
          )}
        </>
      )}
      <Err text={error} />
    </article>
  );
}

export function Penalties({ onChanged }) {
  const [tab, setTab] = useState('open');
  const list = useLoad(() => api('/api/penalties'), [], 10000);
  const rows = (list.data || []).filter((p) => (tab === 'open' ? ['Proposed', 'Disputed'].includes(p.status) : tab === 'issued' ? p.status === 'Issued' : true));
  const done = () => { list.reload(); onChanged(); };
  return (
    <>
      <PageHead title="Penalties" sub="The system proposes penalties after repeat violations, and you can also put one on an employee ID yourself. The employee can dispute it." />
      <div className="note info">Amounts are example values from <span className="mono">api/config/policy.json</span>. Management sets the real ones, and HR confirms whether pay can lawfully be reduced.</div>
      <div className="tabs">{[['open', 'Needs your decision'], ['issued', 'Issued'], ['all', 'Everything'], ['put', 'Put a penalty']].map(([k, label]) => <button key={k} className={tab === k ? 'on' : ''} onClick={() => setTab(k)}>{label}</button>)}</div>
      <Err text={list.error} />
      {tab === 'put' ? <PutPenalty onDone={done} /> : list.loading ? <p className="muted">Loading…</p> : !rows.length ? <div className="empty">Nothing here.</div> : rows.map((p) => <PenaltyRow key={p._id} p={p} onDone={done} />)}
    </>
  );
}

// ---- All cases ------------------------------------------------------------------------------
export function Cases() {
  const [status, setStatus] = useState('');
  const [text, setText] = useState('');
  const list = useLoad(() => api(`/api/violations${status ? `?status=${encodeURIComponent(status)}` : ''}`), [status], 15000);
  const rows = (list.data || []).filter((v) => `${v.employeeName} ${v.missing} ${v.location}`.toLowerCase().includes(text.toLowerCase()));
  return (
    <>
      <PageHead title="All cases" sub="Every reviewed case, with who, what and where.">
        <input className="search" placeholder="Search name, item or place" value={text} onChange={(e) => setText(e.target.value)} />
        <select aria-label="Status" value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="">All reviewed</option>{['Confirmed', 'Acknowledged', 'Disputed', 'Dismissed'].map((s) => <option key={s}>{s}</option>)}
        </select>
      </PageHead>
      <Err text={list.error} />
      {list.loading ? <p className="muted">Loading…</p> : !rows.length ? <div className="empty">No cases match.</div> : (
        <div className="scroll"><table>
          <thead><tr><th>No.</th><th>Picture</th><th>Employee</th><th>Missing</th><th>Where</th><th>When</th><th>Status</th><th>Reviewed by</th><th>Notice</th></tr></thead>
          <tbody>{rows.map((v) => (
            <tr key={v._id}><td className="mono">{ticketNo(v.number)}</td><td><Thumb path={v.evidencePath} /></td>
              <td>{v.employeeName ? <Link to={`/employees/${v.employeeId}`}><div className="who-cell"><Avatar name={v.employeeName} size={28} />{v.employeeName}</div></Link> : <span className="muted">—</span>}</td>
              <td><b>{v.missing}</b>{v.remarks && <div className="small muted" style={{ maxWidth: 360 }}>{v.remarks}</div>}</td><td>{v.location}</td><td className="small nowrap">{fmtDate(v.occurredAt)}{v.catches > 1 && <><br /><span className="small muted">caught {v.catches} times</span></>}</td><td><Stamp status={v.status} /></td><td>{v.reviewedBy}</td><td><NoticeButton path={`/api/violations/${v._id}/notice.pdf`} number={v.number} label="PDF" /></td></tr>
          ))}</tbody>
        </table></div>
      )}
    </>
  );
}
