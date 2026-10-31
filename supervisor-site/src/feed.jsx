import { useState } from 'react';
import { api } from '../../shared/api.js';
import { useAuth } from '../../shared/auth.jsx';
import { DetectDesk } from '../../shared/detect.jsx';
import { Err, Stamp, Thumb, useLoad } from '../../shared/ui.jsx';

const when = (iso) => new Date(iso).toLocaleString([], { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' });
const gear = (r) => String(r.violation || '').split(/\s*[,+]\s*/).filter(Boolean).length;
// One list, sorted the way the supervisor chooses.
const SORTS = {
  new: ['Newest first', (a, b) => new Date(b.at) - new Date(a.at)],
  serious: ['Most items missing first', (a, b) => gear(b) - gear(a) || new Date(b.at) - new Date(a.at)],
  person: ['By person (A to Z)', (a, b) => String(a.name || '~').localeCompare(String(b.name || '~')) || new Date(b.at) - new Date(a.at)],
  waiting: ['Waiting for review first', (a, b) => (b.status === 'Pending review') - (a.status === 'Pending review') || new Date(b.at) - new Date(a.at)],
};

function RecentCatches({ sector }) {
  const log = useLoad(() => api('/api/log'), [], 6000);
  const [sort, setSort] = useState('new');
  const all = (log.data || []).filter((r) => r.kind === 'Violation');
  const list = [...all].sort(SORTS[sort][1]).slice(0, 12);
  return (
    <section className="card">
      <h3>Catches in {sector.name} <select value={sort} onChange={(e) => setSort(e.target.value)} aria-label="Sort the list" style={{ fontSize: '.8rem', padding: '.2rem .5rem' }}>{Object.entries(SORTS).map(([k, [label]]) => <option key={k} value={k}>{label}</option>)}</select></h3>
      <p className="small muted" style={{ margin: '0 0 .6rem' }}>Showing {list.length} of {all.length}, from every input (uploads, laptop camera, phone camera).</p>
      {!list.length ? <p className="muted small">Nothing caught yet.</p> : (
        <ol className="loglist" style={{ listStyle: 'none', margin: 0, padding: 0 }}>{list.map((r, i) => (
          <li key={r.key} className="logrow" style={{ gridTemplateColumns: 'auto auto 1fr auto' }}>
            <span className="rank">{i + 1}</span><Thumb path={r.image} />
            <div><b>{r.violation}</b><div className="small muted">{r.name || 'Not identified'}{r.userId ? ` · ${r.userId}` : ''} · {when(r.at)}{r.location ? ` · ${r.location}` : ''}</div></div>
            <Stamp status={r.status} />
          </li>
        ))}</ol>
      )}
    </section>
  );
}

// The supervisor's feed page: the same inputs as the detection desk (upload, laptop camera, phone camera), fixed to the supervisor's own sector.
// The head supervisor can pick any sector.
export function LiveFeed() {
  const { user } = useAuth();
  const sectors = useLoad(() => api('/api/sectors'), []);
  const [pick, setPick] = useState('');
  const mine = sectors.data || [];
  const sector = mine.find((s) => s.id === (user.isAdmin ? pick || user.sectorId : user.sectorId)) || mine[0];
  return (
    <>
      <Err text={sectors.error} />
      {user.isAdmin && mine.length > 1 && (
        <div className="actions" style={{ marginTop: 0, marginBottom: '.6rem', alignItems: 'center' }}>
          <label htmlFor="fs" style={{ margin: 0 }}>Sector</label>
          <select id="fs" value={sector?.id || ''} onChange={(e) => setPick(e.target.value)}>{mine.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}</select>
        </div>
      )}
      {sector ? <DetectDesk key={sector.id} title={`Live feed · ${sector.name}`} sectorLock={sector.id} extraRight={<RecentCatches sector={sector} />} /> : !sectors.loading && <div className="empty">No sector found for this account.</div>}
    </>
  );
}
