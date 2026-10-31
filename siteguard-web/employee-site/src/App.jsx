import { Fragment, useState } from 'react';
import { Link, Navigate, Route, Routes } from 'react-router-dom';
import { api, download } from '../../shared/api.js';
import { toast } from '../../shared/theme.js';
import { AccuracyPage } from '../../shared/about.jsx';
import { Login, useAuth } from '../../shared/auth.jsx';
import { Avatar, Chip, Err, Evidence, FaultBox, Kpi, NoticeButton, Notifications, PageHead, Shell, Stamp, Thumb, fmtDate, fmtDay, money, monthName, ticketNo, useLoad } from '../../shared/ui.jsx';

function ViolationCard({ v, onChanged }) {
  const [disputing, setDisputing] = useState(false);
  const [note, setNote] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const respond = async (action) => {
    setBusy(true); setError('');
    try { await api(`/api/violations/${v._id}/respond`, { method: 'POST', body: { action, note } }); setDisputing(false); onChanged(); }
    catch (e) { setError(e.message); } finally { setBusy(false); }
  };
  return (
    <article className="case">
      <Evidence path={v.evidencePath} contextPath={v.contextPath} />
      <div className="case-body">
        <div className="case-top"><span className="no">VIOLATION {ticketNo(v.number)}</span><Stamp status={v.status} /></div>
        <div className="what">{v.missing}</div>
        <FaultBox missing={v.missing} />
        <div className="facts">
          <span>When <b>{fmtDate(v.occurredAt)}</b></span>
          {v.location && <span>Where <b>{v.location}</b></span>}
          {v.catches > 1 && <span>Caught <b>{v.catches} times</b> that day</span>}
          <span>Confirmed by <b>{v.reviewedBy}</b></span>
        </div>
        {v.remarks && <div className="remark">{v.remarks}</div>}
        <div className="actions"><NoticeButton path={`/api/me/violations/${v._id}/notice.pdf`} number={v.number} /></div>
        {v.status === 'Confirmed' && !disputing && (
          <div className="actions">
            <button disabled={busy} onClick={() => respond('acknowledge')}>I acknowledge this</button>
            <button className="alt" onClick={() => setDisputing(true)}>I want to dispute this</button>
          </div>
        )}
        {disputing && (
          <div className="field" style={{ marginTop: '.7rem' }}>
            <label htmlFor={`n${v._id}`}>Why do you dispute it? (for example: wrong person, or I was wearing it)</label>
            <textarea id={`n${v._id}`} value={note} onChange={(e) => setNote(e.target.value)} />
            <div className="actions"><button className="go" disabled={busy || !note.trim()} onClick={() => respond('dispute')}>Send to supervisor</button><button className="alt" onClick={() => setDisputing(false)}>Cancel</button></div>
          </div>
        )}
        <Err text={error} />
        <ul className="log">{(v.log || []).map((l, i) => <li key={i}>{fmtDate(l.at)} · {l.by}: {l.action}{l.note ? ` (${l.note})` : ''}</li>)}</ul>
      </div>
    </article>
  );
}

