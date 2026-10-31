import { useState } from 'react';
import { api } from '../../shared/api.js';
import { useAuth } from '../../shared/auth.jsx';
import { Avatar, Chip, Err, PageHead, useLoad } from '../../shared/ui.jsx';

// Sectors are kinds of work (construction, wireman, lineman, ...). Each has its own list of gear that must be worn and its own
// supervisors, who see only the cases of their sector. Only the head supervisor creates sectors and supervisor accounts.
const ITEMS = [['helmet', 'Helmet'], ['vest', 'Vest'], ['goggles', 'Goggles'], ['gloves', 'Gloves'], ['boots', 'Boots']];
const UNMEASURED = new Set(['goggles', 'gloves', 'boots']);
const EMPTY = { name: '', conditionClass: '', location: '', requiredItems: ['helmet', 'vest'] };

function SectorForm({ initial = EMPTY, submitLabel, onSubmit, onCancel }) {
  const [form, setForm] = useState(initial);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const toggle = (k) => setForm((f) => ({ ...f, requiredItems: f.requiredItems.includes(k) ? f.requiredItems.filter((x) => x !== k) : [...f.requiredItems, k] }));
  const submit = async (e) => {
    e.preventDefault(); setBusy(true); setError('');
    try { await onSubmit(form); if (!initial.id) setForm(EMPTY); } catch (err) { setError(err.message); } finally { setBusy(false); }
  };
  return (
    <form onSubmit={submit}>
      <div className="actions" style={{ alignItems: 'flex-end', marginTop: 0 }}>
        <div><label htmlFor="sn">Sector (kind of work)</label><input id="sn" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="e.g. Wireman" /></div>
        <div><label htmlFor="sc">Conditions class</label><input id="sc" value={form.conditionClass} onChange={(e) => setForm({ ...form, conditionClass: e.target.value })} placeholder="e.g. Class B: electrical wiring" style={{ minWidth: 260 }} /></div>
        <div><label htmlFor="sl">Place shown on cases</label><input id="sl" value={form.location} onChange={(e) => setForm({ ...form, location: e.target.value })} placeholder="e.g. Wiring block" /></div>
      </div>
      <label style={{ marginTop: '.8rem' }}>Gear that must be worn in this sector</label>
      <div className="actions" style={{ marginTop: 0 }}>{ITEMS.map(([k, label]) => <label key={k} className="inline"><input type="checkbox" checked={form.requiredItems.includes(k)} onChange={() => toggle(k)} />{label}{UNMEASURED.has(k) && <span className="small muted"> (accuracy not measured)</span>}</label>)}</div>
      <Err text={error} />
      <div className="actions"><button className="go" disabled={busy}>{submitLabel}</button>{onCancel && <button type="button" className="alt" onClick={onCancel}>Cancel</button>}</div>
    </form>
  );
}

// The fields (areas of the site) and classes of a sector, kept by that sector's supervisor right here in the panel.
function OptionsEditor({ sector, onSaved }) {
  const [fields, setFields] = useState(sector.fields || []);
  const [classes, setClasses] = useState(sector.classes || []);
  const [add, setAdd] = useState({ field: '', cls: '' });
  const [msg, setMsg] = useState('');
  const save = async (f, c) => { setMsg(''); try { await api(`/api/sectors/${sector.id}/options`, { method: 'POST', body: { fields: f, classes: c } }); setMsg('Saved.'); onSaved(); } catch (e) { setMsg(e.message); } };
  const List = ({ title, items, set, other, keyName, ph }) => (
    <div style={{ flex: 1, minWidth: 260 }}>
      <label>{title}</label>
      <div className="scene-chips" style={{ margin: '.3rem 0' }}>{items.map((x) => <Chip key={x} tone="info">{x} <button className="link" title="Remove" onClick={() => { const next = items.filter((y) => y !== x); set(next); save(keyName === 'field' ? next : other, keyName === 'field' ? other : next); }}>×</button></Chip>)}{!items.length && <span className="muted small">none yet</span>}</div>
      <div className="actions" style={{ marginTop: 0 }}><input value={add[keyName === 'field' ? 'field' : 'cls']} placeholder={ph} onChange={(e) => setAdd({ ...add, [keyName === 'field' ? 'field' : 'cls']: e.target.value })} />
        <button className="alt sm" onClick={() => { const v = add[keyName === 'field' ? 'field' : 'cls'].trim(); if (!v || items.includes(v)) return; const next = [...items, v]; set(next); setAdd({ field: '', cls: '' }); save(keyName === 'field' ? next : other, keyName === 'field' ? other : next); }}>Add</button></div>
    </div>
  );
  return (
    <section className="card" style={{ marginBottom: '1rem' }}>
      <h3>{sector.name}: fields and classes</h3>
      <p className="small muted">Fields are the areas of this site where your workers work (employees are placed in one). Classes are the work conditions they fall under. Only the supervisor of this sector and the head supervisor can change them.</p>
      <div className="actions" style={{ alignItems: 'flex-start', marginTop: 0 }}>
        <List title="Fields" items={fields} set={setFields} other={classes} keyName="field" ph="e.g. Block C" />
        <List title="Classes" items={classes} set={setClasses} other={fields} keyName="class" ph="e.g. Class D: confined space" />
      </div>
      {msg && <p className="small muted">{msg}</p>}
    </section>
  );
}