function Home({ user }) {
  const summary = useLoad(() => api('/api/me/summary'), [], 15000);
  const list = useLoad(() => api('/api/me/violations'), [], 15000);
  const pay = useLoad(() => api('/api/me/salary'), [], 30000);
  const profile = useLoad(() => api('/api/me/profile'), []);
  const alerts = useLoad(() => api('/api/notifications'), [], 8000);
  const latestAlert = (alerts.data || []).find((n) => /^Safety alert/.test(n.message) && Date.now() - new Date(n.at) < 24 * 3600000);
  const s = summary.data;
  const window_ = (s?.windowDays || 30) * 86400000;
  const recent = (list.data || []).filter((v) => Date.now() - new Date(v.occurredAt) <= window_);
  const open = recent.filter((v) => !v.penaltyId).length;
  const slip = pay.data?.payslips?.[0];
  const good = s && s.awaitingResponse === 0 && s.penaltiesIssued === 0;
  return (
    <>
      {latestAlert && <div className="alertbar person" role="alert"><span className="alertbar-dot" /><div><b>SAFETY ALERT</b><br />{latestAlert.message} <span style={{ opacity: .85 }}>({fmtDate(latestAlert.at)})</span></div></div>}
      <div className="hero">
        <Avatar name={user.name} size={72} photo={profile.data?.photo} />
        <div><h1>Hello, {user.name.split(' ')[0]}</h1><p>{profile.data?.jobRole || 'Employee'}{profile.data?.department ? ` · ${profile.data.department}` : ''}{profile.data?.field ? ` · ${profile.data.field}` : ''} · <span className="mono">{user.employeeId}</span></p>{profile.data?.className && <p className="small muted" style={{ margin: 0 }}>{profile.data.className}</p>}</div>
        <span className="sp" />
        {s && (good ? <Chip tone="ok">In good standing</Chip> : <Chip tone="warn">{s.awaitingResponse ? `${s.awaitingResponse} waiting for your response` : 'Penalty issued'}</Chip>)}
      </div>
      <Err text={summary.error || list.error || pay.error} />
      {s?.awaitingResponse > 0 && <div className="note" style={{ display: 'flex', gap: '1rem', alignItems: 'center', flexWrap: 'wrap' }}><span><b>{s.awaitingResponse} {s.awaitingResponse > 1 ? 'violations are' : 'violation is'} waiting for your reply.</b> Acknowledge {s.awaitingResponse > 1 ? 'them' : 'it'} or dispute {s.awaitingResponse > 1 ? 'them' : 'it'} with a reason.</span><Link to="/violations" className="btn" style={{ textDecoration: 'none' }}>Reply now</Link></div>}
      {s && (
        <div className="grid g4" style={{ marginBottom: '1rem' }}>
          <Kpi icon="alert" tone={recent.length ? 'hot' : 'ok'} label={`Violations, last ${s.windowDays} days`} value={recent.length} />
          <Kpi icon="clock" tone={s.awaitingResponse ? 'hot' : 'ok'} label="Waiting for your response" value={s.awaitingResponse} />
          <Kpi icon="shield" tone={s.penaltiesIssued ? 'bad' : 'ok'} label="Penalties issued" value={s.penaltiesIssued} />
          <Kpi icon="wallet" tone="info" label="Net pay this month" value={slip ? money(slip.net, s.currency) : '—'} />
        </div>
      )}
      <div className="split">
        <div className="card">
          <h3>Latest violations <Link to="/violations" className="small">See all</Link></h3>
          {list.loading ? <p className="muted">Loading…</p> : !list.data?.length ? <div className="empty">No violations on your record. Keep it that way.</div> : (
            <div className="scroll"><table>
              <thead><tr><th>Picture</th><th>Missing</th><th>When</th><th>Status</th></tr></thead>
              <tbody>{list.data.slice(0, 5).map((v) => <tr key={v._id}><td><Thumb path={v.evidencePath} /></td><td><b>{v.missing}</b><br /><span className="small muted">{v.location}</span></td><td className="small nowrap">{fmtDate(v.occurredAt)}</td><td><Stamp status={v.status} /></td></tr>)}</tbody>
            </table></div>
          )}
        </div>
        <div>
          {s && (
            <div className="card">
              <h3>Toward a penalty review</h3>
              <div className="meter">{Array.from({ length: s.proposeAt }, (_, i) => <span key={i} className={`pip ${i < Math.min(open, s.proposeAt) ? 'on' : ''}`} />)}</div>
              <p className="small muted" style={{ margin: 0 }}>{open} of {s.proposeAt}. After {s.proposeAt} confirmed violations within {s.windowDays} days a supervisor reviews a penalty. It is never automatic, and you can dispute it.</p>
            </div>
          )}
          {slip && (
            <div className="card">
              <h3>{monthName(slip.month)} <Link to="/salary" className="small">Details</Link></h3>
              <table><tbody>
                <tr><td>Monthly salary</td><td className="right money">{money(slip.base, pay.data.currency)}</td></tr>
                <tr><td>Penalties issued</td><td className="right money" style={{ color: slip.deductions ? 'var(--bad)' : undefined }}>{slip.deductions ? `− ${money(slip.deductions, pay.data.currency)}` : '—'}</td></tr>
                <tr><td><b>Net pay</b></td><td className="right money"><b>{money(slip.net, pay.data.currency)}</b></td></tr>
              </tbody></table>
            </div>
          )}
        </div>
      </div>
    </>
  );
}

const HOW = { 'live camera': 'Live camera', video: 'Video', 'photo upload': 'Photo', cctv: 'CCTV camera', demo: 'Demo data' };
const STATUS_NOTE = { 'Pending review': 'Waiting for a supervisor to confirm', Confirmed: 'Confirmed by a supervisor', Acknowledged: 'Acknowledged by you', Disputed: 'You disputed this', Dismissed: 'Dismissed by a supervisor as a false alarm' };

// Everything caught about this employee, newest first, as a timeline: one card per incident (the first catch, with any later catches the same day
// folded in), its picture, where and how, and what a supervisor decided.
const TONE = { 'Pending review': 'warn', Confirmed: 'bad', Acknowledged: 'ok', Disputed: 'info', Dismissed: '' };
function Feed() {
  const feed = useLoad(() => api('/api/me/feed'), [], 10000);
  const [show, setShow] = useState('all');
  const day = (iso) => new Date(iso).toLocaleDateString([], { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' });
  const time = (iso) => new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  const cases = new Map();
  (feed.data || []).forEach((e) => { const c = cases.get(e.caseNumber) || { first: null, again: [] }; if (e.kind === 'caught') c.first = e; else c.again.push(e); cases.set(e.caseNumber, c); });
  const all = [...cases.values()].filter((c) => c.first).sort((x, y) => new Date(y.first.at) - new Date(x.first.at));
  const list = all.filter((c) => show === 'all' || (show === 'open' ? ['Pending review', 'Confirmed'].includes(c.first.status) : c.first.status === show));
  const groups = [];
  list.forEach((c) => { const d = day(c.first.at); const last = groups[groups.length - 1]; if (last && last.d === d) last.items.push(c); else groups.push({ d, items: [c] }); });
  const waiting = all.filter((c) => ['Pending review', 'Confirmed'].includes(c.first.status)).length;
  return (
    <>
      <PageHead title="My feed" sub="Every time the cameras caught you without required gear: when, where and how, and what a supervisor decided.">
        <select value={show} onChange={(e) => setShow(e.target.value)} aria-label="Show"><option value="all">Everything</option><option value="open">Needs a decision or your reply</option><option value="Acknowledged">Acknowledged</option><option value="Disputed">Disputed</option><option value="Dismissed">Dismissed as false alarms</option></select>
      </PageHead>
      <div className="note info">A catch here is only an alert. It becomes a violation on your record when a supervisor confirms it, and you can dispute it.{waiting ? ` ${waiting} ${waiting > 1 ? 'are' : 'is'} still waiting.` : ''}</div>
      <Err text={feed.error} />
      {feed.loading ? <p className="muted">Loading…</p> : !groups.length ? <div className="empty">{all.length ? 'Nothing matches this filter.' : 'Nothing has been caught about you. Keep it that way.'}</div> : groups.map((g) => (
        <section key={g.d} className="tl-day">
          <h3 className="tl-head">{g.d} <span className="small muted">{g.items.length} {g.items.length > 1 ? 'incidents' : 'incident'}</span></h3>
          <ol className="timeline">{g.items.map(({ first: e, again }) => (
            <li key={e.caseNumber} className="tl-item">
              <span className={`tl-dot ${TONE[e.status] || ''}`} aria-hidden="true" />
              <article className="tl-card">
                <div className="tl-main">
                  <div className="tl-top"><b>{e.text}</b><Stamp status={e.status} /></div>
                  <div className="facts"><span><b className="mono">{time(e.at)}</b></span>{e.location && <span>at <b>{e.location}</b></span>}<span>{HOW[e.source] || e.source}</span><span className="muted">Case {ticketNo(e.caseNumber)}</span></div>
                  {e.remarks && <div className="remark">{e.remarks}</div>}
                  <p className="small muted" style={{ margin: '.4rem 0 0' }}>{STATUS_NOTE[e.status]}</p>
                  {again.length > 0 && <p className="small" style={{ margin: '.4rem 0 0' }}><b>Caught {again.length} more {again.length > 1 ? 'times' : 'time'} that day</b> <span className="muted">(last at {time(again.reduce((m, x) => (new Date(x.at) > new Date(m.at) ? x : m)).at)}). It still counts as one violation for the day.</span></p>}
                  {['Confirmed'].includes(e.status) && <p className="small" style={{ margin: '.5rem 0 0' }}><Link to="/violations">Open it to acknowledge or dispute</Link></p>}
                </div>
                {e.evidencePath && <div className="tl-pic"><Thumb path={e.evidencePath} /></div>}
              </article>
            </li>
          ))}</ol>
        </section>
      ))}
    </>
  );
}

function Violations() {
  const list = useLoad(() => api('/api/me/violations'), [], 15000);
  return (
    <>
      <PageHead title="My violations" sub="Only violations a supervisor has checked and confirmed appear here. Acknowledge each one or dispute it.">
        <button className="go" onClick={async () => { try { await download('/api/me/report.pdf', 'my-safety-report.pdf'); toast('Your report was downloaded.'); } catch (err) { toast(err.message); } }}>Download my report (PDF)</button>
      </PageHead>
      <Err text={list.error} />
      {list.loading ? <p className="muted">Loading…</p> : !list.data?.length ? <div className="empty">Nothing on your record.</div> : list.data.map((v) => <ViolationCard key={v._id} v={v} onChanged={list.reload} />)}
    </>
  );
}

function Salary() {
  const pay = useLoad(() => api('/api/me/salary'), [], 30000);
  const [open, setOpen] = useState('');
  const d = pay.data;
  const cur = d?.currency;
  const now = d?.payslips?.[0];
  return (
    <>
      <PageHead title="My salary" sub="Your monthly pay and anything a supervisor has issued against it." />
      <Err text={pay.error} />
      {pay.loading ? <p className="muted">Loading…</p> : d && (
        <>
          <div className="grid g3" style={{ marginBottom: '1rem' }}>
            <Kpi icon="wallet" label="Monthly salary" value={money(d.monthlySalary, cur)} />
            <Kpi icon="shield" tone={now.deductions ? 'bad' : 'ok'} label={`Penalties issued, ${monthName(now.month)}`} value={now.deductions ? `− ${money(now.deductions, cur)}` : money(0, cur)} />
            <Kpi icon="check" tone="info" label="Net pay this month" value={money(now.net, cur)} />
          </div>
          <div className="card">
            <h3>Pay history</h3>
            <div className="scroll"><table>
              <thead><tr><th>Month</th><th className="right">Salary</th><th className="right">Penalties issued</th><th className="right">Net pay</th><th /></tr></thead>
              <tbody>{d.payslips.map((p) => (
                <Fragment key={p.month}>
                  <tr><td><b>{monthName(p.month)}</b></td><td className="right money">{money(p.base, cur)}</td><td className="right money">{p.deductions ? `− ${money(p.deductions, cur)}` : '—'}</td><td className="right money"><b>{money(p.net, cur)}</b></td>
                    <td className="right">{p.items.length ? <button className="link" onClick={() => setOpen(open === p.month ? '' : p.month)}>{open === p.month ? 'Hide' : 'Why?'}</button> : null}</td></tr>
                  {open === p.month && p.items.map((i) => <tr key={i.id}><td colSpan="5" className="small muted" style={{ background: 'var(--soft)' }}>{money(i.amount, cur)} · {i.reason}</td></tr>)}
                </Fragment>
              ))}</tbody>
            </table></div>
          </div>
          <div className="note info">The salary figures are demo data. A penalty only appears here after a supervisor has approved it, and you can dispute it. Whether pay can lawfully be reduced for a penalty is for HR and the company to confirm.</div>
        </>
      )}
    </>
  );
}

function PenaltyCard({ p, onChanged }) {
  const [open, setOpen] = useState(false);
  const [note, setNote] = useState('');
  const [error, setError] = useState('');
  const dispute = async () => {
    setError('');
    try { await api(`/api/penalties/${p._id}/dispute`, { method: 'POST', body: { note } }); setOpen(false); onChanged(); } catch (e) { setError(e.message); }
  };
  return (
    <article className="card">
      <div className="case-top"><span className="no">PENALTY · {fmtDay(p.createdAt)}</span><Stamp status={p.status} /></div>
      <div className="what" style={{ color: 'var(--ink)' }}>{money(p.amount, p.currency)}</div>
      <p className="small muted">{p.reason}</p>
      {p.decidedBy && <p className="small muted">Decided by {p.decidedBy}, {fmtDate(p.decidedAt)}{p.note ? `: ${p.note}` : ''}</p>}
      {p.status === 'Issued' && !open && <button className="alt" onClick={() => setOpen(true)}>Dispute this penalty</button>}
      {open && <div className="field"><label htmlFor={`p${p._id}`}>Why do you dispute it?</label><textarea id={`p${p._id}`} value={note} onChange={(e) => setNote(e.target.value)} /><div className="actions"><button className="go" disabled={!note.trim()} onClick={dispute}>Send dispute</button><button className="alt" onClick={() => setOpen(false)}>Cancel</button></div></div>}
      <Err text={error} />
    </article>
  );
}

function Penalties() {
  const list = useLoad(() => api('/api/me/penalties'), [], 15000);
  return (
    <>
      <PageHead title="My penalties" sub="A penalty shows here only after your supervisor has approved it." />
      <Err text={list.error} />
      {list.loading ? <p className="muted">Loading…</p> : !list.data?.length ? <div className="empty">No penalties.</div> : list.data.map((p) => <PenaltyCard key={p._id} p={p} onChanged={list.reload} />)}
    </>
  );
}

export default function App() {
  const { user, logout, autoOn } = useAuth();
  const summary = useLoad(() => (user ? api('/api/me/summary') : Promise.resolve(null)), [user?.id], 15000);
  if (!user && window.location.pathname === '/about') return <div className="page" style={{ maxWidth: 900, margin: '0 auto' }}><AccuracyPage standalone /></div>;
  if (!user) return <Login title="Your safety record and pay, in one place." subtitle="Employee portal" points={['See every violation with its picture', 'Acknowledge it or dispute it', 'Track your salary and any penalty']} demo={['E001', '123456789']} demoNote="Dummy accounts: every employee, E001 to E120, signs in with their code and the same password," />;
  return (
    <Shell site="SiteGuard" tag="Employee portal" user={user} onLogout={autoOn ? undefined : logout}
      nav={[
        { to: '/', label: 'Overview', icon: 'dashboard' },
        { to: '/feed', label: 'My feed', icon: 'clock' },
        { to: '/violations', label: 'My violations', icon: 'alert', count: summary.data?.awaitingResponse },
        { to: '/salary', label: 'Salary', icon: 'wallet' },
        { to: '/penalties', label: 'Penalties', icon: 'shield' },
        { to: '/notifications', label: 'Notifications', icon: 'bell' },
        { to: '/about', label: 'About accuracy', icon: 'dashboard' },
      ]}>
      <Routes>
        <Route path="/" element={<Home user={user} />} />
        <Route path="/feed" element={<Feed />} />
        <Route path="/violations" element={<Violations />} />
        <Route path="/salary" element={<Salary />} />
        <Route path="/penalties" element={<Penalties />} />
        <Route path="/notifications" element={<Notifications />} />
        <Route path="/about" element={<AccuracyPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Shell>
  );
}