export function Sectors() {
  const { user } = useAuth();
  const sectors = useLoad(() => api('/api/sectors'), [], 20000);
  const sups = useLoad(() => api('/api/supervisors'), [], 20000);
  const [editing, setEditing] = useState('');
  const [made, setMade] = useState(null);
  const [form, setForm] = useState({ name: '', sectorId: '', password: '', code: '' });
  const [error, setError] = useState('');
  const admin = user.isAdmin;
  const reload = () => { sectors.reload(); sups.reload(); };

  const createSupervisor = async (e) => {
    e.preventDefault(); setError(''); setMade(null);
    try { setMade(await api('/api/supervisors', { method: 'POST', body: form })); setForm({ name: '', sectorId: form.sectorId, password: '', code: '' }); reload(); } catch (err) { setError(err.message); }
  };

  return (
    <>
      <PageHead title="Sectors and supervisors" sub="A sector is a kind of work. Each one has its own required gear and its own supervisors, who see only their own sector's cases." />
      <div className="note info">The gear lists below are starting values. Your site's safety officer confirms the real list for each kind of work, and the head supervisor can change it here at any time.</div>
      {!admin && <div className="note">You are signed in as the supervisor of <b>{user.sectorName || 'your sector'}</b>. You can change the requirements, fields and classes of your own sector. Only the head supervisor can add other sectors and supervisors.</div>}
      <Err text={sectors.error || sups.error} />
      {(sectors.data || []).filter((s) => admin || s.id === user.sectorId).map((s) => <OptionsEditor key={s.id + (s.fields || []).join() + (s.classes || []).join()} sector={s} onSaved={reload} />)}

      <div className="scroll"><table>
        <thead><tr><th>Sector</th><th>Required gear</th><th>Place on cases</th><th>Supervisors</th><th className="right">Cases</th><th /></tr></thead>
        <tbody>{(sectors.data || []).map((s) => (
          editing === s.id ? (
            <tr key={s.id}><td colSpan="6"><SectorForm initial={{ ...s }} submitLabel="Save changes" onCancel={() => setEditing('')} onSubmit={async (f) => { await api(`/api/sectors/${s.id}`, { method: 'POST', body: f }); setEditing(''); reload(); }} /></td></tr>
          ) : (
            <tr key={s.id}>
              <td><b>{s.name}</b><div className="small muted">{s.conditionClass}</div></td>
              <td><div className="scene-chips">{s.requiredItems.map((i) => <Chip key={i} tone="info">{i}</Chip>)}</div></td>
              <td>{s.location || '—'}</td>
              <td>{s.supervisors.length ? s.supervisors.map((u) => <div key={u.id} className="who-cell" style={{ marginBottom: 2 }}><Avatar name={u.name} size={24} /><span>{u.name} <span className="mono small muted">{u.employeeId}</span></span></div>) : <span className="muted">none yet</span>}</td>
              <td className="right">{s.cases}</td>
              <td className="right">{(admin || s.id === user.sectorId) && <button className="alt sm" onClick={() => setEditing(s.id)}>Edit requirements</button>}</td>
            </tr>
          )
        ))}</tbody>
      </table></div>

      {admin && (
        <>
          <section className="card" style={{ marginTop: '1rem' }}>
            <h3>Add a sector</h3>
            <SectorForm submitLabel="Add sector" onSubmit={async (f) => { await api('/api/sectors', { method: 'POST', body: f }); reload(); }} />
          </section>

          <section className="card">
            <h3>Create a supervisor account</h3>
            <p className="small muted">Choose the kind of work this supervisor looks after. The account code is made for you; the password is the code followed by @123 unless you type another.</p>
            <form onSubmit={createSupervisor}>
              <div className="actions" style={{ alignItems: 'flex-end', marginTop: 0 }}>
                <div><label htmlFor="un">Name</label><input id="un" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></div>
                <div><label htmlFor="us">Sector</label>
                  <select id="us" value={form.sectorId} onChange={(e) => setForm({ ...form, sectorId: e.target.value })}><option value="">Choose…</option>{(sectors.data || []).map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}</select></div>
                <div><label htmlFor="uc">Code (3 letters, optional)</label><input id="uc" value={form.code} maxLength={3} onChange={(e) => setForm({ ...form, code: e.target.value.toUpperCase() })} placeholder="made for you" style={{ width: 110 }} /></div>
                <div><label htmlFor="up2">Password (optional)</label><input id="up2" type="password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} autoComplete="new-password" /></div>
                <button className="go">Create account</button>
              </div>
              <Err text={error} />
            </form>
            {made && <div className="note info" style={{ marginTop: '.8rem' }}>Account created for <b>{made.name}</b> ({made.sectorName}). Sign-in code <span className="mono"><b>{made.employeeId}</b></span> and password <span className="mono"><b>{made.password}</b></span>. Employees this supervisor adds get IDs that start with <span className="mono"><b>{made.code}</b></span> (for example <span className="mono">{made.code}101</span>). Pass these on now: the password is not shown again.</div>}
          </section>
        </>
      )}

      <h3 style={{ marginTop: '1.2rem' }}>All supervisors</h3>
      <div className="scroll"><table>
        <thead><tr><th>Supervisor</th><th>Sign-in</th><th>Employee ID prefix</th><th>Sector</th><th>Role</th></tr></thead>
        <tbody>{(sups.data || []).filter((u) => !u.pending).map((u) => (
          <tr key={u.id}><td><div className="who-cell"><Avatar name={u.name} size={28} />{u.name}</div></td><td className="mono">{u.employeeId}</td><td className="mono"><b>{u.code || '—'}</b></td><td>{u.sectorName || '—'}</td><td>{u.isAdmin ? <Chip tone="info">Head supervisor</Chip> : 'Supervisor'}</td></tr>
        ))}</tbody>
      </table></div>
    </>
  );
}
